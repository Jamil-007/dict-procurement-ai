"""
Put the Knowledge Hub reference PDFs into the bucket.

The Hub is seeded as metadata only — title, category, excerpt — and
data/knowledge_seed.json is generated from data/knowledge_sources.json, the
same manifest build_knowledge_index.py reads for the RAG corpus. Until this
script has actually been run, every entry's gcs_path is empty and the
Download button in the Hub has nothing to serve — that is the whole reason it
does not work out of the box; the source PDFs living in the corpus folder are
a separate pipeline (the RAG index) that never touches an entry's gcs_path.

Usage:

    1. A PDF matches an entry either by being named after its id
       (ra-12009-irr.pdf) or, more usually, by being the exact file
       data/knowledge_sources.json lists for that doc_id — so pointing this
       at the same folder used for `build_knowledge_index.py --source`
       just works, with the original filenames intact.
       Run with --list to see every id and which are still missing.

    2. Upload:
           cd backend
           GCS_BUCKET=ai-procurement GOOGLE_CLOUD_PROJECT=ai-innov-474401 \
           python scripts/upload_knowledge.py ../Reference

Files land at gs://{bucket}/knowledge/{id}.pdf and the entry's gcs_path is
updated, which is what makes the Download button work.

Re-running is safe: it overwrites the object and the entry, so it doubles as
the way to replace a superseded issuance.

If you uploaded the PDFs to the bucket some other way — the console, gsutil —
the entries still won't show as downloadable: gcs_path lives on the Firestore
document, not the bucket, and nothing set it. Use --link-only instead of a
folder: it checks gs://{bucket}/knowledge/{id}.pdf for each entry and sets
gcs_path for whichever ones it finds, without uploading anything itself.

    GCS_BUCKET=ai-procurement GOOGLE_CLOUD_PROJECT=ai-innov-474401 \
    python scripts/upload_knowledge.py --link-only

Add --write-seed to also patch gcs_path straight into data/knowledge_seed.json
on disk. That file is what MemoryStore and the Firestore seeder both load at
startup, so committing it is what makes Download work for every developer who
pulls this branch, on any STORE_BACKEND, without each of them running this
script or standing up their own Firestore — a per-developer --link-only run
only ever fixes it for that one person's database.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from store import get_store  # noqa: E402
from store.files import count_pages  # noqa: E402

SOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_sources.json"
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_seed.json"


def _source_filenames() -> dict:
    """doc_id -> filename, from the same manifest the RAG index build reads."""
    if not SOURCES_PATH.is_file():
        return {}
    import json

    return {row["doc_id"]: row["filename"] for row in json.loads(SOURCES_PATH.read_text(encoding="utf-8"))}


def _patch_seed(gcs_paths: dict, pages: dict) -> int:
    """
    Write gcs_path (and, where known, pages) into knowledge_seed.json itself.

    This is what makes Download work for a developer who has never run this
    script and never touched Firestore: MemoryStore and the Firestore seeder
    both load this file at startup, so a committed gcs_path here is picked up
    everywhere, not just in whichever store this process happens to be
    pointed at.
    """
    import json

    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    patched = 0
    for row in rows:
        if row["id"] in gcs_paths:
            row["gcs_path"] = gcs_paths[row["id"]]
            if row["id"] in pages:
                row["pages"] = pages[row["id"]]
            patched += 1
    SEED_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return patched


def _resolve(entry_id: str, folder: Path, sources: dict) -> Path | None:
    """
    The PDF for one entry, or None if it is not in the folder.

    Tries the entry's own id first, then the filename knowledge_sources.json
    records for it — so a folder of files kept under their real names (as
    build_knowledge_index.py expects) works without renaming anything.
    """
    by_id = folder / f"{entry_id}.pdf"
    if by_id.is_file():
        return by_id
    filename = sources.get(entry_id)
    if filename and (folder / filename).is_file():
        return folder / filename
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "folder", nargs="?", help="Folder of PDFs named {entry-id}.pdf"
    )
    parser.add_argument(
        "--list", action="store_true", help="Show every entry id and its status"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would happen, write nothing"
    )
    parser.add_argument(
        "--link-only",
        action="store_true",
        help="The PDFs are already in the bucket (uploaded some other way) — "
        "just check gs://{bucket}/knowledge/{id}.pdf for each entry and set "
        "gcs_path for whichever ones exist. No folder needed.",
    )
    parser.add_argument(
        "--write-seed",
        action="store_true",
        help="Also patch gcs_path into data/knowledge_seed.json, so Download "
        "works for every developer who pulls this branch, not just against "
        "whichever store this process happens to be pointed at.",
    )
    args = parser.parse_args()

    store = get_store()
    entries = {e.id: e for e in store.list_knowledge()}
    if not entries:
        print("The Knowledge Hub is empty. Start the API once to seed it.")
        return 1

    if args.list or not (args.folder or args.link_only):
        print(f"{len(entries)} entries\n")
        for entry in entries.values():
            state = "uploaded" if entry.gcs_path else "MISSING "
            print(f"  [{state}] {entry.id}.pdf   {entry.title}")
        missing = sum(1 for e in entries.values() if not e.gcs_path)
        print(f"\n{missing} still to upload.")
        return 0

    if not settings.GCS_BUCKET:
        print(
            "GCS_BUCKET is not set, so there is nowhere to put these.\n"
            "Re-run with GCS_BUCKET=ai-procurement."
        )
        return 1

    if settings.STORE_BACKEND == "memory" and not args.write_seed:
        print(
            "STORE_BACKEND=memory, so the entries are held in this process only.\n"
            "The PDFs would reach the bucket but the Download links would go back\n"
            "to 'not uploaded yet' as soon as the API restarts. Either run this\n"
            "against the store the API uses (STORE_BACKEND=firestore), or add\n"
            "--write-seed to patch data/knowledge_seed.json instead — that works\n"
            "on any store backend and is what every other developer's copy loads."
        )
        return 1

    if args.link_only:
        from google.cloud import storage

        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        bucket = client.bucket(settings.GCS_BUCKET)

        linked_paths = {}
        for entry in entries.values():
            blob_name = f"knowledge/{entry.id}.pdf"
            if not bucket.blob(blob_name).exists():
                continue
            gcs_path = f"gs://{settings.GCS_BUCKET}/{blob_name}"
            if args.dry_run:
                print(f"  would link {entry.id} -> {gcs_path}")
                continue
            entry.gcs_path = gcs_path
            store.save_knowledge(entry)
            linked_paths[entry.id] = gcs_path
            print(f"  linked {entry.id}")

        if not args.dry_run:
            if args.write_seed and linked_paths:
                _patch_seed(linked_paths, {})
            remaining = len(entries) - len(linked_paths)
            print(f"\nLinked {len(linked_paths)}. {remaining} entries still have no document.")
        return 0

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Not a folder: {folder}")
        return 1

    sources = _source_filenames()
    resolved = {
        entry.id: path
        for entry in entries.values()
        if (path := _resolve(entry.id, folder, sources)) is not None
    }
    if not resolved:
        print(f"No PDF in {folder} matches a Knowledge Hub entry.")
        print("Run with --list to see every entry id and the filename it expects.")
        return 1

    from google.cloud import storage

    client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
    bucket = client.bucket(settings.GCS_BUCKET)

    uploaded_paths = {}
    uploaded_pages = {}

    for entry_id, path in resolved.items():
        entry = entries[entry_id]
        data = path.read_bytes()
        pages = count_pages(data)
        blob_name = f"knowledge/{entry.id}.pdf"

        if args.dry_run:
            print(f"  would upload {path.name} -> gs://{settings.GCS_BUCKET}/{blob_name}")
            continue

        bucket.blob(blob_name).upload_from_string(
            data, content_type="application/pdf"
        )
        gcs_path = f"gs://{settings.GCS_BUCKET}/{blob_name}"
        entry.gcs_path = gcs_path
        if pages:
            entry.pages = pages
        store.save_knowledge(entry)
        uploaded_paths[entry.id] = gcs_path
        if pages:
            uploaded_pages[entry.id] = pages
        print(f"  {entry.id}  {len(data) // 1024} KB, {pages} pages")

    unmatched = len(entries) - len(resolved)
    if unmatched:
        print(f"\n{unmatched} entr{'y has' if unmatched == 1 else 'ies have'} no file in {folder}.")
        print("Run with --list to see which.")

    if not args.dry_run:
        if args.write_seed and uploaded_paths:
            _patch_seed(uploaded_paths, uploaded_pages)
        remaining = len(entries) - len(uploaded_paths)
        print(f"\nUploaded {len(uploaded_paths)}. {remaining} entries still have no document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
