"""OCR for scanned procurement documents.

Every real DICT transaction document in this project is a scanned image: the
Purchase Request, TOR, Delivery Receipt, PAR, Inspection Report and Contract
Agreement all return zero characters from PyMuPDF's text extractor. Only the
legal corpus (RA 12009, the IRR, GAM, GPPB and COA issuances) has a text layer.

Scanned pages are rendered with PyMuPDF and read with Claude vision, which
preserves tables, signature blocks, stamps and handwriting. When no
ANTHROPIC_API_KEY is configured (or the key is rejected), pages fall back to
local Tesseract OCR so ingestion still works offline.

Results are cached per page, so re-ingesting a document costs nothing and a
failure partway through a 62-page bidding document does not discard the pages
already read.
"""

from __future__ import annotations

import base64
import concurrent.futures
import io
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import pymupdf

from config import settings
from ingest.cache import cache_key, file_sha256, read_cache, write_cache

# Bump when OCR_PROMPT changes so cached vision pages are re-read.
PROMPT_VERSION = "v1"
# Bump when Tesseract settings change so cached fallback pages are re-read.
TESSERACT_VERSION = "tesseract-v1"

OCR_PROMPT = """You are transcribing a page from a Philippine government procurement document.

Transcribe the page to markdown. Rules:

1. Transcribe EXACTLY what is on the page. Never infer, correct, complete or
   summarize. If a figure reads 1,250.00, write 1,250.00.
2. Preserve tables as markdown tables. Keep every column, including empty
   cells. Line-item tables (quantity, unit, description, unit cost, amount)
   are the most important content on most of these pages -- do not collapse,
   merge or reorder their rows.
3. Reproduce serial numbers, contract numbers, PR/PO/DV numbers, and
   reference numbers character for character.
4. For each signature block, record the printed name, position, and whether a
   signature and date are actually present, like this:
   [SIGNATURE BLOCK: role="Approved by" name="JUAN DELA CRUZ" position="Director IV" signed=yes date="12/04/2024"]
   Use signed=no when the line is blank. Use name="" when no printed name appears.
5. Record stamps, seals and received marks as
   [STAMP: text] with the transcribed text.
6. Transcribe handwriting and mark it as [HANDWRITTEN: text]. If handwriting
   is illegible, write [HANDWRITTEN: illegible].
7. Mark anything you cannot read confidently as [ILLEGIBLE].
8. Checkboxes: use [x] for ticked and [ ] for unticked.

Output only the transcription. No preamble, no commentary, no code fences."""

_BLANK_PAGE_MARKER = "[BLANK PAGE]"

# Used to pick pages out of documents that exceed the page budget.
_PRIORITY_KEYWORDS = (
    "signature",
    "signed",
    "approved",
    "certified",
    "conforme",
    "amount",
    "total",
    "quantity",
    "unit cost",
    "contract",
    "delivery",
    "specification",
    "schedule of requirements",
    "bill of quantities",
    "technical specification",
    "eligibility",
    "abstract",
)


@dataclass
class OcrPage:
    """One transcribed page."""

    page_no: int  # 1-indexed, matching the physical page
    text: str
    source: str  # "text_layer" | "vision" | "tesseract" | "cache" | "skipped"


@dataclass
class OcrResult:
    """The transcription of a whole document."""

    path: str
    pages: List[OcrPage] = field(default_factory=list)
    total_pages: int = 0
    skipped_pages: List[int] = field(default_factory=list)
    cache_hits: int = 0
    vision_calls: int = 0
    had_text_layer: bool = False

    @property
    def text(self) -> str:
        """The document as one markdown string with page anchors.

        The `--- Page N ---` anchors are load-bearing: fact extraction records
        a page number for every value so findings can cite their evidence.
        """
        parts = [f"--- Page {p.page_no} ---\n{p.text}" for p in self.pages]
        if self.skipped_pages:
            parts.append(
                f"--- NOTE ---\nPages not transcribed (page budget of "
                f"{settings.OCR_MAX_PAGES} reached): "
                f"{_format_ranges(self.skipped_pages)}"
            )
        return "\n\n".join(parts)


