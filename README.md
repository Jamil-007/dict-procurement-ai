# DICT Procurement Intelligence Platform

An AI-assisted review tool for Philippine government procurement under **RA 12009**
(the New Government Procurement Act), built for the DICT Bids and Awards Committee.

The BAC creates a procurement record, attaches its pre-award documents (Terms of
Reference, Market Study, Purchase Request, BAC Resolution and so on), and runs an
**AI Review**. The review returns *findings* — each citing a specific document and
page — which the committee accepts, modifies, rejects, or sends for further study.
Those decisions flow into a Final Report.

The review is a gate immediately before posting to PhilGEPS. It advises; it never
decides. Every finding is phrased so a human makes the call.

> This README is the orientation and setup guide. **`System Overview.md`** at the
> root is the long-form technical document — read it before changing a screen or
> writing a dimension. `docs/` holds the per-dimension briefs.

---

## Contents

- [Getting it running](#getting-it-running)
- [How the system fits together](#how-the-system-fits-together)
- [The AI Review](#the-ai-review)
  - [Dimension status](#dimension-status)
  - [Severity scale](#severity-scale)
  - [Confidence](#confidence)
- [The knowledge index (RAG)](#the-knowledge-index-rag)
- [Storage](#storage)
- [Performance notes](#performance-notes)
- [Tests and CI](#tests-and-ci)
- [Adding a dimension](#adding-a-dimension)

---

## Getting it running

Requires Python 3.11 and Node 20.

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate        # Windows (Git Bash); use venv/bin/activate on macOS/Linux
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env                # then set GOOGLE_API_KEY
uvicorn server:app --reload --port 8000
```

`http://localhost:8000/docs` for the OpenAPI browser, `/health` for the live
configuration (provider, model, thinking budget).

**The defaults in `.env.example` need no GCP resources and no credentials.**
Records live in memory and uploaded PDFs on local disk, so nothing you do locally
can reach shared data unless you deliberately change `STORE_BACKEND` or
`GCS_BUCKET`. The one key you do need is `GOOGLE_API_KEY` — without it the review
cannot call a model.

`--reload` watches the source but **not** `.env`. Change a setting and you must
restart the process; a stale worker is the usual reason an edit appears to have
had no effect.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local    # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

---

## How the system fits together

```
frontend/  Next.js 16 · React 18 · Tailwind · shadcn-style components
    │
    │  REST, no auth (single BAC account, see System Overview.md §7)
    ▼
backend/   FastAPI
    ├── routers/       procurements · knowledge · review_api
    ├── review/        the review engine — registry, runner, dimensions
    ├── knowledge/     the reference corpus and its retrieval
    ├── store/         records (memory | Firestore) and files (disk | GCS)
    └── utils/         llm_factory, doc_classifier
```

What happens on **upload** (`POST /procurements/{ref}/documents`):

1. The request body is read, and each file size-checked against a 25MB limit.
2. Each file is stored and, if no type was supplied, its opening pages are
   parsed for an excerpt. This is blocking work (a bucket round trip plus
   PyMuPDF), so it runs on worker threads, all files at once.
3. The excerpts go to `classify_many`, which infers the document type — the BAC
   no longer picks one on upload, and can correct it afterwards.

What happens on **review** (`POST /procurements/{ref}/review`):

1. Every attached document is downloaded and parsed into a `ReviewContext`,
   concurrently and off the event loop. An unreadable file logs a warning and is
   skipped; it never stops the review.
2. The runner fans out to the registered dimensions in parallel, each with a
   180-second timeout. A dimension that fails or times out is reported as such
   and the others still return.
3. Findings are grounded, assigned ids, and written to the store, replacing any
   previous review for that procurement — **including the BAC decisions recorded
   against it.**

The endpoint returns everything at once. There is no streaming: the step-by-step
checklist in the UI is a timer, not backend progress. The runner does expose an
`on_dimension` hook for real progress, currently unused.

---

## The AI Review

Five independent dimensions run over one set of documents. Each is a single file
under `backend/review/dimensions/` that registers itself:

```python
@register(key="document_quality", label="Document Quality", blurb="...", owner="Mark")
def run(ctx: ReviewContext) -> list[ReviewFinding]:
    ...
```

Registration is the only shared state. The `/review/dimensions` endpoint, the
runner and the report sections all read the registry, so adding or renaming a
dimension is a backend-only change — the frontend picks it up with no edit.

### Dimension status

| Dimension | Key | Status | Owner | Covers |
|---|---|---|---|---|
| Compliance | `compliance` | **Stub** | Dev B | RA 12009, its IRR, GPPB and COA issuances, documentary completeness |
| Document Consistency | `document_consistency` | **Stub** | Dev B | Figures, dates, quantities and terms compared across documents |
| Document Quality | `document_quality` | **Live** | Mark | Structure, clarity and completeness of the TOR and technical specs |
| Procurement & Market | `procurement_market` | **Live** | Mark | Specification openness, ABC alignment, existing system dependencies |
| Requirements & Risk | `requirements_risk` | **Stub** | Mark | Deliverables, warranty, payment conditions, contract obligations |

**Stub** means the module registers and runs but returns no findings — roughly 30
lines, no model call. The dimension appears in the UI and reports "ok / 0
findings". Nothing outside the stub's own file needs to change to fill it in.

Two are live, and they are not equivalent:

- **`document_quality`** is the worked example. Build a prompt, call `analyze()`,
  return findings. Read it first.
- **`procurement_market`** is the only dimension using retrieval, and the only one
  that can reach outside the documents. Its full brief is
  `docs/dimension-procurement-market.md`. Two things are easy to get wrong: the
  Tavily search is optional and off by default, and a specification that looks
  tailored to one product is raised as *a potential concern requiring BAC review*,
  never as a determination that it is restrictive.

### Severity scale

Every finding carries one of five levels. `review/schema.py` is the single source
— the prompt and the UI tooltip both read `SEVERITY_MEANING`, so they cannot drift
apart.

| Level | Meaning |
|---|---|
| `critical` | Potentially material issue requiring prompt BAC attention |
| `medium` | Meaningful issue but generally does not by itself prevent continuation |
| `low` | Minor quality or completeness issue |
| `info` | Observation rather than an identified deficiency |
| `compliant` | Checked and no issue found |

The wording is deliberately hedged. This tool advises a committee that holds the
legal responsibility; a finding that reads as a ruling is a defect.

`compliant` is not padding — recording what was checked and passed is how the BAC
sees the review's coverage rather than only its complaints.

Findings written under the earlier three-level scale are coerced on load
(`warning` → `medium`, `high` → `critical`), so older procurements still render.

### Confidence

Separate from severity, and deliberately so: how sure the analyzer is, versus how
serious it would be if true. A `critical` finding held at `low` confidence still
belongs in front of the BAC — it just has to say so.

| Level | Rests on |
|---|---|
| `high` | Figures stated in the documents, or an official source |
| `medium` | Indicative sources, or a comparison needing assumptions |
| `low` | Weaker ground — see `CONFIDENCE_MEANING` in `review/schema.py` |

### BAC decisions

Each finding can be `accepted`, `modified`, `further` (needs further study) or
`rejected`. Editing the severity, title, analysis or recommendation marks the
finding edited and records the decision as `modified`; the original AI wording is
preserved in `ai_analysis` so the two can always be compared.

---

## The knowledge index (RAG)

`procurement_market` cites real provisions of RA 12009 and related issuances. It
does this against a **pre-built index committed to the repo** — there is no vector
database.

```
backend/data/
  knowledge_sources.json        which PDFs belong in the corpus
  knowledge_index/
    chunks.jsonl                one JSON object per chunk, readable and diffable
    vectors.npy                 float32 embeddings, shape (n_chunks, 768)
    manifest.json               what was built, from what, and when
```

Retrieval (`knowledge/retrieve.py`) is hybrid: a hand-rolled BM25 and cosine
similarity over the vectors, fused with Reciprocal Rank Fusion. The tokeniser
preserves Philippine legal citation patterns — `23.1`, `12009`, `2023-004` survive
as single tokens instead of being split into noise.

**It never raises.** If embedding is unavailable or slow, it degrades to
keyword-only and the review continues.

Anti-hallucination is structural rather than instructional: `ground_policy_basis()`
only permits citing chunk ids that retrieval actually returned, and the quoted text
is materialised from the chunk. The model never supplies a citation from memory.

Embeddings use `models/gemini-embedding-001` at **768 dimensions**, not the 3072
default, which keeps `vectors.npy` around 5MB rather than 22MB. Embedding always
bills to `GOOGLE_API_KEY` whatever `LLM_PROVIDER` is set to.

To rebuild after changing the corpus:

```bash
cd backend
python scripts/build_knowledge_index.py --source ../Reference
python scripts/build_knowledge_index.py --no-embeddings   # chunks only, for testing
```

The source PDFs are **not** in the repo (`Reference/` is gitignored) — they live in
the bucket under `knowledge/`. `data/knowledge_sources.json` lists what belongs
there. Commit the rebuilt index files.

---

## Storage

Two axes, independent of each other:

| | Local default | Production |
|---|---|---|
| Records — procurements, findings, Knowledge Hub | `STORE_BACKEND=memory`, wiped on restart | `STORE_BACKEND=firestore` |
| Files — uploaded PDFs | `GCS_BUCKET=` empty, local disk under `UPLOAD_DIR` | `GCS_BUCKET=ai-procurement` |

For persistence locally, use the Firestore **emulator**, not a real database:

```bash
gcloud emulators firestore start --host-port=127.0.0.1:8098
```

then set `STORE_BACKEND=firestore` and `FIRESTORE_EMULATOR_HOST=127.0.0.1:8098`.
`config.py` copies that host into `os.environ` at import, because the Google client
reads only the real environment — set in `.env` alone it would be ignored and you
would quietly hit the real database.

---

## Performance notes

Three things dominate review latency, all of them already tuned. If a review gets
slow again, check them in this order.

1. **`GEMINI_THINKING_BUDGET`.** The 2.5 models think by default on a dynamic
   budget. Measured on a real review prompt: 17.7s and ~2,900 invisible reasoning
   tokens, against 4.5s with thinking off. Capped at 1024. `/health` reports the
   live value — if the key is missing, the worker is running stale code or the
   provider is not Gemini.
2. **Blocking work on the event loop.** `uvicorn` runs one loop; an `async def`
   handler that calls synchronous I/O freezes every other request, including
   `/health`. Both upload and review now push their bucket and PyMuPDF work to
   threads. `tests/test_upload_blocking.py` and `tests/test_review_api_blocking.py`
   pin this — they assert the loop keeps getting turns, not any particular
   implementation.
3. **Document fetches are concurrent.** Five attachments used to mean five
   sequential bucket round trips before the first model call.

A slow *page load* is usually not a slow page — it is the request queued behind
something holding the loop. Test by hitting `/health`, which only reads settings.

No token or cost accounting exists yet: `review/llm.py` discards
`response.usage_metadata`. Billing is visible only on the provider consoles.

---

## Tests and CI

```bash
cd backend
pytest                      # 102 tests
ruff check . && ruff format --check .
```

`pytest-asyncio` is deliberately not a dependency — async tests drive their own
loop with `asyncio.run`.

CI (`.github/workflows/ci.yml`) runs on PRs to `main`: backend tests then ruff,
frontend `npm ci && npm run build`. Lint runs *after* the tests because it
currently fails on pre-existing code — typing style and formatting, not defects —
and a broken test is the more urgent signal.

---

## Adding a dimension

1. Copy `review/dimensions/document_quality.py` — it is the reference shape.
2. Write the prompt, call `analyze()`, return `ReviewFinding`s.
3. Import the module in `review/dimensions/__init__.py`. That is the only shared
   file you touch.
4. Add its key to `ORDER` in `review/registry.py` if you want a specific position.

The runner owns parallelism, timeouts, finding ids and error isolation. A
dimension's `run` may be sync or async; a sync one is given a worker thread, so a
blocking `llm.invoke()` will not stall the others.

Try one in isolation without going through the API:

```bash
cd backend
python scripts/try_dimension.py
```
