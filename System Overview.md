# System Overview — DICT Procurement Intelligence Platform

**Status: 2026-09-25** · branch `feature/mark` · supersedes `docs/AI_REVIEW_HANDOFF.md`

This is the single technical orientation document for the system. It is written
to be read start-to-finish by a developer joining the project, or loaded whole
as context by an AI coding assistant working in this repo.

The UI is stable and the plumbing is done. What remains is wiring the AI. If you
are one of the four developers taking that on, read §1–§7 whichever part you
own, then your own brief in §8.

**Read this before writing code:**

| I want to… | Go to |
|---|---|
| Understand what the product does | §1 |
| See the intended UI before changing any screen | §2 — the prototype is authoritative |
| Understand the request flow end to end | §4 |
| Write an AI Review dimension | §6, then §8 |
| Know why there is no login and what that costs us | §7 |
| Run it locally | §9 |

---

## 1. What this system is

An AI-assisted review tool for Philippine government procurement under
**RA 12009** (the New Government Procurement Act), built for the DICT Bids and
Awards Committee.

The BAC creates a procurement record, attaches its pre-award documents (Terms of
Reference, Market Study, Purchase Request, BAC Resolution and so on), and runs an
**AI Review**. The review returns *findings* — each one citing a specific
document and page — which the committee then accepts, modifies, rejects, or sends
for further study. Those decisions flow into a Final Report.

### The moment this tool exists for

**The review is a gate immediately before posting to PhilGEPS.** By that point
the procurement has been planned and its documents drafted — the TOR, the
technical specifications, the market analysis, the chosen mode of procurement.
Once it is posted, it is public and committed. The question the tool answers is:

> *If this is posted today, does it stand up?*

Not "is it complete" in a clerical sense, but **is it legally defensible** —
could the BAC defend the specification, the ABC, and the choice of mode if
challenged, on the strength of the documents in the folder.

That single fact explains most of the design, and it is the thing to hold onto
when a decision seems arbitrary:

- It is why **`source` is mandatory** on every finding. A defence is only as good
  as the document and page it points at.
- It is why findings **never assert illegality** — a legal determination made by
  a tool is not a defence, it is a liability.
- It is why the scope is pre-award, and why the review runs against a *complete
  drafted set* rather than a trickle of documents.
- It is why `compliant` findings matter as much as problems: they are the record
  of what was checked and found sound.

Both rules are enforced in the house rules (§6.5) and the schema (§6.3), and
neither is stylistic — breaking either is a bug, not a matter of taste.

**Scope is pre-award, and narrower than that: pre-posting.** Contracts, payment
records and post-award administration are out of scope. The bidding-stage types
in `domain.DOC_TYPES` (Bidding Documents, Invitation to Bid, Abstract of Bids,
Post-Qualification Report) exist so documents can be filed against the record as
the procurement proceeds — **no review dimension should require them**, because
at the moment of review they do not exist yet.

Note that **Supplier Quotation is a planning document, not a bidding one.** It
is the price canvassing evidence behind the market study and the ABC, gathered
before posting — not a bid received after it. It is grouped with Planning in
`DOC_TYPES` for that reason, and Procurement & Market should read it.

### Review whatever is there

**The review must never require a document set.** Users attach what they have,
and the analysis has to be sound and coherent on exactly that. There is no
readiness gate, no required-documents checklist, and no blocking the run until a
folder is complete — a procurement mid-drafting is a normal input, not an error
state.

What this means in practice for a dimension:

- Read the document types you need if they are present; analyse what is there.
- If none of them are present, say so with `cannot_assess` (§6.4) and stop. That
  is a note recording what fell outside the review, **not** a demand and not a
  failure — the other dimensions still ran and their findings still stand.
- Never degrade another dimension's output because a document you wanted is
  absent. Dimensions are independent by construction (§6.1); keep it that way.

A review of four documents should read as a complete review of four documents,
with an honest margin around what was not covered.

### 1.1 Monorepo layout

```
procurement/
├── System Overview.md          ← you are here
├── html-proto/ai-analyst.html  ← the reference UI prototype (§2)
├── backend/                    FastAPI + LangGraph, Python 3.12
│   ├── server.py               app, CORS, legacy analyst endpoints
│   ├── config.py               settings (pydantic-settings, reads .env)
│   ├── domain.py               Procurement, ProcurementDocument, DOC_TYPES
│   ├── routers/                procurements.py · review_api.py · knowledge.py
│   ├── review/                 ← the AI Review engine (§6)
│   ├── store/                  memory | firestore, plus files.py for GCS
│   ├── utils/                  llm_factory, doc_classifier, storage, gamma
│   ├── agents.py · graph.py    the legacy six-agent pipeline (§5)
│   └── scripts/                check_store.py · upload_knowledge.py
├── frontend/                   Next.js 16 App Router, TypeScript, Tailwind
│   ├── app/(shell)/            items · items/[ref] · analyst · hub
│   ├── components/             procurement-records/ · procurement/ · shell/
│   ├── lib/records-client.ts   client for the records/review/knowledge API
│   └── lib/api-client.ts       client for the legacy analyst chat API
└── docs/                       GCP requirements, storage notes, older docs
```

