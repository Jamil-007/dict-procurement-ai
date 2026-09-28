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

> **Hidden for now:** the **Form Generator** workspace tab. The component
> (`frontend/components/procurement-records/forms-tab.tsx`) and its route are
> untouched — the tab is just removed from `TABS` in
> `frontend/app/(shell)/items/[ref]/page.tsx`, so it is unreachable rather than
> deleted. Re-add the string to `TABS` and its render branch to bring it back.

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

**OCR needs Tesseract installed separately — `pip install` alone is not enough.**
`store/files.py`'s `extract_text()` falls back to OCR for any page with no
embedded text layer (a scan, or a print-to-PDF export that never wrote real
text), but `pytesseract` only calls out to a `tesseract` binary — it does not
ship one. On Windows, install it from the
[UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki) and either
put it on `PATH` or set `TESSERACT_CMD` in `.env` to the installed
`tesseract.exe` path; on macOS/Linux, `brew install tesseract` or
`apt install tesseract-ocr` puts it on `PATH` directly. The Cloud Run image
installs it via `apt-get` in the `Dockerfile`, so production needs nothing
extra. Without it, a scanned document's pages come back as empty text and a
dimension has nothing to review — this fails soft (empty text, not a crash),
so the symptom is a dimension reporting "no discernible content," not an error.

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
def run(ctx: ReviewContext) -> DimensionOutput:
    ...
```

Registration is the only shared state. The `/review/dimensions` endpoint, the
runner and the report sections all read the registry, so adding or renaming a
dimension is a backend-only change — the frontend picks it up with no edit.

`run` may return a bare `list[ReviewFinding]` or a `DimensionOutput`, which
wraps the same findings with an `assessment` of what was reviewed and any
`research_gaps`. The runner accepts either. The envelope exists because "I
checked and found nothing" and "I had nothing to check" both render as an
empty list, and the committee has to be able to tell those apart.

### Dimension status

All five are live. What separates them is what each one is allowed to say — the
whole design rests on the boundaries between them, because five reviewers over
one set of documents will otherwise file the same finding five times.

| Dimension | Key | Owner | Its question |
|---|---|---|---|
| Compliance | `compliance` | Dev B | Does the documentation appear aligned with applicable procurement requirements? |
| Document Consistency | `document_consistency` | Dev A | Do the documents agree with one another on the same facts? |
| Document Quality | `document_quality` | Mark | Is each individual document complete, clear, structured and internally coherent? |
| Procurement & Market | `procurement_market` | Mark | Does the procurement make sense against available market evidence? |
| Requirements & Risk | `requirements_risk` | Dev C | Are requirements sufficiently defined, and are material risks addressed? |

The boundaries that get crossed most often, written out because they are not
obvious:

- A delivery period of 30 days in section 3 and 60 days in section 8 of the
  **same** document is Document Quality. The same disagreement **across** two
  documents is Document Consistency.
- "The support requirement says 'adequate' without defining it" is Document
  Quality — the wording. "Coverage, response time and escalation are undefined"
  is Requirements & Risk — the substance. Not both.
- "Only two suppliers carry this module" is Procurement & Market. "The
  procurement does not address that dependency" is Requirements & Risk.
- A missing requirement is only Compliance when a retrieved provision requires
  it. Otherwise it is a requirement gap, not a rule breach.

**The procurement record (title, ABC, mode, fund, category) is not evidence.**
It is what the BAC typed into the case when it was created, often before every
document was attached, and no dimension is allowed to treat it as ground truth
or judge a document against it. Every fact a dimension reports — including the
ABC that Procurement & Market reasons about — is established from the
documents themselves; the record is shown to the model only for orientation,
and a mismatch between it and the documents is Document Consistency's finding
to make, not a reason for another dimension to prefer the record's number.
`RECORD_IS_NOT_EVIDENCE` in `review/parsing.py` is the shared instruction that
enforces this — every dimension that shows the model `ctx.meta` pastes it in.

Three are worth reading before the others:

- **`document_quality`** is the shape everything else follows: build a prompt,
  call `analyze_with_summary()`, return the output.
- **`compliance`** leans hardest on the reference library, because its subject
  matter *is* the rules. Every statutory citation is grounded against what
  retrieval actually returned (`ground_policy_basis`), so a provision the model
  half-remembers is discarded rather than shown to the BAC.
- **`procurement_market`** is the only one that can reach outside the documents.
  Its full brief is `docs/dimension-procurement-market.md`. Two things are easy
  to get wrong: the Tavily search is optional and off by default, and a
  specification that looks tailored to one product is raised as *a potential
  concern requiring BAC review*, never as a determination that it is restrictive.

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

### The Knowledge Hub is a separate thing from this index

The frontend's Knowledge Hub — the browsable, downloadable list at `/hub` — is
**not** this index. It reads `data/knowledge_seed.json`, a different manifest,
and a document's Download button only works once its entry has a `gcs_path`
pointing at a real object in the bucket. Adding a doc_id to
`knowledge_sources.json` makes the RAG index pick it up; it does nothing for
the Hub, and the two manifests drifting apart is exactly how the Hub ended up
seeded with fifteen fabricated placeholder entries — invented page counts, a
fictional Supreme Court citation, even RA 9184 — that never matched a real
file and could never be downloaded.

**Adding a reference**, so both stay in sync:

```bash
cd backend

