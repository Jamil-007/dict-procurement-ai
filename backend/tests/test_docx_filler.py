from pathlib import Path
from docx import Document
import io
from forms.fillers.docx_filler import render_docx

FIX = Path(__file__).parent / "fixtures" / "mini.docx"

def test_render_replaces_and_tbd():
    out = render_docx(FIX, {"title": "Hello", "missing": None}, disclaimer="DRAFT")
    doc = Document(io.BytesIO(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Hello" in text and "DRAFT" in text and "[TBD]" in text
