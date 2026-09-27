# Handover — DICT Procurement AI
---

## 🔗 Live app (start here)

| What | URL |
|---|---|
| **Frontend (use this)** | https://procurement-ai-rgkvi7273a-as.a.run.app |
| **Backend API** | https://procurement-ai-backend-rgkvi7273a-as.a.run.app |
| Backend health check | https://procurement-ai-backend-rgkvi7273a-as.a.run.app/health |

- GCP project: **`ai-innov-474401`** · region: **`asia-southeast1`**
- **No login** — both services are public (`--allow-unauthenticated`). Pilot/demo data only.
- Live backend is confirmed healthy: `vertex_ai` / `gemini-2.5-flash`.


---

## What this system is

An AI assistant for Philippine government procurement under **RA 12009** (the New
Government Procurement Act), built for a DICT Bids and Awards Committee (BAC). You
create a procurement record, attach its pre-award documents, and run an **AI Review**
that returns *findings* (each citing a document, page, and — where relevant — the law).
The committee accepts / edits / rejects each finding, and those decisions roll up into
a Final Report. **It advises; a human always decides.**

The current branch merges **two feature tracks** into one app under a single top nav:
1. **Procurement Records + AI Review + Knowledge Hub** (the primary product)
2. **ProcAI analyzer + Form Generator + Feedback Bank** (added later)

---

## What you can actually reach (frontend)

Next.js 14 (App Router). Four links in the top-right nav pill, all live:

| Nav link | URL | What it is |
|---|---|---|
| **ProcAI** | `/` | Chat-style analyzer: upload up to 3 PDFs, watch live "thinking" logs, get a PASS/FAIL verdict + report, chat about the doc, generate forms inline. |
| **Forms** | `/forms` | Standalone Form Generator: upload docs (auto-detects GPPB form types) and pick which procurement forms to generate. `/forms/review` edits & downloads them. |
| **Procurements** | `/items` | The BAC records list. Open one (`/items/[ref]`) for a tabbed workspace: **Overview · Documents · AI Review · Final Report**. |
| **Knowledge Hub** | `/hub` | Searchable library of procurement laws/forms with in-browser PDF preview + download. |

**Hidden on purpose:** the per-record **Form Generator tab** inside `/items/[ref]`.
The component (`components/procurement-records/forms-tab.tsx`) and backend are intact —
it's just removed from the `TABS` array. Re-add `"Form Generator"` to `TABS` (and its
render branch) in `app/(shell)/items/[ref]/page.tsx` to bring it back. *(The standalone
`/forms` page is NOT hidden.)*

**Dead code to ignore:** `components/shell/app-sidebar.tsx` isn't rendered anywhere and
links to a nonexistent `/analyst` route.

Branding: rebranded to **"ProcAI"**, with a fixed **BETA** badge on every page.

---

## The subsystems, in plain terms

### 1. AI Review (the core) — ✅ fully implemented
Runs **five independent "dimension" analyzers in parallel** (each its own LLM call,
180s timeout, failures isolated) over a record's documents:

| Dimension | Checks |
|---|---|
| **Compliance** | Alignment with RA 12009 / IRR / GPPB / COA + documentary completeness (leans hardest on the law index; every citation is grounded). |
| **Document Consistency** | The same fact agreeing *across* documents (ABC, quantities, dates, scope). Needs ≥2 docs. |
| **Document Quality** | Each single document's completeness, clarity, structure, internal coherence. |
| **Procurement & Market** | Spec openness, ABC vs market reality, dependencies. The only one that can search the web (Tavily, **off by default**). |
| **Requirements & Risk** | Whether requirements are well-defined and material risks are addressed. |

Findings follow a frozen schema (`review/schema.py`): severity `critical/medium/low/info/compliant`,
a separate confidence score, policy citations, and external-source tiers.

### 2. Knowledge index (RAG) + Knowledge Hub — ✅ works out of the box
- A **built index is committed** (`backend/data/knowledge_index/`: 1,774 chunks from 14
  legal PDFs), so RAG works locally with no setup.
- Retrieval is **hybrid** (keyword BM25 + vector cosine, fused). Without `GOOGLE_API_KEY`
  it silently drops to keyword-only — still functional.
- Findings can only cite provisions retrieval actually returned (anti-hallucination guard).
- The **Knowledge Hub** browser is separate from the index: it lists entries as metadata.
  **Download is inert** until PDFs are pushed to GCS via `scripts/upload_knowledge.py`.

### 3. Doc Generation / Forms — ✅ backend complete
Upload PDFs → detect each type → extract fields with an LLM → generate filled GPPB forms
(docx/xlsx) for download. Endpoints: `/forms/catalog · /upload · /detect · /extract · /generate`.
- **Group A** (richly filled): PPMP, Market Scoping, APP, Contract.
- **Group B** (blank bidder annexes, header-stamped only): Bid Form, Price Schedules, BSD, OSS, PSD.
- **Robust without an LLM:** classifier and header extraction have regex fallbacks; missing
  values render as literal `[TBD]` (never fabricated), with a "verify before submission" disclaimer.

