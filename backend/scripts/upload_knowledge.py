"""
Put the Knowledge Hub reference PDFs into the bucket.

The Hub is seeded as metadata only — title, category, excerpt. The actual
documents (RA 12009, GPPB issuances, COA circulars, the standard forms) are
published material that changes rarely, so they are loaded by running this
once rather than through an upload screen.

Usage:

    1. Name each PDF after its entry id and drop them in one folder:
           ra-12009.pdf
           gppb-resolution-05-2024.pdf
       Run with --list to see every id and which are still missing.

    2. Upload:
           cd backend
           GCS_BUCKET=ai-procurement GOOGLE_CLOUD_PROJECT=ai-innov-474401 \
           python scripts/upload_knowledge.py ./kb-pdfs

Files land at gs://{bucket}/knowledge/{id}.pdf and the entry's gcs_path is
updated, which is what makes the Download button work.

Re-running is safe: it overwrites the object and the entry, so it doubles as
the way to replace a superseded issuance.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from store import get_store  # noqa: E402
from store.files import count_pages  # noqa: E402


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
    args = parser.parse_args()

    store = get_store()
    entries = {e.id: e for e in store.list_knowledge()}
    if not entries:
        print("The Knowledge Hub is empty. Start the API once to seed it.")
        return 1

    if args.list or not args.folder:
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

    if settings.STORE_BACKEND == "memory":
        print(
            "STORE_BACKEND=memory, so the entries are held in this process only.\n"
            "The PDFs would reach the bucket but the Download links would go back\n"
            "to 'not uploaded yet' as soon as the API restarts. Run this against\n"
            "the store the API uses (STORE_BACKEND=firestore)."
        )
        return 1

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Not a folder: {folder}")
        return 1

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {folder}")
        return 1

    from google.cloud import storage

    client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
    bucket = client.bucket(settings.GCS_BUCKET)

    uploaded = 0
    unmatched = []

    for path in pdfs:
        entry = entries.get(path.stem)
        if not entry:
            unmatched.append(path.name)
            continue

        data = path.read_bytes()
        pages = count_pages(data)
        blob_name = f"knowledge/{entry.id}.pdf"

        if args.dry_run:
            print(f"  would upload {path.name} -> gs://{settings.GCS_BUCKET}/{blob_name}")
            continue

        bucket.blob(blob_name).upload_from_string(
            data, content_type="application/pdf"
        )
        entry.gcs_path = f"gs://{settings.GCS_BUCKET}/{blob_name}"
        if pages:
            entry.pages = pages
        store.save_knowledge(entry)
        uploaded += 1
        print(f"  {entry.id}  {len(data) // 1024} KB, {pages} pages")

    if unmatched:
        print(
            f"\nSkipped {len(unmatched)} file(s) with no matching entry id: "
            f"{', '.join(unmatched)}"
        )
        print("Run with --list to see the ids these should be named after.")

    if not args.dry_run:
        remaining = sum(1 for e in store.list_knowledge() if not e.gcs_path)
        print(f"\nUploaded {uploaded}. {remaining} entries still have no document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