---

## 2. The reference UI prototype — `html-proto/ai-analyst.html`

**Before you change any screen, open this file in a browser.**

`html-proto/ai-analyst.html` is a single self-contained 2,562-line HTML file — no
build, no server, no dependencies. It is a working click-through of the entire
product with realistic seeded data: several procurement records, 15 sample
findings across all five review dimensions, and a populated Knowledge Hub.

**It is the authoritative UI specification.** The Next.js app is an
implementation of it. When the two disagree, the prototype is right and the
implementation is behind. Do not invent new UI, new layouts or new
terminology — match the prototype. This has already been the source of two
rounds of rework.

Its structure mirrors the app one-to-one:

```js
const state = { page: "items" }   // items | assistant | hub | workspace

// and inside a procurement workspace:
const tabs = [
  ["overview",  "Overview"],
  ["documents", "Documents"],
  ["review",    "AI Review"],
  ["report",    "Final Report"],
  ["forms",     "Form Generator"],
];
```

Useful things to read in it rather than guess at: the finding card with its
severity chip, side-by-side comparison block and BAC action row; the Final Report
layout; the Form Generator picker; and the exact wording used throughout.

---

## 3. The shape of the app

### 3.1 The sidebar panel

`frontend/components/shell/app-sidebar.tsx`, rendered by
`frontend/app/(shell)/layout.tsx` so it persists across every page. Fixed 232px,
navy, three zones:

```
┌──────────────────────────┐
│ [logo] Procurement       │  → links to /items
│        Intelligence      │
│        Platform          │
│                          │
│ WORKSPACE                │  section label
│  ▸ Procurements          │  /items   — records list + workspace
│  ▸ ProcAI                │  /analyst — ad-hoc document chat
│  ▸ Knowledge Hub         │  /hub     — RA 12009, GPPB/COA issuances
│                          │
│ ──────────────────────── │
│ (BA) BAC Admin           │  ← hardcoded. There is no login. See §7.
│      Bids and Awards …   │
└──────────────────────────┘
```

Active state is computed with `pathname === href || pathname.startsWith(href + "/")`,
so `/items/PROC-2026-001` keeps **Procurements** highlighted.

**The footer is not a user menu.** It is a static label. Nothing behind it
identifies anyone — see §7.

### 3.2 The three destinations

| Route | Purpose | Backend |
|---|---|---|
| `/items` | List of procurement records; create new; open one | `routers/procurements.py` |
| `/items/[ref]` | The workspace — five tabs against one record | `procurements.py` + `review_api.py` |
| `/analyst` | ProcAI: upload a PDF, get a quick verdict, chat about it. No record required | `server.py` (legacy path, §5) |
| `/hub` | Read-only library of RA 12009, GPPB and COA issuances | `routers/knowledge.py` |

The two AI paths — the workspace **AI Review** and the **ProcAI** chat — are
separate systems that do not share code or output format. This trips people up
constantly. §5 explains why, and it is Dev D's job to reconcile them.

### 3.3 The workspace tabs

| Tab | Component | State |
|---|---|---|
| Overview | `overview-tab.tsx` | Record metadata, editable; findings summary |
| Documents | `documents-tab.tsx` | Upload, inferred type (editable), download, remove |
| AI Review | `ai-review-tab.tsx`, `finding-card.tsx` | Findings; BAC accept/modify/reject/further; comments |
| Final Report | `final-report-tab.tsx` | Consolidated findings + decisions; print |
| Form Generator | `forms-tab.tsx` | **Shell only — no backend exists** |

---

## 4. The main flow, end to end

This is the path to hold in your head. Everything else is a detail hanging off it.

```
1. CREATE           POST /procurements
   new-procurement-dialog.tsx → title, ABC, Procurement Type
   (Goods | Infrastructure | Consulting Services), Mode (11 options),
   fund source, end user
        → store assigns ref PROC-YYYY-NNN

2. UPLOAD           POST /procurements/{ref}/documents        (multipart)
   documents-tab.tsx
        ├─ save_document()     → gs://{GCS_BUCKET}/procurements/{ref}/{name}
        │                        or ./uploads/{ref}/{name} if no bucket
        ├─ count_pages()       → PyMuPDF
        └─ classify_many()     → utils/doc_classifier.py, concurrent, best-effort
                                 reads first 3 pages, picks one of 16 DOC_TYPES,
                                 falls back to "Other"; never blocks an upload
   The inferred type shows in the Documents table as a dropdown.
   PATCH /procurements/{ref}/documents/{id}  corrects it in one click.

3. REVIEW           POST /procurements/{ref}/review
   routers/review_api.py
        │
        ├─ _build_context()          for each document: read from GCS,
        │                            extract_text() with [page N] markers
        │                            → ReviewContext
        │
        └─ run_review(ctx)           review/runner.py
                 │
                 ├── asyncio, all registered dimensions at once:
                 │     compliance · document_consistency · document_quality
                 │     · procurement_market · requirements_risk
                 │   180s timeout each; one failure never affects the others
                 │
                 ├── stamps finding.dimension  (you cannot mislabel your output)
                 ├── assigns ids AI-01, AI-02, … in registry order
                 └── → ReviewResult

        store.replace_findings(ref, findings)   ⚠ discards prior BAC decisions

4. DECIDE           PATCH /procurements/{ref}/findings/{id}
   finding-card.tsx → accepted | modified | further | rejected, + comments

5. REPORT           GET /procurements/{ref}/findings
   final-report-tab.tsx renders findings + decisions. Already wired correctly;
   adding a dimension needs no report change.

6. FINALIZE         POST /procurements/{ref}/finalize
   Locks the record: no further uploads or edits.
```

