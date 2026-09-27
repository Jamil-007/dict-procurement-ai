"""
extract_text() and its OCR fallback.

A page with an embedded text layer is read straight off with PyMuPDF and OCR
never runs. A page with none — a scan, or a print-to-PDF export that never
wrote real text — used to come back as an empty string, silently, and a
whole document could go through review looking blank. OCR is the fallback
for exactly that page.
"""

import sys
import types
from unittest.mock import MagicMock

import fitz
import pytest

from store.files import extract_text


def _pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _blank_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_a_page_with_a_text_layer_is_read_directly():
    data = _pdf_with_text("Hello procurement")

    result = extract_text(data)

    assert "Hello procurement" in result


def test_a_blank_page_falls_back_to_ocr(monkeypatch):
    fake_pytesseract = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=""),
        image_to_string=MagicMock(return_value="Text recovered by OCR"),
    )
    fake_pil_image = types.SimpleNamespace(
        frombytes=MagicMock(return_value="a fake image")
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(Image=fake_pil_image))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)

    result = extract_text(_blank_pdf())

    assert "Text recovered by OCR" in result
    fake_pytesseract.image_to_string.assert_called_once_with("a fake image")


def test_ocr_is_never_reached_when_the_page_already_has_text(monkeypatch):
    """Guards the common case from paying for OCR it doesn't need."""
    calls = MagicMock()
    monkeypatch.setattr("store.files._ocr_page", calls)

    extract_text(_pdf_with_text("Already has text"))

    calls.assert_not_called()


def test_missing_ocr_dependencies_degrade_to_empty_text(monkeypatch):
    """pytesseract/Pillow not installed must not fail the whole document."""
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    result = extract_text(_blank_pdf())

    assert result.strip() == "" or "[page 1]" in result


def test_a_tesseract_failure_does_not_fail_the_document(monkeypatch):
    fake_pytesseract = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=""),
        image_to_string=MagicMock(side_effect=RuntimeError("tesseract not found")),
    )
    fake_pil_image = types.SimpleNamespace(
        frombytes=MagicMock(return_value="a fake image")
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(Image=fake_pil_image))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)

    result = extract_text(_blank_pdf())

    assert result is not None  # did not raise


def test_tesseract_cmd_setting_is_applied(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "TESSERACT_CMD", r"C:\fake\tesseract.exe")

    fake_pytesseract = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=""),
        image_to_string=MagicMock(return_value="ocr text"),
    )
    fake_pil_image = types.SimpleNamespace(
        frombytes=MagicMock(return_value="a fake image")
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(Image=fake_pil_image))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil_image)

    extract_text(_blank_pdf())

    assert fake_pytesseract.pytesseract.tesseract_cmd == r"C:\fake\tesseract.exe"
