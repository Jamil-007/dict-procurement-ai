# Dimension brief — Procurement & Market

Implement `backend/review/dimensions/procurement_market.py`, currently a stub.

Read `document_quality.py` first. It is the worked example, and the shape never
changes: build a prompt, call `analyze()`, return findings. Parallelism,
timeouts, finding ids and error isolation belong to the runner — this module
does none of them.

This brief supersedes any earlier "Agent 4" specification. Where the two differ,
this one is right, because it is written against the code that exists.

---

## 1. The question this dimension answers

**Does the planned procurement make sense against the available market
evidence?**

The review runs immediately before the procurement is posted to PhilGEPS. The
test is not whether the paperwork is complete but whether it would stand up:
if the ABC is challenged after award, is there a defensible basis for it on
the record? That is why every price claim here has to carry a citation, and
why a citation's authority is tracked as well as its content.

Six areas are in scope:

| Area | What you are looking at |
|---|---|
| Project cost estimate | Whether the ABC is supported by the market evidence on file |
| Design and specifications | Whether the specification is open enough to attract more than one offer |
| Technical criteria | Whether eligibility and technical requirements are proportionate |
| Delivery lead time | Whether the required schedule is achievable in this market |
| Storage and warehousing | Whether delivery and holding assumptions are stated and feasible |
| Market risks | Supply, pricing and availability conditions bearing on the procurement |

## 2. Boundaries

Five dimensions run in parallel over the same documents. Overlap produces
duplicate findings in front of the BAC, so stay inside the line.

- **Drafting quality** — ambiguity, wrong headings, blank sections — is
  Document Quality's. Not yours, even in a specification.
- **Two documents disagreeing** is Document Consistency's. If the TOR says 50
  units and the PPMP says 45, that is theirs. Yours is whether 50 units at
  this ABC is supportable in this market.
- **Legal and procedural compliance** — mode of procurement, thresholds,
  required approvals — is Compliance's.
- **Requirements and risk** is the closest neighbour, so use this split:
  you own the **market condition**, they own the **procurement response**.
  "Only two suppliers in the Philippines carry this module" is a market
  condition — yours. "The procurement carries no contingency for a
  single-source dependency" is a response — theirs.

Worked example. A 5-year on-site warranty is specified:
- *Yours:* whether 5-year on-site is offered in this market, and by how many
  suppliers.
- *Requirements & Risk:* whether the warranty term is proportionate to the
  asset life and what happens if the supplier exits.
- *Document Quality:* whether "on-site" is defined anywhere.
- *Compliance:* whether the warranty requirement is permitted to be set this way.

## 3. The ABC comes from the documents, not the record

`ctx.meta["abc"]` is what the BAC typed into the case when it was created —
not a verified figure, and not what this dimension reasons about. Establish
the actual ABC from the documents on file (PPMP, Purchase Request, Detailed
Cost Breakdown) and judge the market evidence against that. If a document
disagrees with `ctx.meta["abc"]`, or documents disagree with each other, that
is a cross-document inconsistency and belongs to Document Consistency — this
dimension still needs a number to reason about, so use whichever figure the
documents themselves support. `RECORD_IS_NOT_EVIDENCE` in `review/parsing.py`
carries this instruction into the prompt; every dimension that shows the model
`ctx.meta` pastes it in.

## 4. Documents read

```python
READS = (
    "Market Study",
    "Supplier Quotation",
    "Project Procurement Management Plan (PPMP)",
    "Terms of Reference (TOR)",
    "Technical Specifications",
    "Detailed Cost Breakdown",
)
```

Supplier Quotation is a **planning** document here: it is the price canvassing
evidence behind the market study and the ABC, not a bid received after posting.
It is your strongest internal evidence for whether the ABC is supported.

There is no "Market Scoping Checklist" document type. Its parameters are
assessed against the Market Study and Supplier Quotations instead — see §9.

**Never require a document set.** Users attach what they have and the analysis
must be sound on exactly that. Return `cannot_assess(...)` only when *none* of
the six types above is attached — and that finding is a record of what was
outside the review, not a demand. A procurement mid-drafting is a normal input.

