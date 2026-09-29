"""The checker pipeline: ingest, classify, extract, route, check, compile.

This is the spine the six assigned features hang off. The shape is:

    ingest -> classify -> extract -> route -> [selected checkers] -> compile

`route` is the part that earns the design. Rather than running every check on
every upload, it reads the document types that were actually detected and
fires only the checkers those types can support. A packet of a contract and a
disbursement voucher gets the contract-to-payment comparison; a packet of a
TOR and bidding documents gets planning alignment; a single unrecognised file
still gets the per-type completeness pack, because "we applied no checks" must
never look the same as "we found nothing wrong".

The six original advisory agents are preserved as one routed branch. They fire
for planning documents, which is what they were written for, and are skipped
for a payment packet, which they know nothing about.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from advisory import advisory_verdict
from agents.analysis import create_thinking_log
from consistency.engine import applicable_profiles, load_all_profiles, run_profiles
from facts.classify import classify_document
from facts.extract import extract_facts
from facts.schema import DocumentFacts
from findings import Finding, summarize
from ingest.loaders import LoadedDocument, load_document
from rules.engine import applicable_packs, load_all_packs, run_packs
from state import AgentState

# Document types the six advisory agents were written against. A payment
# voucher tells them nothing, so they are not run on one.
PLANNING_DOC_TYPES = {
    "ppmp",
    "app",
    "pr",
    "tor",
    "market_study",
    "dcb",
    "bidding_docs",
    "rfq",
    "sbb",
}

# Node names the router can return. Kept here so the graph and the router
# cannot drift apart.
ADVISORY_NODES = [
    "spec_validator",
    "lcca_analyzer",
    "market_researcher",
    "sustainability_analyst",
    "domestic_preference_checker",
    "modality_advisor",
]
CHECKER_NODES = ["rule_checks", "consistency_checks"] + ADVISORY_NODES


# -- helpers ---------------------------------------------------------------


def _facts_from_state(state: AgentState) -> List[DocumentFacts]:
    """Revalidate the stored facts. State holds JSON; checkers want models."""
    out = []
    for raw in state.get("documents") or []:
        try:
            out.append(DocumentFacts.model_validate(raw))
        except Exception:
            # A record that will not revalidate is a bug in extraction, not a
            # reason to lose the other documents in the packet.
            continue
    return out


def _findings_to_state(findings: List[Finding]) -> List[Dict[str, Any]]:
    return [f.model_dump(mode="json") for f in findings]


# -- ingest ----------------------------------------------------------------


def ingest_node(state: AgentState) -> Dict[str, Any]:
    """Load every uploaded file to markdown, one record per file.

    Scanned pages go through Tesseract OCR inside `load_document`; the cache
    means a re-run of the same file costs nothing. `parsed_text` is still
    produced because the advisory agents and the chat endpoint read it.
    """
    logs = [create_thinking_log("Ingest", "Reading uploaded documents...", "active")]
    paths = state.get("original_pdf_paths", []) or []

    if not paths:
        logs.append(create_thinking_log("Ingest", "No files were uploaded", "complete"))
        return {"loaded_documents": [], "parsed_text": "", "thinking_logs": logs}

    loaded: List[Dict[str, Any]] = []
    blobs: List[str] = []

    for index, path in enumerate(paths, start=1):
        name = Path(path).name
        try:
            document = load_document(path)
        except Exception as e:
            document = LoadedDocument(
                path=str(path), filename=name, text="", error=str(e)
            )

        loaded.append(asdict(document))
        blobs.append(f"===== Document {index}: {name} =====\n{document.text}")

        if document.error:
            message = f"{name}: could not be read ({document.error})"
        elif document.is_empty:
            message = f"{name}: no readable text found"
        elif document.source == "vision":
            message = (
                f"{name}: scanned, {document.pages_read} page(s) read by OCR"
            )
        else:
            message = f"{name}: {document.pages_read or 1} page(s) read"
        logs.append(create_thinking_log("Ingest", message, "complete"))

    logs.append(
        create_thinking_log("Ingest", f"{len(loaded)} document(s) loaded", "complete")
    )
    return {
        "loaded_documents": loaded,
        "parsed_text": "\n\n".join(blobs),
        "thinking_logs": logs,
    }


# -- classify --------------------------------------------------------------


def classify_node(state: AgentState) -> Dict[str, Any]:
    """Name each document. Everything downstream routes off this.

    Classification reads the first two pages only. It is deliberately cheap
    and deliberately separate from extraction: knowing a file is a Purchase
    Request is what decides which fields are worth asking for.
    """
    logs = [
        create_thinking_log("Classifier", "Identifying document types...", "active")
    ]
    loaded = state.get("loaded_documents") or []
    if not loaded:
        return {"thinking_logs": logs}

    updated = []
    for raw in loaded:
        record = dict(raw)
        text = record.get("text") or ""
        name = record.get("filename", "")
        if not text.strip():
            record["doc_type"] = "other"
            record["doc_type_confidence"] = 0.0
            logs.append(
                create_thinking_log(
                    "Classifier", f"{name}: unreadable, left unclassified", "complete"
                )
            )
        else:
            doc_type, confidence = classify_document(text, filename=name)
            record["doc_type"] = doc_type
            record["doc_type_confidence"] = confidence
            logs.append(
                create_thinking_log(
                    "Classifier",
                    f"{name}: {doc_type} ({confidence:.0%} confidence)",
                    "complete",
                )
            )
        updated.append(record)

    return {"loaded_documents": updated, "thinking_logs": logs}


# -- extract ---------------------------------------------------------------

_LOADED_FIELDS = set(LoadedDocument.__dataclass_fields__)


def extract_node(state: AgentState) -> Dict[str, Any]:
    """Turn each document into canonical facts.

    This is the keystone: from here on no checker sees raw text. Six features
    share two engines precisely because they all read the same record.
    """
    logs = [
        create_thinking_log("Extractor", "Extracting fields from documents...", "active")
    ]
    loaded = state.get("loaded_documents") or []
    documents: List[Dict[str, Any]] = []

    for raw in loaded:
        name = raw.get("filename", "")
        doc_type = raw.get("doc_type")
        document = LoadedDocument(
            **{k: v for k, v in raw.items() if k in _LOADED_FIELDS}
        )
        if document.is_empty:
            logs.append(
                create_thinking_log(
                    "Extractor", f"{name}: skipped, nothing to read", "complete"
                )
            )
            continue
        try:
            facts = extract_facts(document, doc_type=doc_type)
        except Exception as e:
            logs.append(
                create_thinking_log(
                    "Extractor", f"{name}: extraction failed ({e})", "complete"
                )
            )
            continue

        documents.append(facts.model_dump(mode="json"))
        if facts.error:
            logs.append(
                create_thinking_log("Extractor", f"{name}: {facts.error}", "complete")
            )
        else:
            logs.append(
                create_thinking_log(
                    "Extractor",
                    f"{name}: {len(facts.items)} line item(s), "
                    f"{len(facts.signatories)} signatory block(s)",
                    "complete",
                )
            )

    logs.append(
        create_thinking_log(
            "Extractor", f"{len(documents)} document(s) ready for checking", "complete"
        )
    )
    return {"documents": documents, "thinking_logs": logs}


# -- route -----------------------------------------------------------------


def plan_route(documents: List[DocumentFacts], run_advisory: bool = True) -> List[str]:
    """Decide which checkers this packet can support.

    Pure and importable so it can be tested without building a graph.

    `run_advisory` exists for the Compliance Checks tab inside a procurement
    record, which sits beside an AI Review that already reads the documents
    with an LLM. Firing the six advisory agents there would pay for a second
    opinion on the same planning questions and show it nowhere — they write
    to `analysis_results`, which that tab does not render. The Analyst page
    passes nothing and keeps all of them.
    """
    if not documents:
        return []

    selected: List[str] = []

    if applicable_packs(documents):
        selected.append("rule_checks")
    if applicable_profiles(documents):
        selected.append("consistency_checks")

    detected = {d.doc_type for d in documents}
    if run_advisory and detected & PLANNING_DOC_TYPES:
        selected.extend(ADVISORY_NODES)

    return selected


def route_node(state: AgentState) -> Dict[str, Any]:
    """Record the routing decision so the UI can show what ran and why."""
    documents = _facts_from_state(state)
    selected = plan_route(documents, run_advisory=state.get("run_advisory", True))

    detected = sorted({d.type_label or d.doc_type for d in documents})
    logs = [create_thinking_log("Router", "Selecting applicable checks...", "active")]

    if detected:
        logs.append(
            create_thinking_log("Router", "Detected: " + ", ".join(detected), "complete")
        )

    if not selected:
        logs.append(
            create_thinking_log(
                "Router",
                "No document could be read, so no checks were applied.",
                "complete",
            )
        )
    else:
        described = []
        if "rule_checks" in selected:
            described.append("compliance and completeness rules")
        if "consistency_checks" in selected:
            described.append("cross-document consistency")
        if ADVISORY_NODES[0] in selected:
            described.append("planning advisory analysis")
        logs.append(
            create_thinking_log("Router", "Running " + "; ".join(described), "complete")
        )

    return {"routed_checkers": selected, "thinking_logs": logs}


def route(state: AgentState) -> List[str]:
    """The conditional edge. Returns the node names to run in parallel."""
    selected = state.get("routed_checkers") or []
    # Every path must reach the compiler. With nothing selected, go straight
    # there so the run still produces a report explaining why.
    return selected or ["report_compiler"]


# -- checkers --------------------------------------------------------------


def rule_checks_node(state: AgentState) -> Dict[str, Any]:
    """T1, T2, T3 -- the per-document rule engine."""
    logs = [
        create_thinking_log("Rule Checker", "Applying compliance rules...", "active")
    ]
    documents = _facts_from_state(state)
    packs = load_all_packs()
    pack_ids = applicable_packs(documents)

    try:
        # Passes are kept, not discarded. The compiler needs to know how many
        # checks actually ran: "no findings" over three checks and "no
        # findings" over sixty are not the same result, and the confidence
        # score has to be able to tell them apart.
        findings = run_packs(pack_ids, documents, include_passes=True)
    except Exception as e:
        logs.append(
            create_thinking_log("Rule Checker", f"Error: {e}", "complete")
        )
        return {"thinking_logs": logs}

    for pack_id in pack_ids:
        pack = packs.get(pack_id)
        if not pack:
            continue
        failed = sum(
            1 for f in findings if f.is_failure and f.task == pack.task
        )
        logs.append(
            create_thinking_log(
                "Rule Checker",
                f"{pack.name}: {failed} issue(s) found"
                if failed
                else f"{pack.name}: no issues",
                "complete",
            )
        )

    return {"findings": _findings_to_state(findings), "thinking_logs": logs}


def consistency_checks_node(state: AgentState) -> Dict[str, Any]:
    """T4, T5, T6 -- the cross-document consistency engine."""
    logs = [
        create_thinking_log(
            "Consistency Checker", "Cross-checking documents...", "active"
        )
    ]
    documents = _facts_from_state(state)
    profiles = load_all_profiles()
    profile_ids = applicable_profiles(documents)

    try:
        findings = run_profiles(profile_ids, documents, include_passes=True)
    except Exception as e:
        logs.append(
            create_thinking_log("Consistency Checker", f"Error: {e}", "complete")
        )
        return {"thinking_logs": logs}

    for profile_id in profile_ids:
        profile = profiles.get(profile_id)
        if not profile:
            continue
        failed = sum(1 for f in findings if f.is_failure and f.task == profile.task)
        logs.append(
            create_thinking_log(
                "Consistency Checker",
                f"{profile.name}: {failed} discrepancy(ies)"
                if failed
                else f"{profile.name}: documents agree",
                "complete",
            )
        )

    return {"findings": _findings_to_state(findings), "thinking_logs": logs}


# -- compile ---------------------------------------------------------------

# Findings at or above this severity are what decide PASS/FAIL. A low or info
# finding is worth printing and not worth failing a packet over.
BLOCKING_SEVERITIES = ("high",)


def _grouped(findings: List[Finding]) -> List[Dict[str, Any]]:
    """Group failures by category, most severe category first.

    Each group keeps both the plain `items` strings the current UI renders and
    a `details` array carrying evidence, authority and the side-by-side
    comparison, so the richer view can be built without changing this shape
    again.
    """
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    buckets: Dict[str, List[Finding]] = {}
    for finding in findings:
        buckets.setdefault(finding.category or "General", []).append(finding)

    groups = []
    for category, group in buckets.items():
        group.sort(key=lambda f: f.sort_key)
        severity = min(
            (f.severity for f in group), key=lambda s: order.get(s, 9), default="low"
        )
        groups.append(
            {
                "category": category,
                "severity": severity,
                "items": [f.summary_line() for f in group],
                "details": [
                    {
                        "rule_id": f.rule_id,
                        "task": f.task,
                        "title": f.title,
                        "detail": f.detail,
                        "severity": f.severity,
                        "field": f.field,
                        "action_hint": f.action_hint,
                        "evidence": [e.model_dump(mode="json") for e in f.evidence],
                        "authority": f.authority,
                        "comparison": f.comparison,
                    }
                    for f in group
                ],
            }
        )

    groups.sort(key=lambda g: (order.get(g["severity"], 9), g["category"]))
    return groups


def _confidence(documents: List[DocumentFacts], counts: Dict[str, int]) -> int:
    """How much the verdict should be trusted.

    Two things erode it: documents we could not read well, and checks we could
    not run. Reporting a clean PASS at high confidence over a packet half of
    which failed to extract would be the worst output this system could give.
    """
    if not documents:
        return 0
    extraction = sum(d.extraction_confidence for d in documents) / len(documents)
    total = max(counts["total"], 1)
    coverage = 1.0 - (counts["skipped"] / total)
    return int(round(100 * (0.6 * extraction + 0.4 * coverage)))


def compile_node(state: AgentState) -> Dict[str, Any]:
    """Build the verdict from the findings the checkers actually produced."""
    logs = [
        create_thinking_log("Report Compiler", "Compiling the report...", "active")
    ]

    documents = _facts_from_state(state)
    findings = [Finding.model_validate(f) for f in state.get("findings") or []]
    failures = [f for f in findings if f.is_failure]
    skipped = [f for f in findings if f.skipped_reason]
    counts = summarize(findings)

    blocking = [f for f in failures if f.severity in BLOCKING_SEVERITIES]
    groups = _grouped(failures)

    # Checks that could not run are reported as their own group. "Not
    # verified" is not "compliant", and a reviewer has to be able to see the
    # difference at a glance.
    if skipped:
        groups.append(
            {
                "category": "Not Verified",
                "severity": "low",
                "items": sorted(
                    {f"{f.title}: {f.skipped_reason}" for f in skipped if f.title}
                ),
                "details": [],
            }
        )

    unverified = f", {len(skipped)} check(s) not verified" if skipped else ""

    # Per-assigned-feature counts (T1..T6), so the UI can show what each
    # requirement found without re-deriving it from the finding list.
    task_stats: Dict[str, Dict[str, int]] = {}
    for f in findings:
        if not f.task:
            continue
        stats = task_stats.setdefault(
            f.task,
            {"total": 0, "failed": 0, "passed": 0, "skipped": 0, "high": 0},
        )
        stats["total"] += 1
        if f.skipped_reason is not None:
            stats["skipped"] += 1
        elif f.passed:
            stats["passed"] += 1
        else:
            stats["failed"] += 1
            if f.severity == "high":
                stats["high"] += 1

    readable = [d for d in documents if not d.error]
    extraction_errors = [d.error for d in documents if d.error]

    if not documents:
        status, title = "FAIL", "No document could be read"
    elif not readable:
        status = "FAIL"
        title = f"Documents could not be processed — {extraction_errors[0]}"
    elif blocking:
        status = "FAIL"
        title = (
            f"{len(blocking)} critical issue(s) across "
            f"{len(documents)} document(s){unverified}"
        )
    elif failures:
        status = "PASS"
        title = f"No critical issues; {len(failures)} item(s) to address{unverified}"
    else:
        status = "PASS"
        title = (
            f"{len(documents)} document(s) reviewed, "
            f"{counts['passed']} check(s) passed{unverified}"
        )

    verdict: Dict[str, Any] = {
        "status": status,
        "title": title,
        "confidence": _confidence(documents, counts),
        "findings": groups,
        "summary": counts,
        "documents": [
            {
                "file": d.source.filename or d.source.file,
                "doc_type": d.doc_type,
                "label": d.type_label,
                "confidence": round(d.doc_type_confidence, 2),
                "pages_read": d.source.pages_read,
                "total_pages": d.source.total_pages,
                "skipped_pages": d.source.skipped_pages,
                "ingest_source": d.source.ingest_source,
                "error": d.error,
            }
            for d in documents
        ],
        "checkers_run": state.get("routed_checkers") or [],
        "tasks": task_stats,
    }

    # The six advisory agents, when the router fired them, contribute
    # commentary -- not the verdict. Their failure must not take the
    # deterministic result down with it.
    analysis_results = state.get("analysis_results") or {}
    if any(analysis_results.values()):
        advisory = advisory_verdict(analysis_results)
        if advisory.get("error"):
            logs.append(
                create_thinking_log(
                    "Report Compiler", advisory["error"], "complete"
                )
            )
        else:
            verdict["advisory"] = advisory
            for group in advisory.get("findings", []) or []:
                if not isinstance(group, dict):
                    continue
                verdict["findings"].append(
                    {
                        "category": f"Advisory: {group.get('category', 'Analysis')}",
                        "severity": group.get("severity", "low"),
                        "items": group.get("items", []),
                        "details": [],
                    }
                )

    logs.append(
        create_thinking_log(
            "Report Compiler",
            f"{counts['failed']} finding(s), {counts['high']} critical",
            "complete",
        )
    )

    return {"compiled_report": json.dumps(verdict, indent=2), "thinking_logs": logs}