**The one thing to internalise:** a dimension is a single function that takes a
`ReviewContext` and returns `list[ReviewFinding]`. That is the entire interface.
Parallelism, timeouts, id assignment, error isolation, persistence and rendering
are already handled. You do not touch them.

---

## 5. The two AI paths (and why there are two)

They are not duplicates of each other, and neither is a stepping stone to the
other. **They answer different questions and the split is deliberate:**

| | **Procurements** (Path A) | **ProcAI** (Path B) |
|---|---|---|
| Question | "Is this procurement sound?" | "What does this document say?" |
| Role | System of record | Fast query tool |
| Input | Documents attached to one procurement entry | Any procurement document, ad hoc |
| Output | Cited findings the BAC acts on | A chat answer |
| Persists? | Yes — findings, decisions, report | No |

**Nothing in Path A is independent of a procurement entry**, because nothing in
procurement is. Every document exists in service of one procurement, which has
its own lifecycle from planning through award. That is why documents attach to a
`ref` rather than standing alone, why findings are keyed to a `ref`, and why
there is no "review a loose file" path in the records section. Do not add one.

Path B exists precisely so that the ad-hoc need has somewhere to go that is not
the record. It is for reading and asking — not for assessing. Anything that
should end up in a report belongs in a procurement entry.

**Path A — AI Review** (`backend/review/`). The current architecture. Five
dimensions over the documents attached to a procurement record, producing
`ReviewFinding` objects with source citations. Everything in §6 is about this.

**Path B — the legacy six-agent pipeline** (`backend/agents.py`, `graph.py`). The
original system: a LangGraph fan-out of six agents (Specification Validator,
LCCA, Market Researcher, Sustainability, Tatak Pinoy, Modality Advisor) with a
compiler and a human-in-the-loop interrupt. It still runs, and it still serves
the **ProcAI** chat page via `POST /analyze`, `GET /stream/{thread_id}`,
`POST /review`, `POST /chat`.

**Note the mismatch between what it does and what ProcAI is for.** A fast query
tool does not need a PASS/FAIL verdict, a confidence score, or a generated slide
deck — those are assessment outputs, and assessment belongs to Path A. The
pipeline predates the split and still carries all three. The chat is the part
that matches the intended role; the verdict, the human-in-the-loop interrupt and
the Gamma generation are leftovers. See Dev D (§8.4) and open decision 2.

They produce incompatible shapes:

```ts
// Legacy. Severity is high|medium|low, findings are grouped into categories of
// bare strings, and there is NO source citation anywhere.
interface VerdictData {
  status: 'PASS' | 'FAIL';
  title: string;
  findings: { category: string; items: string[]; severity: 'high'|'medium'|'low' }[];
  confidence: number;
}
```

Nothing in Path B reads the dimension registry. `compiler_agent`
(`agents.py:524`) builds `VerdictData`; `gamma_generator_node` (`agents.py:633`)
turns it into a Gamma slide deck. Reconciling the two — adapter or retirement —
is Dev D's second job (§8.4), and retirement is a live option.

---

## 6. The AI Review engine

### 6.1 Module map

| File | Responsibility | Do you edit it? |
|---|---|---|
| `review/schema.py` | The finding contract | **Frozen.** No. |
| `review/registry.py` | `@register` decorator, dimension order | No |
| `review/runner.py` | Parallel execution, timeouts, ids, isolation | No |
| `review/context.py` | `ReviewContext`, `ReviewDocument`, selection helpers | No |
| `review/llm.py` | `analyze(prompt, dimension)` | No |
| `review/parsing.py` | `FINDING_JSON_CONTRACT`, response parsing | No |
| `review/gaps.py` | `cannot_assess()` | No |
| `review/dimensions/*.py` | **One file per dimension** | **Yes — only yours** |

Adding a dimension touches exactly one shared file,
`review/dimensions/__init__.py`, to import your module so the decorator runs —
and all five are already listed there, so in practice **you edit one file, your
own.** The module boundary *is* the coordination mechanism; devs A, B and C
should never need to negotiate a merge.

If you find yourself editing `runner.py`, `registry.py`, `schema.py` or
`review_api.py`, stop and raise it. That is a design conversation, not a task.