## 5. Working without Tavily

`TAVILY_API_KEY` is not set locally and `run()` must work without it. This is
not a degraded curiosity; it is the default path on every developer machine
and the one to build first.

With no key, or when a search fails or returns nothing:

- Run every internal check — ABC against the PPMP, the Detailed Cost Breakdown
  and the Supplier Quotations; specification openness; delivery feasibility as
  stated; storage assumptions. Most of the value is here.
- Say so in the affected findings: *"No external market evidence was retrieved
  for this review; the assessment below rests on the attached documents."*
- Cap `confidence` at `"medium"` for anything price-related.
- Do not emit `cannot_assess`. Documents were read and checks were run.

A search failure must never fail the dimension. Wrap it, log it, carry on.

## 6. External search

Tavily is **evidence retrieval, not authority**. It supplies pages; the
judgement stays with the analyzer, and the citation stays with the BAC.

Pipeline:

```
extract what needs pricing  →  generate targeted queries  →  search
    →  rank by source tier  →  normalize prices  →  prompt  →  parse
    →  strip_unretrieved_sources()  →  findings
```

**Query generation.** One generic query returns nothing usable. Generate
several narrow ones from the actual line items — brand and model where the
specification names one, generic category plus capacity where it does not,
and at least one restricted to Philippine government sources. Include the
year for anything price-sensitive.

**Budget.** The runner kills a dimension at 180 seconds, and that ceiling
covers search, fetch and the LLM call. Cap searches at six, give each a short
per-request timeout, run them concurrently, and proceed with whatever came
back when the budget is spent. A partial result is fine; a timeout is not.

**Source tiers.** Rank every result before it reaches the prompt, using
`SOURCE_TIER_MEANING` in `review/schema.py`:

| Tier | Source |
|---|---|
| 1 | Philippine government — PhilGEPS, DBM, PS-DBM, COA, GPPB |
| 2 | Manufacturer or official distributor |
| 3 | Philippine supplier or reseller |
| 4 | Online marketplace listing |
| 5 | Informational — news, blogs, reviews |

Prefer tier 1–3. A tier 4 listing may be cited, but a finding resting on tier
4 or 5 alone cannot exceed `"medium"` confidence. Non-Philippine sources are
usable for availability and specification questions, rarely for price.

## 7. Price normalization

Two prices are not comparable until they describe the same thing. Before any
comparison, bring both sides onto the same basis and **state the basis in the
analysis**:

- currency and conversion date, where the source is not in pesos
- VAT inclusive or exclusive
- unit of sale — per unit, per licence, per user, per year
- quantity and delivery terms, where they move the price
- whether the figure is **observed** on the source or **derived** by you

Derived figures are legitimate. Undeclared derived figures are not. If a
comparison needs an assumption, say which.

## 8. What to raise

Write findings as points for the committee to verify. Never as determinations.

**Cost estimate.** Raise where the ABC sits materially outside the supported
range, where the ABC has no traceable basis in any attached document, or where
the Supplier Quotations are too few or too alike to establish a market price.
Quantify: the figure, the comparison, the gap, the basis.

**Specification openness.** A specification that names a brand, or whose
combination of parameters only one product satisfies, is **a potential concern
requiring BAC review** — never a determination that it is restrictive, and
never an allegation of tailoring. Say which parameters narrow the field and
what evidence supports that.

**Delivery feasibility.** Compare the required lead time against observed
availability and typical lead times. Note where the requirement appears tight
rather than asserting it is impossible.

**Market risks.** Single-source dependency, thin local supply, volatile
pricing, end-of-life or superseded products, import dependency. State the
condition and its evidence; leave the mitigation to Requirements & Risk.

**Record what passes.** Where the ABC is supported, or the specification is
genuinely open, emit a `"compliant"` finding saying so with its evidence. The
committee needs to see what was checked and held, not only what failed. A
dimension that returns only problems reads as if nothing else was examined.

## 9. Market scoping parameters