@dataclass
class TextLayerProbe:
    """What PyMuPDF's text extractor found in a PDF."""

    total_pages: int
    page_text: Dict[int, str]  # 1-indexed page number -> extracted text
    chars_per_page: float
    has_text_layer: bool

    def pages_needing_vision(self) -> List[int]:
        """Pages whose own text layer is too thin to trust."""
        return [
            n
            for n in range(1, self.total_pages + 1)
            if len(self.page_text.get(n, "").strip()) < settings.OCR_MIN_CHARS_PER_PAGE
        ]


def _format_ranges(numbers: Sequence[int]) -> str:
    """Render [1,2,3,7,9,10] as '1-3, 7, 9-10'."""
    if not numbers:
        return ""
    ordered = sorted(numbers)
    ranges: List[str] = []
    start = prev = ordered[0]
    for n in ordered[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = n
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(ranges)


def probe_text_layer(pdf_path: str | Path) -> TextLayerProbe:
    """Check whether a PDF carries real extractable text.

    A scanned document returns a handful of stray characters at most, so the
    per-page average is compared against OCR_MIN_CHARS_PER_PAGE rather than
    testing for emptiness.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    page_text: Dict[int, str] = {}
    with pymupdf.open(path) as doc:
        total_pages = len(doc)
        for index, page in enumerate(doc):
            page_text[index + 1] = page.get_text()

    total_chars = sum(len(t.strip()) for t in page_text.values())
    chars_per_page = total_chars / total_pages if total_pages else 0.0

    return TextLayerProbe(
        total_pages=total_pages,
        page_text=page_text,
        chars_per_page=chars_per_page,
        has_text_layer=chars_per_page >= settings.OCR_MIN_CHARS_PER_PAGE,
    )


def select_pages(
    probe: TextLayerProbe,
    candidates: Sequence[int],
    max_pages: int,
) -> List[int]:
    """Choose which pages to send to vision when a document exceeds the budget.

    Front matter and signature pages carry the fields the checkers need, so
    the head and tail are always kept. Pages with a partial text layer are
    ranked by procurement keywords; the rest of the budget is filled by an
    even sweep so no long stretch of the document goes unread.
    """
    candidates = sorted(candidates)
    if len(candidates) <= max_pages:
        return list(candidates)

    head = candidates[: max(1, max_pages // 3)]
    tail = candidates[-max(1, max_pages // 6) :]
    chosen = set(head) | set(tail)

    # Keyword ranking only works on pages that have *some* text. Fully scanned
    # documents fall through to the even sweep below.
    scored: List[tuple[int, int]] = []
    for page_no in candidates:
        if page_no in chosen:
            continue
        haystack = probe.page_text.get(page_no, "").lower()
        if not haystack:
            continue
        hits = sum(1 for kw in _PRIORITY_KEYWORDS if kw in haystack)
        if hits:
            scored.append((hits, page_no))
    for _, page_no in sorted(scored, key=lambda pair: (-pair[0], pair[1])):
        if len(chosen) >= max_pages:
            break
        chosen.add(page_no)

    remaining = [p for p in candidates if p not in chosen]
    slots = max_pages - len(chosen)
    if slots > 0 and remaining:
        step = max(1, len(remaining) // slots)
        for page_no in remaining[::step][:slots]:
            chosen.add(page_no)

    return sorted(chosen)[:max_pages]


def render_page_png(page: "pymupdf.Page", dpi: int, max_edge: int) -> bytes:
    """Render a page to PNG, capped at `max_edge` on the long side."""
    zoom = dpi / 72.0
    rect = page.rect
    long_edge = max(rect.width, rect.height) * zoom
    if long_edge > max_edge:
        zoom *= max_edge / long_edge
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    return pixmap.tobytes("png")


def _configure_tesseract() -> None:
    """Point pytesseract at the Tesseract binary, failing with a clear message."""
    import pytesseract

    candidates = [
        settings.TESSERACT_CMD,
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        str(Path.home() / r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return
    raise RuntimeError(
        "No OCR engine available: no usable vision API key and Tesseract is "
        "not installed. Install it (e.g. `winget install UB-Mannheim.TesseractOCR`) "
        "or set TESSERACT_CMD in .env to the full path of tesseract.exe."
    )


def ocr_page_tesseract(png_bytes: bytes) -> str:
    """Transcribe a single rendered page with local Tesseract."""
    import pytesseract
    from PIL import Image

    try:
        with Image.open(io.BytesIO(png_bytes)) as image:
            text = pytesseract.image_to_string(image, lang="eng")
    except pytesseract.TesseractError as exc:
        raise RuntimeError(f"Tesseract OCR failed: {exc}") from exc
    return text.strip() or _BLANK_PAGE_MARKER


def _anthropic_client():
    """Build an Anthropic client; caller has already checked the key exists."""
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _is_auth_error(exc: Exception) -> bool:
    detail = str(exc).lower()
    return (
        "401" in detail
        or "403" in detail
        or "authentication" in detail
        or "x-api-key" in detail
        or "api key" in detail
        or "api_key" in detail
        or "permission" in detail
    )


def _strip_fences(text: str) -> str:
    """Remove a wrapping code fence if the model added one despite instructions."""
    stripped = text.strip()
    match = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", stripped, re.DOTALL)
    return match.group(1) if match else stripped


def ocr_page_vision(client, png_bytes: bytes, model: str) -> str:
    """Transcribe a single rendered page with Claude vision."""
    import anthropic

    image_b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"Vision OCR failed ({exc.status_code}): {exc}") from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(f"Could not reach the Anthropic API: {exc}") from exc

    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return _strip_fences(text) or _BLANK_PAGE_MARKER


def ocr_page_gemini(client, png_bytes: bytes, model: str) -> str:
    """Transcribe a single rendered page with Gemini vision."""
    from google.genai import errors, types

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                OCR_PROMPT,
            ],
        )
    except errors.APIError as exc:
        raise RuntimeError(f"Vision OCR failed ({exc.code}): {exc.message}") from exc
    return _strip_fences(response.text or "") or _BLANK_PAGE_MARKER


def ocr_pdf(
    pdf_path: str | Path,
    dpi: Optional[int] = None,
    max_pages: Optional[int] = None,
    model: Optional[str] = None,
    force: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> OcrResult:
    """Transcribe a PDF, using its text layer where it has one and OCR elsewhere.

    Gemini vision is used when GOOGLE_API_KEY is configured, else Claude
    vision via ANTHROPIC_API_KEY. With no usable key, pages fall back to
    local Tesseract.

    Args:
        pdf_path: Path to the PDF.
        dpi: Render resolution. Defaults to OCR_DPI.
        max_pages: Page budget for OCR. Defaults to OCR_MAX_PAGES.
        model: Vision model override.
        force: Ignore cached pages and re-read them.
        progress: Optional callback for human-readable progress lines.

    Returns:
        An OcrResult whose `.text` is the full transcription.
    """
    path = Path(pdf_path)
    dpi = dpi or settings.OCR_DPI
    max_pages = max_pages or settings.OCR_MAX_PAGES
    use_gemini = bool(settings.GOOGLE_API_KEY)
    model = model or (
        settings.GEMINI_MODEL_NAME if use_gemini else settings.OCR_MODEL_NAME
    )
    emit = progress or (lambda _msg: None)

    probe = probe_text_layer(path)
    result = OcrResult(
        path=str(path),
        total_pages=probe.total_pages,
        had_text_layer=probe.has_text_layer,
    )

    scanned_pages = probe.pages_needing_vision()
    if not scanned_pages:
        emit(f"{path.name}: text layer found on all {probe.total_pages} pages")
        result.pages = [
            OcrPage(page_no=n, text=probe.page_text[n].strip(), source="text_layer")
            for n in range(1, probe.total_pages + 1)
        ]
        return result

    to_ocr = select_pages(probe, scanned_pages, max_pages)
    result.skipped_pages = [n for n in scanned_pages if n not in set(to_ocr)]
    emit(
        f"{path.name}: {len(scanned_pages)} scanned page(s), "
        f"transcribing {len(to_ocr)}"
        + (f", skipping {len(result.skipped_pages)}" if result.skipped_pages else "")
    )

    file_hash = file_sha256(path)

    def vision_key(page_no: int) -> str:
        return cache_key(
            file_hash,
            page=page_no,
            dpi=dpi,
            edge=settings.OCR_MAX_EDGE_PX,
            model=model,
            prompt=PROMPT_VERSION,
        )

    def tesseract_key(page_no: int) -> str:
        return cache_key(
            file_hash,
            page=page_no,
            dpi=dpi,
            edge=settings.OCR_MAX_EDGE_PX,
            engine=TESSERACT_VERSION,
        )

    # Resolve cache hits (from either engine) before rendering or calling out.
    transcribed: Dict[int, OcrPage] = {}
    pending: List[int] = []
    for page_no in to_ocr:
        cached = None
        if not force:
            cached = read_cache(vision_key(page_no)) or read_cache(
                tesseract_key(page_no)
            )
        if cached and "text" in cached:
            transcribed[page_no] = OcrPage(page_no, cached["text"], "cache")
            result.cache_hits += 1
        else:
            pending.append(page_no)

    if pending:
        emit(f"{path.name}: {result.cache_hits} cached, {len(pending)} to transcribe")

        # Rendering is CPU-bound and PyMuPDF documents are not thread-safe, so
        # pages are rendered serially up front and only the OCR calls fan out.
        rendered: Dict[int, bytes] = {}
        with pymupdf.open(path) as doc:
            for page_no in pending:
                rendered[page_no] = render_page_png(
                    doc[page_no - 1], dpi, settings.OCR_MAX_EDGE_PX
                )

        workers = max(1, min(settings.OCR_MAX_CONCURRENCY, len(pending)))
        remaining = list(pending)

        if use_gemini or settings.ANTHROPIC_API_KEY:
            if use_gemini:
                from google import genai

                client = genai.Client(api_key=settings.GOOGLE_API_KEY)

                def work(page_no: int) -> tuple[int, str]:
                    return page_no, ocr_page_gemini(client, rendered[page_no], model)
            else:
                client = _anthropic_client()

                def work(page_no: int) -> tuple[int, str]:
                    return page_no, ocr_page_vision(client, rendered[page_no], model)

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    for page_no, text in pool.map(work, remaining):
                        transcribed[page_no] = OcrPage(page_no, text, "vision")
                        result.vision_calls += 1
                        write_cache(vision_key(page_no), {"text": text, "page": page_no})
                        emit(f"{path.name}: page {page_no} transcribed")
                remaining = []
            except RuntimeError as exc:
                if not _is_auth_error(exc):
                    raise
                remaining = [p for p in remaining if p not in transcribed]
                provider = "Gemini" if use_gemini else "Anthropic"
                emit(
                    f"{path.name}: {provider} rejected the API key, "
                    f"falling back to Tesseract for {len(remaining)} page(s)"
                )
        else:
            emit(f"{path.name}: no vision API key, using local Tesseract")

        if remaining:
            _configure_tesseract()

            def work_local(page_no: int) -> tuple[int, str]:
                return page_no, ocr_page_tesseract(rendered[page_no])

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for page_no, text in pool.map(work_local, remaining):
                    transcribed[page_no] = OcrPage(page_no, text, "tesseract")
                    write_cache(
                        tesseract_key(page_no), {"text": text, "page": page_no}
                    )
                    emit(f"{path.name}: page {page_no} transcribed (tesseract)")

    # Reassemble in page order, keeping real text-layer pages in hybrid PDFs.
    pages: List[OcrPage] = []
    skipped = set(result.skipped_pages)
    for page_no in range(1, probe.total_pages + 1):
        if page_no in transcribed:
            pages.append(transcribed[page_no])
        elif page_no in skipped:
            continue
        else:
            layer_text = probe.page_text.get(page_no, "").strip()
            if layer_text:
                pages.append(OcrPage(page_no, layer_text, "text_layer"))
    result.pages = pages
    return result


def _main(argv: List[str]) -> int:
    if not argv:
        print("usage: python -m ingest.ocr <pdf-path> [--force] [--max-pages N]")
        return 2

    pdf_path = argv[0]
    force = "--force" in argv
    max_pages = None
    if "--max-pages" in argv:
        max_pages = int(argv[argv.index("--max-pages") + 1])

    result = ocr_pdf(
        pdf_path,
        max_pages=max_pages,
        force=force,
        progress=lambda msg: print(f"[ocr] {msg}", file=sys.stderr),
    )
    print(
        f"[ocr] done: {len(result.pages)}/{result.total_pages} pages, "
        f"{result.cache_hits} cached, {result.vision_calls} vision call(s)",
        file=sys.stderr,
    )
    print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
