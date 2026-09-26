"""
The contract between building the reference index and querying it.

Two halves depend on this and nothing else: `corpus.py` produces Chunks and
writes them, `retrieve.py` reads them back and ranks them. Keep the on-disk
format described here in step with both.

ON DISK, under backend/data/knowledge_index/:

  chunks.jsonl   One JSON object per line, the fields of Chunk. Line order is
                 authoritative — row i of vectors.npy is line i here.
  vectors.npy    float32 array, shape (n_chunks, dimensions). Absent when the
                 index was built without embeddings; retrieval then falls back
                 to keyword-only rather than failing.
  manifest.json  The fields of IndexManifest.

Text, not a binary blob, so a reviewer can read what the model will be shown
and a diff shows what changed when the corpus is rebuilt.
"""

from dataclasses import asdict, dataclass, field

#: Where a built index lives, relative to the backend package root.
INDEX_DIRNAME = "data/knowledge_index"

CHUNKS_FILE = "chunks.jsonl"
VECTORS_FILE = "vectors.npy"
MANIFEST_FILE = "manifest.json"

#: Both halves must embed with the same model at the same width. A query
#: vector produced by a different model than the index would still return a
#: confident ranking — just a meaningless one — so this lives in the shared
#: contract rather than being repeated either side.
EMBEDDING_MODEL = "models/gemini-embedding-001"

#: The model defaults to 3072, which for this corpus is a ~22MB vectors.npy
#: committed to the repo and rewritten whole on every rebuild. 768 costs
#: little retrieval quality on passage matching and keeps it near 5MB.
EMBEDDING_DIMENSIONS = 768


@dataclass(frozen=True)
class Chunk:
    """
    One passage of a reference document, large enough to stand on its own as a
    quotable provision and small enough to retrieve precisely.

    `section` and `page` are what make a citation checkable. A finding that
    says "RA 12009 IRR Section 23.1" is only defensible if a reader can open
    that page and see the text, so every chunk carries both even when the
    heading had to be inferred.
    """

    id: str
    """Stable and unique: f"{doc_id}#{ordinal:04d}"."""

    doc_id: str
    """Matches an id in data/knowledge_sources.json."""

    doc_title: str
    """Official title as it should appear in a citation."""

    section: str
    """Nearest preceding heading, e.g. "Section 23.1". Empty when none was found."""

    page: int
    """1-based page the passage starts on. 0 when unknown."""

    text: str

    def searchable(self) -> str:
        """
        What keyword search indexes, which is more than the body text.

        Someone searching "Section 23.1" is naming the provision, not quoting
        it — the number usually appears in the heading and nowhere in the
        prose. Indexing only `text` made those queries miss the very chunk
        they asked for, so the title and section are indexed alongside it.
        """
        return f"{self.doc_title} {self.section} {self.text}"

    def cite(self) -> str:
        """How this passage should be named in a finding."""
        where = self.section or f"p{self.page}"
        return f"{self.doc_title} — {where}" if where else self.doc_title

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, row: dict) -> "Chunk":
        return cls(
            id=row["id"],
            doc_id=row["doc_id"],
            doc_title=row.get("doc_title", ""),
            section=row.get("section", ""),
            page=int(row.get("page", 0) or 0),
            text=row["text"],
        )


@dataclass(frozen=True)
class SourceDocument:
    """A PDF that went into the index, recorded so a rebuild is verifiable."""

    doc_id: str
    title: str
    filename: str
    sha256: str
    pages: int
    chunks: int


@dataclass
class IndexManifest:
    """
    What was built, from what, and when.

    The per-document sha256 is the only check available that the committed
    index still corresponds to the PDFs it claims to come from: the PDFs
    themselves live in the bucket and are not in the repo, so CI cannot
    rebuild the index to compare. A mismatch is at least detectable.
    """

    built_at: str = ""
    embedding_model: str = ""
    dimensions: int = 0
    chunk_count: int = 0
    documents: list[SourceDocument] = field(default_factory=list)

    @property
    def has_vectors(self) -> bool:
        return self.dimensions > 0

    def to_json(self) -> dict:
        return {
            "built_at": self.built_at,
            "embedding_model": self.embedding_model,
            "dimensions": self.dimensions,
            "chunk_count": self.chunk_count,
            "documents": [asdict(d) for d in self.documents],
        }

    @classmethod
    def from_json(cls, row: dict) -> "IndexManifest":
        return cls(
            built_at=row.get("built_at", ""),
            embedding_model=row.get("embedding_model", ""),
            dimensions=int(row.get("dimensions", 0) or 0),
            chunk_count=int(row.get("chunk_count", 0) or 0),
            documents=[SourceDocument(**d) for d in row.get("documents", [])],
        )


@dataclass(frozen=True)
class Provision:
    """A chunk that a search returned, with the score that got it there."""

    chunk: Chunk
    score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0

    @property
    def id(self) -> str:
        return self.chunk.id


@dataclass
class Retrieval:
    """
    What a search produced, including why it produced nothing.

    Retrieval must never raise into a review dimension — a reference library
    that is missing or unreadable degrades the review to what it does today,
    which is still useful. `note` carries the explanation to the prompt.
    """

    provisions: list[Provision] = field(default_factory=list)
    note: str = ""
    embedded: bool = False
    """True when the query was matched on meaning as well as words."""

    @property
    def ids(self) -> set:
        """The provision ids a finding is permitted to cite."""
        return {p.chunk.id for p in self.provisions}

    def render(self) -> str:
        """The retrieved provisions as prompt text, strongest match first."""
        if not self.provisions:
            return "(none)"
        blocks = []
        for p in self.provisions:
            blocks.append(
                f"[{p.chunk.id}] {p.chunk.cite()}\n"
                f"page: {p.chunk.page}\n"
                f"{p.chunk.text.strip()}"
            )
        return "\n\n---\n\n".join(blocks)


def index_dir(backend_root: str | None = None) -> str:
    """Absolute path to the index directory."""
    from pathlib import Path

    root = (
        Path(backend_root) if backend_root else Path(__file__).resolve().parent.parent
    )
    return str(root / INDEX_DIRNAME)