### 6.2 A dimension, in full

```python
from prompts import RA_12009_DIRECTIVE
from review.context import ReviewContext, render
from review.gaps import cannot_assess
from review.llm import analyze
from review.parsing import FINDING_JSON_CONTRACT
from review.registry import register
from review.schema import ReviewFinding

DIMENSION = "document_quality"
READS = ("Terms of Reference (TOR)", "Technical Specifications")

@register(key=DIMENSION, label="Document Quality",
          blurb="Structure, clarity and completeness of the TOR and specs.",
          owner="Mark")
def run(ctx: ReviewContext) -> list[ReviewFinding]:
    targets = ctx.of_types(*READS)
    if not targets:
        return cannot_assess(DIMENSION, READS, [d.doc_type for d in ctx.documents])

    prompt = PROMPT.format(
        ra_12009_directive=RA_12009_DIRECTIVE,
        json_contract=FINDING_JSON_CONTRACT,
        documents=render(targets),
    )
    return analyze(prompt, DIMENSION)
```

`review/dimensions/document_quality.py` is the worked example and the only
implemented dimension. Copy its shape.

### 6.3 The contract — `review/schema.py`

**This file is frozen.** Changing a field breaks four developers and the frontend
at once. Changes go through Mark and get announced, not committed quietly.

```python
class ReviewFinding(BaseModel):
    id: str = ""              # leave empty — the runner assigns it
    dimension: str            # leave empty — the runner stamps it
    severity: Literal["critical", "medium", "low", "info", "compliant"]
    title: str                # one neutral sentence
    analysis: str             # what you observed and why it matters
    recommendation: str = ""  # what the BAC should do; omit when compliant
    source: Source            # REQUIRED — doc, optional page, section
    policy_basis: str = ""    # "RA 12009 IRR", a GPPB/COA issuance, DICT policy
    quote: str = ""           # verbatim cited text, single-passage findings
    comparison: list[ComparedText] = []   # 2+ entries for cross-document findings
    delta: str | None = None  # plain summary: "Differs by ₱600,000.00"
```

Two rules people get wrong:

- **`source` is required.** A finding the committee cannot trace back to a
  document and page is not usable. If the model will not cite, drop the finding.
- **`quote` XOR `comparison`.** `quote` for a single passage; `comparison` (plus
  `delta`) when two documents disagree — the UI renders those side by side. Never
  both.

| Severity | UI label | Meaning |
|---|---|---|
| `critical` | Critical | Potentially material issue requiring prompt BAC attention |
| `medium` | Medium | Meaningful issue but generally does not by itself prevent continuation |
| `low` | Low | Minor quality or completeness issue |
| `info` | Informational | Observation rather than an identified deficiency |
| `compliant` | Compliant | Checked and no issue found |

Do not retype these meanings in your prompt. `SEVERITY_MEANING`
(`review/schema.py:21`) is the single source: the prompt contract renders it for
the model and `status-pill.tsx` renders it for the BAC, so the level means the
same thing to both. Note the level says how much attention something wants — it
never says anything is unlawful.

An older three-level scale (`high`/`warning`) is coerced on load via
`LEGACY_SEVERITY` (`schema.py:31`) so records reviewed before the change still
render. Don't emit those values in new code.

Emit `compliant` findings deliberately. A review that returns only problems tells
the committee nothing about what was actually examined.

### 6.4 Document types, and what to do when yours is missing

Nobody picks a document type on upload. `utils/doc_classifier.py` reads the first
three pages and picks one of the 16 types in `domain.DOC_TYPES` (Planning /
Requirements / Bidding / BAC action, plus `Other`). The Documents tab shows the
result in a dropdown so the BAC can correct it. Anything the classifier cannot
place confidently becomes `"Other"` — it is built to under-claim rather than
guess.

So `doc.doc_type` is a good hint, not a guarantee:

- **Select with `ctx.of_types(...)`**, not a hand-rolled comprehension.
  `ctx.document(name)`, `ctx.by_type(one)` and `ctx.combined_text` are also
  available, and `render(docs)` turns a subset into prompt text.
- **Never `return []` because nothing matched.** To the BAC an empty dimension is
  indistinguishable from a clean one, and a missing document is itself something
  RA 12009 expects the committee to notice. `cannot_assess()` returns one warning
  naming what you needed and what was actually attached.

An empty list is reserved for exactly one meaning: *I read the documents and
found nothing to report.*

### 6.5 House rules — these are not style preferences

They come from the domain and from prior review. Breaking them is a bug.

- Never state that something **is illegal, non-compliant, or a violation.** Write
  "potential issue", "requires BAC review", "suggested action".
- A specification that looks written around one product is *"a potential concern
  requiring BAC review"* — never *"restrictive"* or *"rigged"*.
- **Never surface the machinery**: no "LangGraph", "LLM", "agent", "RAG",
  "embedding", "vector", "chunk", "retrieval", "prompt", "token", no model names.
  The UI says "AI Review". That is the whole vocabulary.