### 4. Feedback Bank — ✅ built, ON in prod, backend-only consumer
Captures human corrections and feeds the *trusted* ones back into the **forms extractor**
as few-shot hints on future extractions.
- **Trust gate:** a correction is only used after it repeats `FEEDBACK_MIN_REPEATS` times
  (default 3; 👍 +1 / 👎 −1). Stops one bad edit from steering the model.
- **Local (SQLite)** for dev vs **Firestore vector search** for prod.
- ⚠️ **Never switch backends on a populated bank** — local uses hash embeddings, Firestore
  uses Vertex neural embeddings; the vector spaces are incompatible.

### Legacy path (heads-up)
`graph.py` + `agents/analysis.py` is an **older 6-agent LangGraph pipeline** behind
`/analyze`, `/stream`, `/review`, `/chat` (what the ProcAI `/` page uses). It's separate
from the five-dimension AI Review and is a candidate for retirement — see `System Overview.md §5`.

---

## Running it locally

Two terminals. Backend on **8000**, frontend on **3000**.

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt                     # + requirements-dev.txt for pytest/ruff
cp .env.example .env                                 # then set ONE llm key (see below)
uvicorn server:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local                    # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```
Open **http://localhost:3000**.

**Minimum config to run:** just an LLM provider. Pick one in `.env`:
- `LLM_PROVIDER=google_genai` + `GOOGLE_API_KEY=...` (Gemini via AI Studio — the dev default), **or**
- `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=...`, **or**
- `LLM_PROVIDER=vertex_ai` + `GOOGLE_CLOUD_PROJECT=...` (needs GCP credentials).

Defaults (`STORE_BACKEND=memory`, empty `GCS_BUCKET`) touch **no** GCP resources, and the
RAG index is already committed — so the app runs offline-ish with just a key. For persistent
local records use the Firestore emulator (`System Overview.md §9`).

> **Frontend port:** `npm run dev` uses 3000. To change: `npm run dev -- -p 3001`
> (and update `NEXT_PUBLIC_API_URL` only if you move the *backend*, not the frontend).

---

## Deploying

One wrapper handles it:
```bash
./deploy.sh            # backend, then frontend (full release)
./deploy.sh backend    # backend only
./deploy.sh frontend   # frontend only (reuses existing backend URL)
```
**Order matters:** backend first. The frontend bakes `NEXT_PUBLIC_API_URL` into its image
at *build* time by reading the deployed backend's URL, so the backend must already exist.

**Auto-deploy:** merging to `main` auto-deploys the **staging** services via GitHub Actions
(`.github/workflows/deploy-staging.yml`, only the changed side). **Prod** is manual
(`deploy-prod.yml`, `workflow_dispatch`). CI (`ci.yml`) runs pytest + `npm run build` on PRs.

### ⚠️ Before you deploy — one infra prerequisite remains
The deploy scripts have been **reconciled into a single `backend/deploy.sh`** (the old
`deploy-backend.sh` and broken `deploy-backend-simple.sh` were removed). The new script
sets the correct combined config — Firestore-persisted records **and** the feedback bank,
correct env-var names, single instance — and has a **preflight that refuses to deploy** if a
required database is missing.

**The one thing still needed:** the records database **`ai-procurement-db` does not exist yet.**
Create it once, then deploy:
```bash
gcloud firestore databases create --database=ai-procurement-db \
  --location=asia-southeast1 --type=firestore-native --project=ai-innov-474401
```
Until it exists, `backend/deploy.sh` will stop with instructions rather than deploy a broken
service. `proc-feedback-bank` (feedback) already exists and is ready.

**What the new `backend/deploy.sh` fixes vs the old live deployment:**
- Records/Hub now persist (`STORE_BACKEND=firestore`, `FIRESTORE_DATABASE=ai-procurement-db`) instead of in-memory.
- Pinned to `min=1,max=1` (was `max=10`) — required while LangGraph state + uploads are in-process/local-disk.
- Feedback DB uses the correct var `FEEDBACK_FIRESTORE_DATABASE=proc-feedback-bank` (the live service wrongly set `FIRESTORE_DATABASE`, so it was silently using `(default)`).

**Optional later — persist uploaded files (GCS):** file blobs currently stay on local disk
(fine for a single instance; wiped on redeploy). To persist them and allow scaling, grant the
runtime SA `roles/storage.objectAdmin` on `gs://ai-procurement`, then set `GCS_BUCKET="ai-procurement"`
in `backend/deploy.sh`. (Bucket exists; the SA does **not** yet have access — verified.)

