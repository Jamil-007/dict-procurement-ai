# Procurement AI — Compliance & Data-Integrity Prototype

What was built, how to run it, and how each of the six assigned features maps onto it.

---

## 1. The short version

The six assigned tasks were built as **two engines driven by six YAML configurations**, sitting on a
shared document-reading layer. No task got its own bespoke pipeline — they share everything except
their configuration file.

| # | Task | Owner | Engine | Configuration file |
|---|------|-------|--------|--------------------|
| T1 | Payment Document & DV Checker | Jerald | Rule | `backend/rules/packs/dv_payment.yaml` |
| T2 | AI Procurement Compliance Checker | Michelle | Rule | `backend/rules/packs/ra12009_planning.yaml` |
| T3 | Procurement Doc Review & Compliance Engine | OUPCO | Rule | `backend/rules/packs/completeness_by_doctype.yaml` |
| T4 | Contract-to-Payment Consistency Checker | PCMD | Consistency | `backend/consistency/profiles/contract_to_payment.yaml` |
| T5 | Automated Document & Data Cross-Checker | PCMD | Consistency | `backend/consistency/profiles/delivery_acceptance.yaml` |
| T6 | Inconsistencies across MS/TOR/DCB/Bidding Docs | Jen L. | Consistency | `backend/consistency/profiles/planning_alignment.yaml` |

Current size: **64 rules** across the three rulepacks, **31 cross-document comparisons** across the
three profiles, **2,039 indexed passages** from **18 legal documents**, **45 labelled test fixtures**,
**143 automated tests**.

---

## 2. Why the original app could not do this

Three findings from reading the existing code and the real documents in `docs/`:

1. **Every real DICT transaction document is a scanned image.** PR, TOR, Market Research, DCB,
   Bidding Docs, APP, SBB, Delivery Receipt, PAR, Technical Inspection Report, Tax Receipt,
   Contract Agreement, NOA — all return **zero characters** of text. The old `extract_text_from_pdf()`
   returned an empty string for every document the prototype needs to demo. (The legal corpus —
   RA 12009, its IRR, GPPB manuals, COA circulars, GAM — *is* text-extractable.)
2. **Four of the six tasks are cross-document comparisons.** The old pipeline concatenated every
   upload into one text blob, which destroys per-document identity. "Does the contract quantity
   match the delivery receipt quantity" is unanswerable once both are in the same string.
3. **Two tasks require citing specific legal sections**, and an unaided language model invents
   plausible-looking section numbers.

---

## 3. How a document now moves through the system

```
upload (up to 50 files: PDF, Word, Excel, text)
  ↓
INGEST      probe the text layer; if the page is a scan, render it and read it with
            Claude vision. Results cached on disk by file hash.
  ↓
CLASSIFY    decide what each file is (DV, PR, TOR, delivery receipt, PAR, …)
  ↓
EXTRACT     pull a canonical fact record out of each file: parties, amounts, line
            items with serial numbers, signatories, dates — each with a page anchor
  ↓
ROUTE       look at what was detected and pick which checkers to run
  ↓
  ├── Rule engine ─────────── T1, T2, T3
  ├── Consistency engine ──── T4, T5, T6
  └── Planning advisory ───── the original 6 agents (planning documents only)
  ↓
CITE        look up the governing provision in the indexed legal corpus
  ↓
COMPILE     verdict + findings grouped by category, each with evidence and authority
  ↓
ARCHIVE     saved to SQLite; reopenable from the "Past Reviews" panel
```

**The keystone:** every checker reads the canonical fact record, never raw text. That is the single
design decision that lets six features share two engines.

---

## 4. What each part does, and where it lives

### 4.1 Reading scanned documents — `backend/ingest/`

| File | What it does |
|------|--------------|
| `ocr.py` | Renders each page at 150 dpi and reads it with Claude vision, preserving tables, signature blocks, stamps and handwriting. Capped at 40 pages per document (`OCR_MAX_PAGES`), with keyword-targeted page selection for long bidding documents; pages that were skipped are recorded on the fact record so the report can say so. |
| `cache.py` | Keyed on the file's SHA-256 plus the dpi and prompt version. Without this the 62-page Bidding Documents would be re-read on every run. Cache lives in `backend/cache/ocr/`. |
| `loaders.py` | Word and Excel readers, for the `.docx`/`.xlsx` assets (PPMP, APP, readiness checklist, RFQ template) that T3 needs. |

`load_document()` is the single front door: text layer → OCR → Word/Excel, chosen automatically.

### 4.2 Canonical facts — `backend/facts/`

| File | What it does |
|------|--------------|
| `schema.py` | The record every checker reads: document type and number, project title, contract/PR/PO numbers, supplier, payee, amounts (ABC, gross, tax, retention, net), line items (description, qty, unit price, amount, brand/model, serial numbers), signatories (role, name, signed, date), dates, referenced attachments. Every value carries the page it came from. |
| `classify.py` | Decides the document type from the first two pages only — cheap, and enough. |
| `extract.py` | Per-type extraction with schema validation and one retry. |