- Never label anything an **"AI Decision"**. The AI raises findings; the BAC decides.

**The prompt contract is centralised.** Paste `FINDING_JSON_CONTRACT` from
`review/parsing.py` into your prompt rather than describing the JSON yourself. It
already encodes the page-marker rule, the quote-verbatim rule and the
never-say-illegal rule. **Every prompt also includes `RA_12009_DIRECTIVE`** from
`backend/prompts.py`.

---

## 7. Session management and isolation — there is no RBAC

This section is about what the system actually does today, not what it should do.
Every claim below is verified against the source.

**Read it in context: this build is an MVP demonstrator.** Its job is to show the
BAC how the review flow works, on pilot documents, to people in the room. A
single shared workspace is an acceptable — arguably correct — shape for that.
The section is here so nobody mistakes a demonstrator for a deployable system,
and so the one constraint that follows from it (§7.5) is impossible to miss.

### 7.1 There is no authentication at all

No login, no session cookie, no bearer token, no API key, no `Depends()` security
dependency on any endpoint. Both Cloud Run services deploy with
`--allow-unauthenticated` (`backend/deploy-backend.sh:17`).

Every action is attributed to a hardcoded string:

- `routers/procurements.py:32` — `ACTOR = "BAC Admin"` → `finalized_by`
- `routers/review_api.py:25` — `ACTOR = "BAC Admin"` → `decided_by`, comment `author`
- `review/schema.py:80` — `Comment.author` defaults to `"BAC Admin"`
- The sidebar footer renders the same string as static text.

**CORS is not access control.** The allowlist in `server.py:54-67` only
constrains browser JavaScript from other origins. `curl`, a script, or any
server-side caller reaches every endpoint unimpeded.

### 7.2 Two paths, two different isolation models

**Path A — procurement records: no isolation whatsoever.**

- `store/__init__.py:17` — `@lru_cache(maxsize=1)` on `get_store()`. One store
  object per process, shared by every request from every browser.
- Neither `Procurement` (`domain.py:62`) nor `StoredFinding` (`review/schema.py:84`)
  has an `owner`, `user`, `created_by` or `tenant` field. (`end_user` is the
  requesting office — a business attribute, not an identity.)
- `GET /procurements` returns everything, unfiltered. Every handler resolves
  purely by `ref`.
- Refs are sequential — `PROC-2026-001`, `-002`, `-003` — and therefore trivially
  enumerable. `FIRESTORE_PREFIX` separates staging from prod, not user from user.

**Path B — the ProcAI analyst: isolated by unguessable capability.**

- `utils/storage.py:143` — `generate_thread_id()` returns a `uuid4`. Returned to
  the caller by `/analyze` and used as the handle for `/stream`, `/chat`,
  `/review`, `/status`.
- Uploads go to `./uploads/{thread_id}/`; path traversal is correctly blocked by
  a UUID-format check.
- **But the only check on those endpoints is "does this thread exist".** There is
  no owner check. Anyone who obtains a thread_id has full access to that
  session's document text, verdict and chat — and can trigger the paid Gamma
  generation. The protection is the unguessability of the UUID, nothing more.
- The browser keeps the thread_id in `useRef` only
  (`use-procurement-analysis.ts:58`) — no localStorage, sessionStorage, cookie or
  URL param anywhere in first-party code. **A page refresh loses the conversation
  permanently**; the backend state survives but there is no resume-by-id UI.
- The checkpointer is `MemorySaver()` (`graph.py:77`) — a module-level in-memory
  dict. `STATE_STORAGE` in config is accepted but unimplemented.

### 7.3 Summary

This table is what the code does **today**, and no work is in flight to change
it — see §7.6 for why that is deliberate.

| | Isolated? | By what |
|---|---|---|
| Analyst chat sessions from each other | **Yes** | unguessable `uuid4`, a capability not an identity |
| Analyst upload directories | **Yes** | `uploads/{uuid4}/`, traversal blocked |
| Staging vs prod data | **Yes** | `FIRESTORE_PREFIX` |
| Review dimensions from each other's failures | Yes | fault isolation, not data isolation |
| Procurement records, documents, findings | **No** | one global dataset |
| Decisions, comments, finalize actions | **No** | one global dataset |
| Who did what (audit trail) | **No** | everything is `"BAC Admin"` |

### 7.4 What this means in practice

