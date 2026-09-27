"""
Uploading documents must not freeze the rest of the API.

Same defect as the review endpoint, same cause: `upload_documents` is an
`async def`, so it runs on the event loop, and per file it calls
`save_document` (a GCS upload, plus a PyMuPDF page count) and `extract_text`
(a full parse of the opening pages) synchronously. Uploading four PDFs held
the loop for the whole of four uploads, and every other request queued.

Reading the request body with `await upload.read()` was always fine — it is
the storing and parsing afterwards that blocks.

The files are also independent of one another, so they are stored
concurrently rather than one at a time.
"""

import asyncio
import threading
import time

import pytest

from domain import Procurement
from routers import procurements

#: How long a faked store-and-parse blocks for, per file.
STORE_SECONDS = 0.3

FILE_COUNT = 3

#: The ticker runs every 10ms; an unblocked loop gets many turns during the
#: uploads. A handful is enough to prove it was never frozen.
MIN_TICKS = 5


class FakeUpload:
    """Stands in for Starlette's UploadFile."""

    def __init__(self, filename: str):
        self.filename = filename

    async def read(self):
        return b"%PDF-1.4 fake"


class FakeStore:
    def __init__(self, procurement):
        self._procurement = procurement
        self.added = []

    def get_procurement(self, ref):
        return self._procurement if ref == self._procurement.ref else None

    def add_documents(self, ref, documents):
        self.added = documents
        self._procurement.documents = documents
        return self._procurement


@pytest.fixture
def procurement():
    return Procurement(ref="PROC-TEST-002", title="Supply of Rack Servers")


@pytest.fixture(autouse=True)
def fake_backends(monkeypatch, procurement):
    def slow_save(ref, filename, data):
        time.sleep(STORE_SECONDS)
        return f"gs://bucket/{ref}/{filename}", 10

    monkeypatch.setattr(procurements, "save_document", slow_save)
    monkeypatch.setattr(
        procurements, "extract_text", lambda data, max_pages=0, markers=True: "Text."
    )
    monkeypatch.setattr(procurements, "get_store", lambda: FakeStore(procurement))

    async def classified(pairs):
        return ["Terms of Reference (TOR)"] * len(pairs)

    monkeypatch.setattr(procurements, "classify_many", classified)


def _files():
    return [FakeUpload(f"Document {n}.pdf") for n in range(FILE_COUNT)]


def test_upload_does_not_block_the_event_loop(procurement):
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
            await procurements.upload_documents(procurement.ref, files=_files(), doc_types=None)
        finally:
            beat.cancel()

    asyncio.run(drive())

    assert ticks >= MIN_TICKS, (
        f"the event loop only got {ticks} turns while {FILE_COUNT} files were "
        "stored; the upload is blocking it and every other request queues behind it"
    )


def test_files_are_stored_off_the_event_loop(procurement, monkeypatch):
    store_threads = []
    loop_thread = {}

    def record_thread(ref, filename, data):
        store_threads.append(threading.current_thread().ident)
        return f"gs://bucket/{ref}/{filename}", 10

    monkeypatch.setattr(procurements, "save_document", record_thread)

    async def drive():
        loop_thread["ident"] = threading.current_thread().ident
        await procurements.upload_documents(procurement.ref, files=_files(), doc_types=None)

    asyncio.run(drive())

    assert len(store_threads) == FILE_COUNT
    assert all(ident != loop_thread["ident"] for ident in store_threads), (
        "files were stored on the event loop thread"
    )


def test_files_are_stored_concurrently(procurement):
    """Three independent uploads should not run one after another."""
    started = time.monotonic()
    asyncio.run(procurements.upload_documents(procurement.ref, files=_files(), doc_types=None))
    elapsed = time.monotonic() - started

    sequential = STORE_SECONDS * FILE_COUNT
    assert elapsed < sequential * 0.7, (
        f"{FILE_COUNT} uploads took {elapsed:.2f}s against {sequential:.2f}s "
        "sequential — they are not overlapping"
    )


def test_documents_keep_their_order(procurement):
    """Concurrency must not shuffle the files against their given types."""
    store = FakeStore(procurement)

    async def drive():
        return await procurements.upload_documents(procurement.ref, files=_files(), doc_types=None)

    result = asyncio.run(drive())
    names = [d.name for d in result.documents]

    assert names == [f"Document {n}.pdf" for n in range(FILE_COUNT)]
    assert store is not None  # the fixture's store is what actually recorded them