Assess these against the Market Study and Supplier Quotations. Each is a
question, not a checklist item to tick:

- **A — Market definition.** Is the relevant market described at all, and is
  the description specific enough to support the ABC?
- **B — Supplier landscape.** How many capable suppliers are identified, and
  is that number consistent with the specification's openness?
- **C — Price basis.** Where did the prices come from, how current are they,
  and are they like-for-like?
- **D — Availability and lead time.** Is stock and delivery evidence present?
- **E — Alternatives considered.** Were other solutions or configurations
  examined, or only the one being procured?
- **F — Cost over the asset's life.** Are recurring costs — licences, support,
  consumables, disposal — reflected, or only acquisition cost?

A parameter with no evidence is worth an `"info"` or `"low"` finding naming
what is absent. Absence of evidence is not evidence of a defect.

## 10. The output contract

`review/schema.py` is shared by all five dimensions and the frontend. Return
`List[ReviewFinding]` and nothing else — there is no `agent`, `category`,
`status`, `evidence[]` or `market_summary` field, and adding one drops the
finding at parse time.

Severity is exactly these five. **There is no `"high"`.**

| Severity | Meaning |
|---|---|
| `critical` | Potentially material issue requiring prompt BAC attention |
| `medium` | Meaningful issue but generally does not by itself prevent continuation |
| `low` | Minor quality or completeness issue |
| `info` | Observation rather than an identified deficiency |
| `compliant` | Checked and no issue found |

Do not restate these meanings in your prompt. `SEVERITY_MEANING` and
`FINDING_JSON_CONTRACT` are the single source; paste the contract in.

**Confidence is separate from severity.** Severity is how serious the issue
would be if true; confidence is how sure you are. A `critical` finding held at
`"low"` confidence still belongs in front of the BAC — it just has to say so.

**External sources.** Every figure not drawn from the uploaded documents needs
at least one `ExternalSource`. Paste `EXTERNAL_EVIDENCE_CONTRACT` into the
prompt *in addition to* `FINDING_JSON_CONTRACT` — it is opt-in precisely
because a dimension that never searches must not be told it may cite URLs.

Then enforce it. Instructing a model not to invent URLs is not the same as it
not inventing them:

```python
from review.parsing import strip_unretrieved_sources

findings = analyze(prompt, DIMENSION)
findings = strip_unretrieved_sources(findings, retrieved_urls)
```

Anything the search did not actually return is removed, and a finding left
with no surviving source is downgraded to `"low"` confidence.

A price comparison table is a single finding with `comparison[]` populated and
`delta` set — that is what `ComparedText` exists for. It is not a separate
summary object.

## 11. Safeguards

- Never state or imply that anything is illegal, non-compliant or rigged. That
  determination is the committee's. Use "potential concern", "requires BAC
  review", "available market evidence suggests".
- Never invent a price, a supplier, a URL or a lead time. A figure with no
  source is not a finding.
- Never present a derived figure as an observed one.
- Do not name a supplier as preferred, or recommend a product.
- Nothing in the UI may mention search, retrieval, prompts, models or tokens.
  The user sees findings and citations.

## 12. Done when

1. `run()` works with `TAVILY_API_KEY` unset, on a record with only a Market
   Study attached.
2. `run()` works with no documents at all — returns `cannot_assess`.
3. Every finding validates against `ReviewFinding`; none is dropped by
   `findings_from_response`.
4. Every external figure carries an `ExternalSource` that survives
   `strip_unretrieved_sources`.
5. At least one `"compliant"` finding is produced on a sound record.
6. A full review completes inside the 180-second dimension timeout with all
   five dimensions running.
7. No finding asserts illegality, and no finding names a preferred supplier.

## 13. Open question for Mark

Tavily results are non-deterministic and re-running a review calls
`replace_findings`, which discards BAC decisions. Once this dimension searches
the web, the same record reviewed twice can produce different findings and
different prices. Whether retrieved evidence should be pinned to the record at
first run — so a review is reproducible and defensible months later — is not
decided. Build the straightforward path first; raise it before this goes near
live procurement data.
