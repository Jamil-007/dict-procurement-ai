"""
Add new entries to data/knowledge_seed.json from data/knowledge_sources.json.

The Hub's browsable list (knowledge_seed.json) and the RAG chunker's manifest
(knowledge_sources.json) are two different files that happen to describe the
same documents. Adding a doc_id to knowledge_sources.json makes the chunker
pick it up; it does nothing for the Hub. This is the other half: for any
doc_id in knowledge_sources.json with no matching entry yet, it reads the PDF
from --source, counts its pages, pulls a short excerpt from the opening text,
and appends a new row.

Only adds — never touches an existing entry, so a title, subtitle or date you
already hand-edited is never clobbered. Use --refresh to also recompute pages
and excerpt for existing entries after replacing a PDF with a new version.

Usage:

    cd backend
    python scripts/sync_knowledge_seed.py --source ../Reference
    python scripts/sync_knowledge_seed.py --source ../Reference --dry-run

Run this, then scripts/build_knowledge_index.py, then
scripts/upload_knowledge.py --write-seed — see README's "Adding a reference"
for the full sequence.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from store.files import count_pages, extract_text  # noqa: E402

SOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_sources.json"
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_seed.json"

DOC_TYPE_BY_KEYWORD = [
    ("resolution", "Resolution"),
    ("circular", "Circular"),
    ("irr", "IRR"),
    ("form", "Form"),
    ("manual", "Manual"),
]


def _guess_doc_type(title: str, category: str) -> str:
    low = title.lower()
    for keyword, label in DOC_TYPE_BY_KEYWORD:
        if keyword in low:
            return label
    return {"Manuals": "Manual", "Standard Forms": "Form"}.get(category, "")


def _excerpt(data: bytes) -> str:
    text = extract_text(data, max_pages=2, markers=False).strip()
    return re.sub(r"\s+", " ", text)[:280]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Folder holding the PDFs, e.g. ../Reference")
    parser.add_argument("--refresh", action="store_true", help="Also recompute pages/excerpt for existing entries")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        print(f"Not a folder: {source}")
        return 1

    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in seed}

    added = 0
    refreshed = 0
    for src in sources:
        doc_id, filename, title, category = src["doc_id"], src["filename"], src["title"], src["category"]
        path = source / filename
        existing = by_id.get(doc_id)

        if existing and not args.refresh:
            continue
        if not path.is_file():
            print(f"  SKIP {doc_id}: {filename} not found in {source}")
            continue

        data = path.read_bytes()
        pages = count_pages(data)
        excerpt = _excerpt(data)

        if existing:
            if args.dry_run:
                print(f"  would refresh {doc_id}  ({pages} pages)")
                continue
            existing["pages"] = pages
            existing["excerpt"] = excerpt
            refreshed += 1
            print(f"  refreshed {doc_id}  ({pages} pages)")
        else:
            if args.dry_run:
                print(f"  would add {doc_id}  ({pages} pages)")
                continue
            seed.append(
                {
                    "id": doc_id,
                    "title": title,
                    "subtitle": "",
                    "category": category,
                    "doc_type": _guess_doc_type(title, category),
                    "date": "",
                    "pages": pages,
                    "excerpt": excerpt,
                }
            )
            added += 1
            print(f"  added {doc_id}  ({pages} pages)")

    if not args.dry_run and (added or refreshed):
        SEED_PATH.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n{added} added, {refreshed} refreshed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
