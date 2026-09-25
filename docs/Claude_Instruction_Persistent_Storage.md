# Claude Instruction — Wire Up Persistent Storage

**Hand this file to whoever picks up the task.** Open Claude Code in the repository root and say:

> Read `Claude_Instruction_Persistent_Storage.md` and carry it out.

**Model: Sonnet.** This is wiring and verification against an existing design, not architecture — Sonnet is the right fit and will be faster and cheaper. Set it with `/model sonnet` before starting.

---

## Background

This repository is an AI-powered procurement document review system for DICT, built around RA 12009. It runs on Cloud Run in project `ai-innov-474401`, region `asia-southeast1`.

The application currently stores **nothing durably**. Procurement records live in a Python dict and uploaded PDFs land on the container's local disk. Cloud Run wipes both on redeploy and on scale-down, and staging runs at `min-instances 0`, so records disappear within the hour.

The code to persist to Firestore and Cloud Storage **is already written and merged**. It sits behind environment variables and is inert until those are set. Your job is to switch it on, prove it actually works, and fix the one known defect in it.

Read `docs/gcp-requirements.md` first — it is the provisioning spec that was sent to the GCP administrator and describes every resource, role and data shape involved.

---

## Preconditions — confirm before writing any code

Do not start until all four are true. If any is missing, stop and report which one.

1. Firestore exists in `ai-innov-474401`, **Native mode**, location `asia-southeast1`.
2. A Cloud Storage bucket exists in `asia-southeast1` with uniform bucket-level access and public access prevented. **Get the actual bucket name** — do not assume `ai-innov-procurement-docs`.
3. The Cloud Run runtime service account holds `roles/datastore.user` on the project and `roles/storage.objectAdmin` on the bucket. Note whether it is the default compute account or a dedicated one.
4. You have credentials that can reach both from your machine (`gcloud auth application-default login`).

Verify with:

```bash
gcloud firestore databases list --project=ai-innov-474401
gcloud storage buckets list --project=ai-innov-474401
```

---

## Tasks

### 1. Prove `FirestoreStore` works

`backend/store/firestore.py` **has never executed against a real database.** It was written without credentials available and is entirely unverified. Treat every method as suspect until you have watched it work.

Point a local backend at the real Firestore and bucket:

```bash
cd backend
export STORE_BACKEND=firestore
export GOOGLE_CLOUD_PROJECT=ai-innov-474401
export FIRESTORE_PREFIX=dev_          # keep your test data out of the real collections
export GCS_BUCKET=<actual bucket name>
venv/Scripts/python.exe -m uvicorn server:app --port 8000
```

Then exercise every path end to end — create a procurement, upload a PDF, list, patch, add and delete a document, list findings, patch a finding, add a comment, finalize. Confirm each write actually landed by reading it back in a **fresh process**, not from the same in-memory session. Check the objects appear in the bucket at `procurements/{ref}/{filename}`.

Fix whatever is broken. Expect real bugs here — pydantic models round-tripping through Firestore dictionaries, nested `documents[]` and `comments[]` lists, and `None` versus missing fields are the likely trouble spots.

Clean up your `dev_`-prefixed test data when you are done.

### 2. Fix the reference-number race

`next_ref()` in `backend/store/firestore.py` scans existing documents for the highest `PROC-{year}-NNN` and adds one. This is a read-then-write guarded only by a local lock, which does nothing across Cloud Run instances — two concurrent creates on different instances will hand out the same reference number and one will overwrite the other.

Replace it with something atomic. Either a Firestore transaction on a dedicated counter document (e.g. `counters/procurement-{year}`), or `@firestore.transactional` around the scan-and-write. A counter document is simpler and is what I would pick.

Write a test that proves it: fire off at least ten concurrent create requests and assert you get ten distinct references with no gaps.

### 3. Seed the Knowledge Hub

`FirestoreStore.seed_knowledge(overwrite=False)` loads the 15 reference entries from `backend/data/knowledge_seed.json`. Make sure it runs against the real database and that `GET /knowledge` returns all 15 with working category and search filters.

Decide where seeding is triggered from — a one-off script is fine and probably better than doing it on application startup. Say which you chose and why.

### 4. Wire the environment variables into both workflows

Add to the `gcloud run deploy` block for the **backend** service in `.github/workflows/deploy-staging.yml` and `.github/workflows/deploy-prod.yml`:

```
--set-env-vars "STORE_BACKEND=firestore" \
--set-env-vars "GCS_BUCKET=<actual bucket name>" \
```

and on **staging only**:

```
--set-env-vars "FIRESTORE_PREFIX=staging_" \
```

Leave the prefix empty on prod. Do not touch the frontend deploy steps.

While you are in there: `--set-env-vars "STATE_STORAGE=memory"` is dead config that nothing in the codebase reads. Delete that line from both workflows.

### 5. Deploy to staging and verify

Push, let the workflow run, then confirm against the deployed staging backend that a procurement created through the UI survives a redeploy. That is the whole point of the exercise — do not report success without having seen it.

---

## Out of scope — do not touch

- `backend/graph.py`, `backend/agents.py`, `backend/prompts.py` — the legacy Procurement Analyst pipeline. It has its own separate, unfixed statelessness problem (LangGraph's `MemorySaver` and `backend/uploads/`). It is known, it is deliberate, and it is somebody else's ticket.
- `backend/review/dimensions/` — two developers are actively adding dimension analyzers here. Do not refactor, rename or "tidy" anything in that package.
- `backend/review/schema.py` — **frozen contract** between the two dimension owners and the frontend. Changing a field here breaks both. If you believe it must change, stop and ask.
- Anything under `frontend/`.
- Authentication. There is none; every action is attributed to a hardcoded `"BAC Admin"`. That is a known MVP gap, tracked separately.

---

## Also worth flagging

`backend/env.md` is tracked in git and contains live `TAVILY_API_KEY` and `GAMMA_API_KEY` values. `.gitignore` covers `.env` but not `env.md`. Both keys need rotating, and removing them from HEAD is not sufficient — they are in the history. Raise this with the repository owner; do not attempt a history rewrite yourself.

---

## When you are done, report

1. Which preconditions you found already satisfied, and which you had to chase.
2. Every bug you found in `FirestoreStore`, and how you fixed it.
3. How you made reference-number allocation atomic, and the evidence it holds under concurrency.
4. Confirmation that a staging record survived a redeploy — with the reference number you used.
5. Anything you deliberately left undone.

Do not report a task complete on the strength of the code looking correct. Every claim above needs something you actually ran behind it.
