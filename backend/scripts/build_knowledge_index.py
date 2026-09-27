"""
Build the searchable reference index from the PDFs listed in knowledge_sources.json.

Usage:

    # Build with embeddings from local PDFs
    python scripts/build_knowledge_index.py --source ../Reference

    # Build with embeddings from GCS
    python scripts/build_knowledge_index.py --source gs://bucket-name/path/

    # Build chunks only (no embeddings), useful for testing
    python scripts/build_knowledge_index.py --no-embeddings

    # Build a subset for smoke tests
    python scripts/build_knowledge_index.py --limit 2 --no-embeddings

The script reads data/knowledge_sources.json and processes each PDF listed
there. It produces three files under data/knowledge_index/:

  chunks.jsonl   One JSON object per line, readable and diffable.
  vectors.npy    float32 embeddings, shape (n_chunks, dimensions). Omitted
                 when --no-embeddings is set.
  manifest.json  What was built, from what, and when.

Warns and skips missing files rather than crashing, so a partial build is
still useful. Reports duplicate PDFs (by sha256) because they waste embedding
quota and inflate the index.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.corpus import chunk_document
from knowledge.schema import (
    CHUNKS_FILE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    MANIFEST_FILE,
    VECTORS_FILE,
    Chunk,
    IndexManifest,
    SourceDocument,
)
from store.files import count_pages, extract_text, read_document


def sha256_digest(data: bytes) -> str:
    """Fingerprint a PDF so duplicate files can be detected."""
    return hashlib.sha256(data).hexdigest()


def load_sources(manifest_path: Path) -> list[dict]:
    """Read the list of documents the index should cover."""
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Could not read {manifest_path}: {exc}") from exc


def read_pdf(source_dir: str, filename: str) -> bytes | None:
    """
    Fetch a PDF from local disk or GCS. Returns None if the file is missing.

    The source_dir can be a local path like "../Reference" or a GCS prefix like
    "gs://bucket-name/path/". read_document handles both.
    """
    if source_dir.startswith("gs://"):
        path = f"{source_dir.rstrip('/')}/{filename}"
    else:
        path = str(Path(source_dir) / filename)

    try:
        return read_document(path)
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001 - best effort file reading
        print(f"  ERROR reading {filename}: {exc}")
        return None


def embed_chunks(
    chunks: list[Chunk], batch_size: int = 100, model: str = EMBEDDING_MODEL
):
    """
    Produce embeddings for a list of chunks. Batches the calls to avoid
    timeouts and retries transient failures once.

    Returns a float32 numpy array with shape (len(chunks), dimensions).
    """
    try:
        import numpy as np
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        from config import settings
    except ImportError as exc:
        raise SystemExit(f"Missing dependency for embeddings: {exc}") from exc

    if not settings.GOOGLE_API_KEY:
        raise SystemExit(
            "GOOGLE_API_KEY is not set. Cannot generate embeddings without it."
        )

    # output_dimensionality must be passed explicitly; the model's own default
    # is 3072 and silently produces an index four times larger than intended.
    embedder = GoogleGenerativeAIEmbeddings(
        model=model,
        google_api_key=settings.GOOGLE_API_KEY,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )

    texts = [chunk.text for chunk in chunks]
    all_vectors = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        print(f"  embedding {i + 1}..{min(i + len(batch), len(texts))} / {len(texts)}")

        # Retry once on transient failures. The quota errors are permanent and
        # should fail immediately, but network glitches are worth retrying.
        for attempt in range(2):
            try:
                vectors = embedder.embed_documents(batch)
                all_vectors.extend(vectors)
                break
            except Exception as exc:
                if attempt == 0:
                    print(f"  retrying batch {i // batch_size + 1} after error: {exc}")
                    time.sleep(2)
                else:
                    raise SystemExit(f"Embedding failed: {exc}") from exc

    array = np.array(all_vectors, dtype=np.float32)
    print(f"  embedded {len(chunks)} chunks -> {array.shape}")
    return array


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        default="../Reference",
        help="Directory or gs:// prefix where the PDFs live",
    )
    parser.add_argument(
        "--out",
        default="data/knowledge_index",
        help="Output directory for the built index",
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding generation (chunks only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N documents (for testing)",
    )
    args = parser.parse_args()

    backend_root = Path(__file__).resolve().parent.parent
    sources_path = backend_root / "data" / "knowledge_sources.json"
    out_dir = backend_root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Source PDFs : {args.source}")
    print(f"Output dir  : {out_dir}")
    print(f"Embeddings  : {'disabled' if args.no_embeddings else 'enabled'}")
    if args.limit:
        print(f"Limit       : {args.limit} document(s)")
    print()

    source_list = load_sources(sources_path)
    if args.limit > 0:
        source_list = source_list[: args.limit]

    all_chunks: list[Chunk] = []
    documents: list[SourceDocument] = []
    missing: list[str] = []
    seen_hashes: dict[str, str] = {}  # sha256 -> doc_id

    for entry in source_list:
        doc_id = entry["doc_id"]
        filename = entry["filename"]
        title = entry["title"]

        print(f"Processing {doc_id} — {filename}")

        pdf_data = read_pdf(args.source, filename)
        if pdf_data is None:
            print("  WARN: file not found, skipping")
            missing.append(filename)
            continue

        # Detect duplicates by content hash. Different filenames that contain
        # the same PDF waste embedding quota and bloat the index.
        file_hash = sha256_digest(pdf_data)
        if file_hash in seen_hashes:
            print(
                f"  WARN: duplicate content detected!"
                f"\n        This file matches {seen_hashes[file_hash]}"
                f"\n        Both have sha256 {file_hash[:16]}..."
            )
        seen_hashes[file_hash] = doc_id

        # Extract text with page markers so the chunker knows what page each
        # passage comes from. This takes a few seconds per document.
        pages = count_pages(pdf_data)
        text = extract_text(pdf_data, max_pages=0, markers=True)
        if not text.strip():
            print("  WARN: no extractable text, skipping")
            continue

        # Chunk the text. The chunker is pure and fast.
        chunks = chunk_document(doc_id, title, text)
        print(f"  {pages} pages -> {len(chunks)} chunks")

        all_chunks.extend(chunks)
        documents.append(
            SourceDocument(
                doc_id=doc_id,
                title=title,
                filename=filename,
                sha256=file_hash,
                pages=pages,
                chunks=len(chunks),
            )
        )

    if missing:
        print(f"\nWARNING: {len(missing)} file(s) were not found and were skipped:")
        for name in missing:
            print(f"  - {name}")
        print()

    if not all_chunks:
        print("No chunks produced. Nothing to write.")
        return 1

    # Write chunks as JSONL so a diff shows what changed in the corpus.
    chunks_path = out_dir / CHUNKS_FILE
    print(f"Writing {len(all_chunks)} chunks to {chunks_path}")
    with chunks_path.open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")

    # Generate and write embeddings unless disabled.
    dimensions = 0
    embedding_model = ""
    if not args.no_embeddings:
        print("Generating embeddings (this will take several minutes)...")
        vectors = embed_chunks(all_chunks)
        dimensions = vectors.shape[1]
        embedding_model = EMBEDDING_MODEL

        vectors_path = out_dir / VECTORS_FILE
        print(f"Writing vectors to {vectors_path}")
        import numpy as np

        np.save(vectors_path, vectors)

    # Write the manifest so retrieval knows what it is loading.
    manifest = IndexManifest(
        built_at=datetime.now(timezone.utc).isoformat(),
        embedding_model=embedding_model,
        dimensions=dimensions,
        chunk_count=len(all_chunks),
        documents=documents,
    )
    manifest_path = out_dir / MANIFEST_FILE
    print(f"Writing manifest to {manifest_path}")
    manifest_path.write_text(
        json.dumps(manifest.to_json(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Summary table: what went into the index.
    print("\n" + "=" * 72)
    print(f"{'Document':<40} {'Pages':>6} {'Chunks':>8}")
    print("=" * 72)
    for doc in documents:
        print(f"{doc.title[:40]:<40} {doc.pages:6} {doc.chunks:8}")
    print("-" * 72)
    total_pages = sum(d.pages for d in documents)
    print(f"{'TOTAL':<40} {total_pages:6} {len(all_chunks):8}")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
