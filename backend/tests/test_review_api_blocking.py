"""
A running review must not freeze the rest of the API.

`run_procurement_review` is an `async def`, so FastAPI runs it on the event
loop rather than in the threadpool. Everything it calls is synchronous:
reading each document means a GCS download and a PyMuPDF parse, and the store
writes block too. Done directly, that holds the only event loop for as long as
the documents take, and every other request — the procurement page, /health —
waits behind it.

Measured before the fix: /health, which only reads settings, did not answer in
60 seconds while a review was in flight, then answered in 0.22s once it
finished.

These tests pin the property rather than the implementation: while a review is
reading documents, the loop still gets a turn. pytest-asyncio is not a
dependency here, so each test drives its own loop with asyncio.run.
"""

import asyncio
import threading
import time

import pytest

from domain import Procurement, ProcurementDocument
from review.schema import ReviewResult
from routers import review_api

#: How long a faked document read blocks for. Long enough that a blocked loop
#: is unambiguous, short enough to keep the suite quick.
READ_SECONDS = 0.3

#: The ticker runs every 10ms, so an unblocked loop manages many turns across
#: three reads. Asserting only a handful keeps this from flaking on a slow box.
MIN_TICKS = 5


class FakeStore:
    """Just enough store for the endpoint, with blocking writes like the real one."""

    def __init__(self, procurement):
        self._procurement = procurement
        self.saved = 0

    def get_procurement(self, ref):
        return self._procurement if ref == self._procurement.ref else None

    def save_procurement(self, procurement):
        self.saved += 1
        return procurement

    def replace_findings(self, ref, findings, engine="ai_review"):
        return findings


@pytest.fixture
def procurement():
    return Procurement(
        ref="PROC-TEST-001",
        title="Supply of Rack Servers",
        documents=[
            ProcurementDocument(
                id=f"doc-{n}",
                name=f"Document {n}.pdf",
                doc_type="Terms of Reference (TOR)",
                pages=10,
                gcs_path=f"gs://bucket/doc-{n}.pdf",
            )
            for n in range(3)
        ],
    )


@pytest.fixture(autouse=True)
def fake_backends(monkeypatch, procurement):
    """Stand in for the GCS download and the PDF parse, which both block."""

    def slow_read(path):
        time.sleep(READ_SECONDS)
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(review_api, "read_document", slow_read)
    monkeypatch.setattr(review_api, "extract_text", lambda data: "[page 1] Some text.")
    monkeypatch.setattr(review_api, "get_store", lambda: FakeStore(procurement))

    async def no_findings(ctx, keys=None):
        return ReviewResult(procurement_ref=ctx.procurement_ref)

    monkeypatch.setattr(review_api, "run_review", no_findings)


def test_review_does_not_block_the_event_loop(procurement):
    """The whole point: other requests still get served during a review."""
    ticks = 0

    async def drive():
        nonlocal ticks

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        beat = asyncio.create_task(ticker())
        try:
            await review_api.run_procurement_review(procurement.ref, keys=None)
        finally:
            beat.cancel()

    asyncio.run(drive())

    assert ticks >= MIN_TICKS, (
        f"the event loop only got {ticks} turns while three documents were read; "
        "the review is blocking it and every other request queues behind it"
    )


def test_documents_are_read_off_the_event_loop(procurement, monkeypatch):
    """The reads belong on a worker thread, not the loop's own."""
    read_threads = []
    loop_thread = {}

    def record_thread(path):
        read_threads.append(threading.current_thread().ident)
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(review_api, "read_document", record_thread)

    async def drive():
        loop_thread["ident"] = threading.current_thread().ident
        await review_api.run_procurement_review(procurement.ref, keys=None)

    asyncio.run(drive())

    assert read_threads, "no documents were read"
    assert all(ident != loop_thread["ident"] for ident in read_threads), (
        "documents were read on the event loop thread"
    )


def test_documents_are_read_concurrently(procurement):
    """
    Three independent downloads should overlap.

    Off the loop is not the same as fast: read one at a time, the reviewer
    still waits the sum of every bucket round trip before the first model call.
    """
    started = time.monotonic()
    asyncio.run(review_api.run_procurement_review(procurement.ref, keys=None))
    elapsed = time.monotonic() - started

    sequential = READ_SECONDS * len(procurement.documents)
    assert elapsed < sequential * 0.7, (
        f"reading {len(procurement.documents)} documents took {elapsed:.2f}s "
        f"against {sequential:.2f}s sequential — they are not overlapping"
    )


def test_document_order_survives_concurrency(procurement, monkeypatch):
    """Whichever download finishes first, the reviewer sees the attached order."""
    # Reverse the durations, so the last document would finish first.
    delays = {
        f"gs://bucket/doc-{n}.pdf": 0.05 * (len(procurement.documents) - n)
        for n in range(len(procurement.documents))
    }

    def staggered_read(path):
        time.sleep(delays[path])
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(review_api, "read_document", staggered_read)

    context = review_api._build_context(procurement)

    assert [d.name for d in context.documents] == [
        d.name for d in procurement.documents
    ]


def test_review_still_returns_its_result(procurement):
    """Moving work to a thread must not change what the endpoint answers."""
    response = asyncio.run(
        review_api.run_procurement_review(procurement.ref, keys=None)
    )

    assert response.ref == procurement.ref
    assert response.findings == []