### 4.3 Legal citations — `backend/kb/`

`build_index.py` chunks the text-extractable legal PDFs by section heading; `retriever.py` searches
them with BM25 (no vector database, no embedding cost). **Citations are retrieved, never written by
the model.** When a named provision is not in the index, the finding is marked `unverified` and the
interface says so in plain words rather than implying the citation was checked.

### 4.4 Rule engine — `backend/rules/` → T1, T2, T3

Rules are data, not code:

```yaml
- id: dv.amount_words_matches_figures
  applies_to: [disbursement_voucher]
  severity: high
  check: cross_field_equal
  params: {a: amounts.net, b: amount_in_words_parsed}
  authority: {doc: "GAM Volume I", section: "Chapter 8"}
```

The check primitives are deterministic Python: `field_present`, `signatory_present`,
`signatory_order`, `arithmetic_sum`, `cross_field_equal`, `date_order`, `attachment_present`,
`threshold_compare`, plus `llm_judgment` for the genuinely qualitative rules (restrictive
specification language, for instance).

**Adding a rule does not require a developer** — it is a few lines of YAML.

- **T1 `dv_payment.yaml` (17 rules)** — required DV fields, signatory matrix and order, date
  sequencing (delivery ≤ inspection ≤ acceptance ≤ DV), arithmetic (gross − tax − retention = net),
  and the attachment checklist from COA Circular 2023-004.
- **T2 `ra12009_planning.yaml` (17 rules)** — missing or inconsistent provisions, cited to
  RA 12009 / the IRR / GPPB issuances / COA.
- **T3 `completeness_by_doctype.yaml` (30 rules)** — a per-document-type completeness checklist, so
  *any* uploaded type gets a meaningful review rather than nothing.

### 4.5 Consistency engine — `backend/consistency/` → T4, T5, T6

```yaml
id: contract_to_payment
left:  [contract, bidding_docs]
right: [disbursement_voucher, delivery_receipt, iar, par]
compare:
  - {field: contract_no,   match: normalized_exact, severity: high}
  - {field: items[].qty,   match: exact,            severity: high, action_hint: variation_order}
  - {field: amounts.total, match: numeric_tolerance, tolerance: 0.01, severity: high}
```

**The diffing is deterministic Python**, not a prompt: exact, normalised, fuzzy, numeric tolerance,
date window, and serial-number set comparison. Line items are aligned by fuzzy description match
before their attributes are compared. The model is used only to explain materiality and to classify
the required remedy — **Amendment to Order** (IRR §71.1.1, goods) versus **Variation Order**
(IRR §71.2.1 with COA 2009-001 Annex B, infrastructure). Asking a model to "find the discrepancies"
across a hundred scanned pages is precisely the failure this avoids.

- **T4 `contract_to_payment.yaml`** — 10 comparisons.
- **T5 `delivery_acceptance.yaml`** — 9 comparisons across DR / IAR / PAR / ICS / warranty:
  serial numbers, descriptions, quantities, dates, contract numbers, recipients.
- **T6 `planning_alignment.yaml`** — 12 comparisons across Market Study / TOR / DCB / Bidding Docs:
  specifications, quantities, timelines, eligibility, deliverables.

### 4.6 The router — `backend/pipeline.py`, `backend/graph.py`

The old fixed six-way fan-out was replaced with `ingest → classify → extract → route → checkers →
compile`. The router inspects the detected document types and runs only what applies: a payment
packet runs the rule and consistency engines and skips the planning advisory entirely; a planning
packet runs all eight. Every path reaches the compiler, so a verdict is always produced.

**Nothing regressed** — the original six planning agents are preserved and still fire for planning
documents.

### 4.7 The verdict

The compiler reports three things that the previous version could not:

- **How much was actually checked.** "No findings" over 3 checks and "no findings" over 169 checks
  are not the same result. The verdict now carries the count of checks run, passed, flagged, and
  not verified.
- **Checks that could not run** are reported separately as "Not Verified" — never silently counted
  as compliant.
- **Which documents were reviewed**, with the detected type and confidence for each, so a
  misclassification is visible rather than mysterious.

### 4.8 Persistence and archive — `backend/persistence/`

Analyses survive a backend restart. Three tables — `sessions`, `documents`, `findings` — plus
LangGraph checkpoints, all in SQLite. Every check result is stored, including the passes: the row
count is the evidence of how much was examined. Reopening a review shows only what needs attention;
the full trail stays in the database.

Endpoints: `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`.

### 4.9 Upload limits

The three-file cap is gone. Up to **50 files** per upload (a payment packet is ten or more
documents, and comparing a contract against a voucher requires both in the same upload), with
PDF, Word, Excel and text all accepted, and per-extension content verification on the server.