1. **Two BAC staff share one workspace.** Officer A's in-progress record appears
   immediately in Officer B's list. B can edit it, upload to it, re-run its
   review (destroying A's recorded decisions), or hard-delete it *and its stored
   files*. Nothing warns anyone and nothing records who did it.
2. **The audit trail cannot establish accountability.** A finalized procurement
   says `finalized_by: "BAC Admin"`. For a government procurement record that is
   a real deficiency, not a cosmetic one.
3. **Last write wins.** `FirestoreStore.save_procurement` is a blind full-document
   `set()` with no optimistic concurrency. Two officers editing one record will
   silently clobber each other.
4. **Sequential refs + no auth + a public URL** means the whole dataset, including
   the attached PDFs, is readable by anyone who finds the backend URL.
5. **Analyst sessions break under multi-instance traffic.** `MemorySaver` and the
   `uploads/` directory are instance-local. `deploy-backend.sh` allows 10
   instances, which would 404 unpredictably; the system holds together only
   because `deploy-backend-simple.sh` pins it to one always-on instance — and
   that instance loses every analyst session on redeploy.
6. **No rate limiting anywhere.** Four unauthenticated LLM endpoints, the most
   expensive being `/procurements/{ref}/review`, which fans out to five parallel
   calls over full document text and can be looped by anyone.

### 7.5 The rule this imposes

> **This system must not hold live procurement data until sign-in exists.**
> Pilot and test data only.

Treat that as a hard constraint on every demo and deployment decision. Note also
that `allow_credentials=True` is already set with `http://localhost:3000` on the
allowlist — a latent footgun the moment a cookie is introduced.

### 7.6 Why there is no interim isolation

**The intended end state is Google sign-in restricted to `@dict.gov.ph`.** Access
is a property of holding a DICT government mail account; identity is the user's
email address.

Interim schemes that isolate without a login — a per-browser key in
`localStorage`, a name picker — have been **considered and rejected**, and that
decision should hold:

- They isolate *browsers*, not people. One person on two machines gets two
  disjoint workspaces; clearing site data destroys access permanently.
- They replace `"BAC Admin"` with an opaque token. For a government procurement
  record, an unattributable uuid in `finalized_by` is worse than an honest
  placeholder.
- They do not lift §7.5, so the pilot-data-only rule binds either way.
- Most decisively: **it is throwaway work that has to be unpicked.** Records
  owned by browser uuids do not map onto email-owned records, so the migration
  is a manual reassignment of every record by asking people which ones were
  theirs. Domain-restricted sign-in makes the interim layer not just redundant
  but an obstacle.

So the sequence is: demonstrate on a shared workspace now, add real identity
once, migrate nothing.

**What that work looks like when it is scheduled:** Google Identity Services on
the frontend, ID-token verification on the backend with an `hd` / domain check;
an `owner` field on `Procurement` holding the email, with filtering pushed into
the store layer rather than the routers; both `ACTOR` constants replaced by the
authenticated principal; **404 not 403** on an owner mismatch, since sequential
refs make a 403 an existence oracle; per-record authorisation on the document
download endpoints; and optimistic concurrency on `save_procurement`.

Resolve identity in exactly one FastAPI dependency. That is the single piece of
structure worth putting in early, because everything above depends on its shape
and nothing depends on where it gets its answer.

## 8. What each developer needs to do

| Dev | Scope | Files |
|---|---|---|
| **A** | Compliance · Document Consistency | `dimensions/compliance.py`, `dimensions/document_consistency.py` |
| **B** | Procurement & Market | `dimensions/procurement_market.py` |
| **C** | Requirements & Risk · harden Document Quality | `dimensions/requirements_risk.py`, `dimensions/document_quality.py` |
| **D** | Final Report · Form Generator · legacy adapter | `forms-tab.tsx`, new `routers/forms.py`, adapter |

Devs A, B and C never touch the same file. Dev D never touches a dimension.
Update the `owner=` string in your `@register(...)` call — the frontend surfaces
it via `GET /review/dimensions`.

> **On the B/C split:** the original ask was two developers across Document
> Quality, Procurement & Market and Requirements & Risk. Document Quality is
> already implemented, so the genuinely open work is two dimensions, not three.
> B takes Procurement & Market alone because it is the largest — two legacy
> agents, an optional external search, and the most judgement-heavy findings.
> C takes Requirements & Risk plus ownership of Document Quality. Rebalance if
> that proves wrong after a week.

### 8.1 Dev A — Compliance · Document Consistency

**Compliance** (`dimensions/compliance.py`). Replaces `modality_advisor_agent`
and `domestic_preference_agent`. Legacy prompts to mine:
`COMPLIANCE_MODALITY_PROMPT` (`prompts.py:173`), `TATAK_PINOY_PROMPT`
(`prompts.py:139`).

Cover: correct procurement modality for the ABC and subject matter under RA 12009
and its IRR; documentary completeness for the chosen modality; applicable GPPB and
COA issuances; domestic preference / Tatak Pinoy.

`ctx.meta` carries `title`, `abc`, `mode`, `category`. **Read the mode off
`ctx.meta["mode"]`; do not infer it from the documents.** The eleven valid modes
are in `frontend/types/records.ts:PROCUREMENT_MODES`.

**Document Consistency** (`dimensions/document_consistency.py`). No legacy
equivalent — you build it from nothing, which also means no legacy prompt to
inherit bad habits from.

Compare figures, dates, quantities, unit prices, delivery periods and defined
terms **across** documents: TOR vs Purchase Request vs Market Study vs BAC
Resolution. Almost every finding here should populate `comparison` with one
`ComparedText` per document plus a `delta` in plain words. This is the dimension
the side-by-side UI was built for — if you are returning bare `quote` findings,
you are probably in the wrong dimension.

Watch prompt size: `ctx.combined_text` across six documents is large. Prefer
pulling specific documents and comparing pairs.

**Done when:** both return real findings with correct `source` citations on the
pilot set; a malformed model response fails the dimension loudly rather than
returning `[]`; the other four still pass.

### 8.2 Dev B — Procurement & Market

`dimensions/procurement_market.py`. Replaces `market_scoping_agent` and
`lcca_agent`. Legacy prompts: `MARKET_SCOPING_PROMPT` (`prompts.py:71`),
`LCCA_PROMPT` (`prompts.py:39`).

Cover: whether specifications are open enough to attract real competition;
whether the ABC is consistent with the described market; lifecycle cost
considerations; dependencies on an incumbent system or vendor.

**Two constraints specific to you:**

1. **`TAVILY_API_KEY` is not set locally and the key in the repo needs rotating**
   (§10). Your `run()` **must work without external search.** Treat Tavily as
   optional enrichment behind a config check, never a hard dependency — otherwise
   the dimension fails for everyone who lacks the key.
2. **This dimension carries the most reputational risk.** A finding that says a
   specification is restrictive is in effect an accusation. Phrase every one as an
   observation to verify: *"The specification names a single product family; the
   BAC may wish to confirm that equivalent products were considered."* Never *"the
   specification is tailored to Vendor X."*

**Done when:** produces findings with and without a Tavily key; ABC findings cite
the figure compared against; no finding asserts restriction as fact.

### 8.3 Dev C — Requirements & Risk · Document Quality

**Requirements & Risk** (`dimensions/requirements_risk.py`). Replaces
`sustainability_agent`. Legacy prompt: `GREEN_SUSTAINABLE_PROMPT`
(`prompts.py:107`) — lifecycle and sustainability requirements belong here, not in
Procurement & Market.

Cover: deliverables defined and measurable; warranty and support terms; payment
milestones and conditions; contract obligations and termination; risk allocation
between agency and supplier; sustainability and lifecycle requirements.

**Document Quality** — already implemented; you inherit it. It is the worked
example the other four were written against, so treat changes as changes to a
reference: keep the shape, improve the substance. Open gap: **it has no test
against a real TOR. Build the fixture the others can copy.**

**Done when:** Requirements & Risk returns real findings; both stay within the
180s timeout; a reusable TOR fixture exists.

### 8.4 Dev D — Final Report · Form Generator · legacy adapter

You own the output end. Three pieces, in priority order.

**(a) Form Generator — build it.** `forms-tab.tsx` lists six target forms
(Invitation to Bid, Bid Data Sheet, BAC Resolution, Notice of Award,
Post-Qualification Checklist, Abstract of Bids) with nothing behind them. The
button calls `toast.info("Form generation is not available yet")`.

You need `routers/forms.py`, a template per form, prefill from the `Procurement`
record, and a download. Follow the download endpoints in `routers/procurements.py`
for shape.

Settle this early because it changes the design: **templated fill-ins or
LLM-drafted?** The GPPB standard forms are prescribed documents — a model
inventing clause text in an Invitation to Bid is a liability. Recommendation:
deterministic templates with record-derived prefill, and the model only for
genuinely narrative sections, clearly marked as draft.

**(b) Final Report — already consuming review output; extend it.** In order of
value:

- **Surface dimensions that failed or timed out.** Right now a crashed dimension
  is indistinguishable from one that found nothing, in the one document the
  committee actually relies on. `RunReviewResponse.dimensions[]` carries `status`
  and `error`; the report ignores both. This is the most important item on your list.
- Group findings by dimension with section headings instead of one flat list.
  Read the list from `GET /review/dimensions`; never hardcode it.
- Server-side PDF export (`window.print()` is the current mechanism).

**(c) The legacy adapter.** Two report systems exist and do not speak to each
other (§5). Write a `ReviewFinding[] → VerdictData` adapter so
`report-preview.tsx` and `verdict-card.tsx` survive the migration. The mapping is
lossy and you will have to make calls:

| `ReviewFinding` | `VerdictData` | Note |
|---|---|---|
| `severity: critical/warning/compliant` | `severity: high/medium/low` | Not clean; `compliant` has no target |
| `dimension` | `findings[].category` | Use the registry `label`, not the key |
| `title` + `analysis` | `findings[].items: string[]` | Structure collapses to strings |
| `source`, `quote`, `comparison`, `delta`, `policy_basis` | — | **Lost entirely** |
| — | `status: PASS/FAIL` | Derive. Propose: FAIL if any `critical` |
| — | `confidence: number` | No equivalent. Do not fabricate one |

Flag early if you conclude the legacy path should be retired rather than adapted.
That is a real option and arguably the right one — a question for Mark, not a
decision to make inside a PR.

**Done when:** the Form Generator produces at least one downloadable form; the
Final Report groups by dimension and shows failed dimensions; the adapter has a
test with a fixture of each severity.

---

## 9. Local setup

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then set your LLM key

# Windows: if GOOGLE_APPLICATION_CREDENTIALS is set machine-wide it overrides
# your gcloud login and GCS calls fail with 403. Start with:
env -u GOOGLE_APPLICATION_CREDENTIALS uvicorn server:app --reload

# Frontend
cd frontend && npm install && npm run dev          # Turbopack, port 3000
```

**The defaults in `.env.example` need no GCP resources and no credentials.**
`STORE_BACKEND=memory` (records vanish on restart — fine for dimension work) and
`GCS_BUCKET=` empty (files go to local disk). Nothing you do locally can reach
shared data unless you deliberately change those.

For persistence, use the Firestore emulator rather than a real database:

```bash
gcloud emulators firestore start --host-port=127.0.0.1:8098
# then in .env:  STORE_BACKEND=firestore  FIRESTORE_EMULATOR_HOST=127.0.0.1:8098
```

`backend/scripts/check_store.py` exercises all 36 store behaviours against either
backend. Run it if you touch storage.

### 9.1 The dev loop — run one dimension at a time

```bash
curl -X POST "http://localhost:8000/procurements/PROC-2026-001/review?keys=compliance"
```

Use this constantly. A full review is five parallel model calls and up to 180s.
Repeat the parameter for several: `?keys=compliance&keys=document_quality`.

### 9.2 Definition of done, for any dimension

1. `run(ctx)` returns real `ReviewFinding` objects on the pilot documents.
2. Every finding has a `source` pointing at a real document and, where placeable,
   a real page.
3. `quote` text is verbatim — copy-pasteable back into the source PDF.
4. No finding asserts illegality or non-compliance.
5. At least one `compliant` finding when the documents are sound.
6. A malformed model response **raises**, so the runner marks the dimension
   failed. **Returning `[]` on error is the one thing you must not do** — it is
   indistinguishable from a clean review and it is how a broken dimension ships
   unnoticed.
7. The other four dimensions still pass with your change applied.
8. Completes within the 180s timeout.

---

## 10. Known risks — read before you commit anything

**Secrets.** `backend/env.md` was a tracked `.env` in disguise containing live
`TAVILY_API_KEY` and `GAMMA_API_KEY`. It has been untracked and gitignored, **but
the keys remain in git history and still need rotating.** Do not attempt a
history rewrite without the repository owner.

**No authentication.** See §7. Pilot data only.

**Re-running a review destroys BAC decisions.** `POST /procurements/{ref}/review`
calls `store.replace_findings()`, deleting every existing finding including the
committee's recorded actions and comments. The only warning is the button reading
"Run AI Review again". Unowned; raise it if it affects your work.

**Do not create or download a service-account key JSON.** Local GCP access uses
ADC (`gcloud auth application-default login`) or the emulator.

**Cloud Run is not ready for GCS.** Do not set `GCS_BUCKET` in the Cloud Run
environment until `roles/storage.objectAdmin` on `proc-ai-staging-files` is granted to
`623960795683-compute@developer.gserviceaccount.com`. Local dev is unaffected.

**Firestore.** One named database per application. Never point at `(default)` or
`procurement-agent-db` — neither is ours, and this store batch-deletes and seeds
on startup. A guardrail in `store/__init__.py` refuses to start without
`FIRESTORE_DATABASE` outside the emulator.

**Next 16 on React 18.3** is an unsupported combination; Next 16 targets React 19.
Worth scheduling an upgrade.

---

## 11. Open decisions

Not assigned. Each needs a call before the work it blocks.

1. **Form Generator: templated or LLM-drafted?** — blocks Dev D(a).
2. **Reduce the legacy path to chat, or adapt its verdict?** Now that ProcAI's
   role is settled as a query tool (§5), the verdict / interrupt / Gamma stages
   look like scope that belongs to Path A. Cutting them is probably simpler than
   writing the adapter. Blocks Dev D(c).
3. **Re-running a review discards BAC decisions.** Acceptable, or does it need
   versioning? Related: `replace_findings` replaces *all* findings on a record,
   so a `?keys=` filtered run wipes the dimensions that did not run. Harmless as
   a dev tool, unshippable as a feature — see §9.1.
4. *(Resolved — kept for the record.)* Whether to define a required pre-posting
   document set and gate the review on it. **No.** The review runs on whatever
   is attached and must stay coherent on a partial set; see "Review whatever is
   there" in §1. Each dimension declares its own `READS` and reports its own gap
   through `cannot_assess`. Do not reintroduce a completeness gate.
5. **When does `@dict.gov.ph` sign-in land?** The target is settled and interim
   half-measures are ruled out (§7.6), so the only open question is timing — and
   until it ships the no-live-data rule binds (§7.5). Unassigned; it needs a
   date, because it gates the pilot rather than following it.
6. **`docs/CLAUDE.md` is not at the repo root**, so Claude Code does not load it as
   project instructions. `docs/System_Overview_For_Non_Technical_Users.md` still
   describes the six original agents and is now wrong — it needs rewriting against
   the five dimensions or removing.