# 1. Drop the PDF in ../Reference, named after its id: gppb-res-99-2026.pdf

# 2. Add one entry to data/knowledge_sources.json:
#    { "doc_id": "gppb-res-99-2026", "filename": "gppb-res-99-2026.pdf",
#      "title": "GPPB Resolution No. 99-2026", "category": "GPPB Issuances" }

# 3. Parse it into the RAG index
python scripts/build_knowledge_index.py --source ../Reference

# 4. Add it to the Hub's list (only adds — never touches an existing entry)
python scripts/sync_knowledge_seed.py --source ../Reference

# 5. Get it into the bucket and link gcs_path, committing the result so
#    Download works for every developer who pulls the branch, not just you
python scripts/upload_knowledge.py ../Reference --write-seed
```

Step 5 assumes you have bucket write access and want the script to upload for
you. If you uploaded the PDFs some other way (console, `gsutil`), use
`--link-only` instead of the folder argument — it checks what's already in the
bucket rather than uploading. `--write-seed` is what makes the result durable:
without it, `gcs_path` only lands in whatever store this process happens to be
pointed at, which for `STORE_BACKEND=memory` is gone the moment the process
restarts.

---

## Storage

Two axes, independent of each other:

| | Local default | Production |
|---|---|---|
| Records — procurements, findings, Knowledge Hub | `STORE_BACKEND=memory`, wiped on restart | `STORE_BACKEND=firestore` |
| Files — uploaded PDFs | `GCS_BUCKET=` empty, local disk under `UPLOAD_DIR` | `GCS_BUCKET=proc-ai-staging-files` |

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
2. Write the prompt, paste in `FINDING_JSON_CONTRACT` and `SUMMARY_CONTRACT`,
   call `analyze_with_summary()`, return the `DimensionOutput`.
3. Say in the prompt what the dimension does **not** own. Every dimension has a
   `STAY INSIDE THIS DIMENSION` section, and a test asserts it is still there.
4. Import the module in `review/dimensions/__init__.py`. That is the only shared
   file you touch.
5. Add its key to `ORDER` in `review/registry.py` if you want a specific position.

The runner owns parallelism, timeouts, finding ids and error isolation. A
dimension's `run` may be sync or async; a sync one is given a worker thread, so a
blocking `llm.invoke()` will not stall the others.

Try one in isolation without going through the API:

```bash
cd backend
python scripts/try_dimension.py
```