---

## Config reference (backend `config.py`)

**Required to run:** `LLM_PROVIDER` + the matching key (`GOOGLE_API_KEY` /
`ANTHROPIC_API_KEY` / Vertex creds). `GOOGLE_API_KEY` is *also* used for the RAG
embeddings regardless of provider — without it, RAG is keyword-only.

**Common optional knobs:**
| Var | Default | Purpose |
|---|---|---|
| `STORE_BACKEND` | `memory` | `firestore` to persist records/findings/Hub. |
| `FIRESTORE_DATABASE` | `""` | Named DB for records (required when store=firestore; app refuses `(default)`). |
| `GCS_BUCKET` | `""` | Bucket for uploaded docs; empty = local disk. |
| `TAVILY_API_KEY` | `""` | Enables web search in the Procurement & Market dimension. |
| `GAMMA_API_KEY` | `""` | Slide generation (optional). |
| `FEEDBACK_BANK_ENABLED` | `False` | Master switch for the feedback bank. |
| `FEEDBACK_BACKEND` | `local` | `firestore` in prod (vector search). |
| `FEEDBACK_FIRESTORE_DATABASE` | `(default)` | Feedback DB (`proc-feedback-bank`) — separate from records DB. |
| `FEEDBACK_MIN_REPEATS` | `3` | Trust-gate threshold. |
| `VERTEX_MODEL_NAME` | `gemini-2.0-flash-exp` | Prod overrides to `gemini-2.5-flash`. |
| `GEMINI_THINKING_BUDGET` | `1024` | Gemini 2.5 reasoning-token cap (`0`=off, `-1`=dynamic). |

Full list with every flag is in `config.py` (well-commented). `STATE_STORAGE` accepts
`sqlite`/`postgres` but **only `memory` is implemented**.

**Frontend:** only `NEXT_PUBLIC_API_URL` (baked in at build time).

---

## Prerequisites in the cloud (verified status)

Project `ai-innov-474401`, region `asia-southeast1`. ✅ = ready, ⛔ = must provision.

- ✅ **Secret Manager:** `TAVILY_API_KEY`, `GAMMA_API_KEY` (deploys read `:latest`).
- ✅ **Firestore `proc-feedback-bank`** (feedback bank) — exists. Needs a **vector index** on
  `embedding` (COSINE) for `find_nearest`; verify it's present before enabling feedback in anger.
- ⛔ **Firestore `ai-procurement-db`** (records / Knowledge Hub) — **does NOT exist yet.** Create it
  before deploying (command in the deploy section above). The `backend/deploy.sh` preflight enforces this.
- ✅ **GCS bucket `ai-procurement`** — exists, **but** the runtime SA has **no access** ⛔. Uploaded
  files stay on local disk until you grant `roles/storage.objectAdmin` and set `GCS_BUCKET`.
- ✅ **Runtime SA IAM:** `roles/datastore.user` + `roles/aiplatform.user` present.
  ⛔ `roles/storage.objectAdmin` on the bucket is **not** granted (only needed when enabling GCS).
- ✅ **CI auth:** Workload Identity Federation (`WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT` GitHub secrets).

---

## Known risks & things to fix (do not skip)

1. **🔑 Keys were exposed in git history (accepted, private repo).** `backend/env.md` (added in
   commit `f8396e9`, "Added explaniner document .md") once held live `TAVILY_API_KEY=tvly-…` and
   `GAMMA_API_KEY=sk-gam…`. It's untracked at HEAD but the commit remains across `main`,
   `feature/mark`, and this branch. **Decision: no rotation** — the repo is private. If it ever
   goes public or the keys leave the team, rotate both and purge the file from history first.
2. **No authentication anywhere.** Both services are public. Threads/records are protected
   only by unguessable UUIDs. Pilot data only. (`System Overview.md §7`.)
3. **Re-running a review discards prior findings *and* their BAC decisions** — finding IDs
   are reassigned each run. Known behavior; flag before relying on it. (Not yet fixed.)
4. ~~Records not persisted~~ — **fixed in `backend/deploy.sh`** (Firestore + single instance);
   just create `ai-procurement-db` first (see deploy section).
5. ~~Docs drift in `System Overview.md`~~ — **fixed**: the Form Generator "no backend" line and
   the "only `document_quality` implemented" line have been corrected.

---

## Where to go deeper
- **`README.md`** — "Getting it running", severity/confidence scales, "Adding a dimension".
- **`System Overview.md`** — full architecture, the two AI paths, security/isolation (§7),
  known risks (§10), per-dimension internals (§6).
- **`CLAUDE.md`** — repo conventions and the `agents/` package layout.
- **`docs/`** — per-dimension briefs, the feedback-bank explainer, form templates.
