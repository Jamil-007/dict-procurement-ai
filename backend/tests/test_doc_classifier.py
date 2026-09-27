"""
Document type inference, filename pass and model pass.

The filename is the uploader's own label for the file. When it names a type
outright it is good evidence and it is free, so it runs first and a hit skips
the model call entirely.

The bar for a hit is deliberately high: exactly one type may match. A filename
carrying two type words is the uploader being loose, not the classifier being
clever, and it falls through to the model, which at least has the text.
"""

import pytest

from domain import DOC_TYPES
from utils import doc_classifier
from utils.doc_classifier import classify, classify_filename

# Enough text to get past the "too short to classify" floor.
SOME_TEXT = "Section 1. Scope of work. " * 20


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    """
    Fail loudly if a test reaches the model.

    Most of these assert the filename pass answered on its own, and an
    accidental network call would otherwise pass silently.
    """

    def forbidden():
        raise AssertionError("the model was called when it should not have been")

    monkeypatch.setattr("utils.llm_factory.get_llm", forbidden)


# --- the filename pass ---


@pytest.mark.parametrize(
    "filename,expected",
    [
        # Spelled out.
        ("Terms of Reference.pdf", "Terms of Reference (TOR)"),
        ("Annual Procurement Plan 2026.pdf", "Annual Procurement Plan (APP)"),
        (
            "Certificate of Availability of Funds.pdf",
            "Certificate of Availability of Funds",
        ),
        ("Post-Qualification Report.pdf", "Post-Qualification Report"),
        ("Notice of Award.pdf", "Notice of Award"),
        # "scoping" is the checklist's word alone, so this must not come back
        # as Market Study, and must not be ambiguous between the two either.
        ("Market Scoping Checklist.pdf", "Market Scoping Checklist"),
        # Acronyms.
        ("TOR.pdf", "Terms of Reference (TOR)"),
        ("PPMP-2026.pdf", "Project Procurement Management Plan (PPMP)"),
        ("ITB.pdf", "Invitation to Bid"),
        ("NOA.pdf", "Notice of Award"),
        # Separators, casing and a procurement ref in front.
        ("PROC-2026-004_technical_specifications_v2.PDF", "Technical Specifications"),
        ("proc 2026 004 market study.pdf", "Market Study"),
        ("BAC_Resolution_No_12.pdf", "BAC Resolution"),
        # Paths, in case a client sends one.
        ("uploads/2026/Purchase Request.pdf", "Purchase Request"),
        ("Contract_Agreement_signed.pdf", "Contract"),
        # "contract" alone is too loose to type a file by, so it abstains and
        # the word that actually names a type wins.
        ("Contract Cost Breakdown.pdf", "Detailed Cost Breakdown"),
    ],
)
def test_filename_names_the_type(filename, expected):
    assert classify_filename(filename) == expected
    assert expected in DOC_TYPES


@pytest.mark.parametrize(
    "filename",
    [
        # Nothing to go on.
        "Scan_0012.pdf",
        "document (1).pdf",
        "",
        # Two types named at once — the uploader was loose, so ask the model.
        "TOR and Technical Specifications.pdf",
        "Bidding Documents with TOR.pdf",
        # A type word inside a longer word must not count.
        "Motor Vehicle Inventory.pdf",
    ],
)
def test_filename_gives_nothing(filename):
    assert classify_filename(filename) is None


def test_an_it_project_called_an_app_is_not_a_procurement_plan():
    """
    'APP' is both a document type and an everyday word at an ICT agency.

    So the plan has to be spelled out. Bare 'app' in a filename is far more
    likely to be the subject of the procurement than its type.
    """
    assert classify_filename("Mobile App TOR.pdf") == "Terms of Reference (TOR)"
    assert classify_filename("Mobile App.pdf") is None


# --- how it plugs into classify() ---


def test_a_named_file_never_reaches_the_model():
    """The point of a first pass: no round trip when the filename settles it."""
    # The autouse fixture turns a model call into a failure.
    assert classify("TOR.pdf", SOME_TEXT) == "Terms of Reference (TOR)"


def test_a_scanned_file_is_still_typed_from_its_name():
    """
    An image-only PDF yields no text and used to be a flat 'Other'.

    The filename is all there is, and it is often right, so it is now used.
    """
    assert classify("Purchase Request.pdf", "") == "Purchase Request"


def test_an_unnamed_file_falls_through_to_the_model(monkeypatch):
    class Reply:
        content = "Market Study"

    monkeypatch.setattr(
        doc_classifier, "_ask_model", lambda filename, excerpt: Reply.content
    )
    assert classify("Scan_0012.pdf", SOME_TEXT) == "Market Study"


def test_an_unnamed_scanned_file_is_still_other():
    """No name to read and no text to read: do not pretend."""
    assert classify("Scan_0012.pdf", "") == "Other"
