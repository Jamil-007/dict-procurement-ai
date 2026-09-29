"""
The procurement-record Forms tab seeds a forms session from the record's
already-persisted documents (see frontend forms-tab.tsx). A record legitimately
has many documents, so that flow must not be bound by the 3-file guardrail that
protects the standalone, ad-hoc Forms upload. /forms/upload gets a from_record
flag: set, it accepts more than 3 files; unset (ad-hoc uploads), the 3-file cap
still applies.
"""

import fitz
import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def _files(n: int):
    return [
        ("files", (f"doc{i}.pdf", _pdf(f"Document {i}"), "application/pdf"))
        for i in range(n)
    ]


def test_adhoc_upload_still_capped_at_three():
    resp = client.post("/forms/upload", files=_files(4))
    assert resp.status_code == 400
    assert "Maximum of 3" in resp.json()["detail"]


def test_record_seeded_upload_allows_more_than_three():
    resp = client.post(
        "/forms/upload",
        files=_files(4),
        data={"from_record": "true"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_docs"] is True
    assert len(body["filenames"]) == 4