### 4.10 The interface — `frontend/`

- **Documents Reviewed** card: every uploaded file with its detected type, match confidence, pages
  read, and whether it had to be read by OCR.
- **Findings**: each one carries the sentence, the evidence chips (document + page), the legal
  citation as an expandable chip showing the verbatim provision text, the required-action badge
  (Amendment to Order vs Variation Order), and — for cross-document findings — a side-by-side table
  showing what each document said.
- **Unverified citations** are shown in amber with an explicit note, not as ordinary citations.
- **Past Reviews** panel (top-left): every archived analysis, reopenable and deletable.
- **Downloadable PDF report** now includes the documents reviewed, the coverage counts, and each
  finding's evidence and citation — so it can be attached to a COA response as-is.

---

## 5. Running it

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows;  source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # then set ANTHROPIC_API_KEY
uvicorn server:app --reload --port 8000

# Frontend, in a second terminal
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000, drop documents in, and the router decides what to check.

**On Windows, always use `backend/venv/Scripts/python.exe`.** The Python on the system PATH is a
different installation and does not have these dependencies.

---

## 6. Verifying it

```bash
cd backend
./venv/Scripts/python.exe -m pytest -q
```

Current result: **143 passed, 39 skipped**. The skips are the tests that need a live API key.

The suite runs against 45 labelled fixtures in `backend/fixtures/cases/` — clean packets and packets
with a single known defect injected into each (a changed quantity, a wrong contract number, a
removed signature, an arithmetic error, a shifted date, a dropped attachment, diverging serial
numbers). Every injected defect must be caught, and clean packets must not produce high-severity
findings. That gives an exact false-negative measurement rather than an impression.

End-to-end scenarios to demo:

1. **T6** — Market Research + TOR + DCB + Bidding Docs → planning alignment findings.
2. **T2** — the same set → compliance findings with RA 12009 / IRR citations.
3. **T5** — Delivery Receipt + Technical Inspection Report + PAR → serials, quantities, dates.
4. **T4** — contract + payment set → discrepancies tagged amendment vs variation order.
5. **T3** — 10+ mixed-type files including Word and Excel → per-type completeness, no cap.
6. **T1** — the DV rulepack against the synthetic DV fixtures.
7. Restart the backend, open **Past Reviews** → everything is still there.

---

## 7. Two things to know before demoing

**The API key is a placeholder.** `backend/.env` currently contains the literal string
`your-anthropic-key`. Everything in this guide that does not call the model — routing, the rule
engine, the consistency engine, citation retrieval, the verdict, persistence, the whole test suite —
has been run and verified. The three paths that do call the model (vision OCR, classification
fallback, fact extraction) have **never been executed**. Put a real key in `.env` and run one real
document through before any demo.

**Seven documents are still needed from PCMD.** These do not block the prototype, but they cap its
fidelity on T1, T4 and T5:

1. **Sample Disbursement Vouchers**, both complete and deficient. There are none in `docs/`; the DV
   rulepack was built from the COA/GAM standard structure.
2. **The rest of the GECS payment packet.** The folder holds only items 3, 6.1, 9 and 10 — items 1,
   2 and 4 through 8 are missing (likely the DV, the Obligation Request, the PO, the invoice, the
   IAR and the Certificate of Acceptance).
3. **A Warranty Certificate and an ICS.** Both are named in T5; neither is present.
4. **The signed GECS contract.** T4 needs a contract and a payment set for the *same* project. The
   only contract in `docs/` is for an unrelated project (PIALEOS NCR Public Markets).
5. **Loan Agreement No. 9370-PH**, the **DICT Project Operations Manual**, and the **World Bank IPF
   Procurement Regulations (September 2023)** — all three are cited in T1's reference column and
   none is present.
6. **Internal workflow and SOP documents** — the preparer/certifier/reviewer/approver matrix and
   signing order, internal acceptance checklists, and the list of recurring COA and internal-audit
   deficiencies. These were requested in nearly every task. Until they arrive, **the DV signatory
   matrix is provisional**, derived from GAM Volume I and COA Circular 2023-004.
7. **The full GAM Volume II.** The copy in `docs/` is an 11-page excerpt, so the Appendices 59, 62
   and 71 that T4 cites are not in the index — findings that rest on them will be marked unverified.

---

## 8. Extending it

- **A new compliance rule** → add a YAML block to the relevant pack in `backend/rules/packs/`.
- **A new cross-document check** → add a `compare` entry to a profile in
  `backend/consistency/profiles/`.
- **A new document type** → add its label to `backend/facts/classify.py` and its field profile to
  `backend/facts/extract.py`; the router, both engines and the interface pick it up automatically.
- **A new legal source** → drop the PDF in and re-run `backend/kb/build_index.py`.

None of these requires touching the pipeline, the graph, or the interface.
