"""
One checker Finding rendered as one ReviewFinding.

The two schemas were written independently and turned out to describe nearly
the same thing, which is why this file is a translation and not a rewrite:

    findings.Finding            review.schema.ReviewFinding
    ------------------------    ---------------------------------------
    detail                      analysis
    evidence[0]                 source (doc, page, section)
    comparison.rows             comparison (List[ComparedText])
    authority                   policy_sources (List[PolicyCitation])
    action_hint                 recommendation
    passed / skipped_reason     severity "compliant" / "info"

Keeping the checkers on their own Finding type rather than making them emit
ReviewFinding directly is deliberate. `Finding` carries `passed` and
`skipped_reason` as first-class state, and the whole point of the engines is
that "checked and compliant", "checked and failed" and "could not check" are
three different answers. Collapsing that into a severity at the point of
production would lose the distinction everywhere upstream — in the fixtures,
in the compiler, in the report. It is lost only here, at the edge, and only
because the UI needs a single ordered scale to sort by.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from findings import Finding
from review.schema import (
    ComparedText,
    PolicyCitation,
    ReviewFinding,
    Severity,
    Source,
)

#: Our four levels onto the review's five. `high` becomes `critical` because
#: that is what the review scale calls the same thing; the review's
#: `compliant` has no counterpart on our side, since we carry it as a flag.
SEVERITY_MAP: Dict[str, Severity] = {
    "high": "critical",
    "medium": "medium",
    "low": "low",
    "info": "info",
}

#: What the BAC is expected to do about a discrepancy, spelled out. The YAML
#: carries the short form; a reviewer needs the sentence.
ACTION_HINTS: Dict[str, str] = {
    "amendment_to_order": (
        "If the change is to be kept, issue an Amendment to Order under "
        "Section 71.1.1 of the IRR before payment is processed."
    ),
    "variation_order": (
        "If the change is to be kept, issue a Variation Order under Section "
        "71.2.1 of the IRR, supported by the documentation COA Circular "
        "2009-001 Annex B requires."
    ),
}


def _severity_of(finding: Finding) -> Severity:
    """
    The review scale's name for this outcome.

    A skipped check is `info`, never `compliant`: the reviewer is being told
    the check did not run, and a scale that renders that the same as "checked
    and no issue found" would be reporting an absence of evidence as evidence
    of compliance.
    """
    if finding.skipped_reason is not None:
        return "info"
    if finding.passed:
        return "compliant"
    return SEVERITY_MAP.get(finding.severity, "medium")


def _title_of(finding: Finding) -> str:
    """
    A headline that states the outcome.

    Rule and comparison titles are written as the requirement being tested —
    "Delivered quantities match the contracted quantities" — which reads
    correctly under a pass and backwards under a failure. That is the right
    convention in the YAML, where one title has to serve both outcomes, but a
    card headed with it and badged "critical" would be telling the reviewer
    the opposite of what happened.
    """
    title = finding.title or finding.rule_id
    if finding.skipped_reason is not None:
        return f"Not verified — {title}"
    if finding.passed:
        return title
    return f"Not met — {title}"


def _analysis_of(finding: Finding) -> str:
    if finding.skipped_reason is not None:
        return f"Not verified — {finding.skipped_reason}"
    return finding.detail or finding.title


def _source_of(finding: Finding) -> Source:
    """
    Where the finding was seen. The first piece of evidence, because Source
    holds one document and the rest are carried in `comparison`.
    """
    if not finding.evidence:
        return Source(doc="", section=finding.category or "")
    first = finding.evidence[0]
    return Source(
        doc=first.document or "(document)",
        page=first.page if (first.page or 0) >= 1 else None,
        section=first.field or finding.category or "",
    )


#: How many rows of a line-item disagreement to render side by side. Each
#: costs two entries, and a reviewer scrolling past forty of them is reading
#: the `analysis` sentence instead.
MAX_ITEM_ROWS = 6


def _comparison_of(finding: Finding) -> List[ComparedText]:
    """
    Both sides of a cross-document disagreement, reference first.

    Two payload shapes, because the reference means different things in each:

    - `scalar` — one reference value for the whole comparison, then a row per
      document that disagrees with it.
    - `line_items` — the reference value varies per line, so it is carried on
      the row rather than once at the top, and each disagreeing line is
      rendered as its own reference/actual pair.

    Rule findings have no comparison and return an empty list, which is what
    the UI expects when there is a single passage to quote instead.
    """
    payload: Optional[Dict[str, Any]] = finding.comparison
    if not payload:
        return []

    label = finding.field or ""
    reference = payload.get("reference") or {}
    reference_doc = str(reference.get("document") or "")
    rows = [row for row in (payload.get("rows") or []) if isinstance(row, dict)]
    out: List[ComparedText] = []

    if payload.get("kind") == "line_items":
        for row in rows[:MAX_ITEM_ROWS]:
            item = str(row.get("item") or "")
            pair_label = f"{label} — {item}" if item else label
            if reference_doc:
                out.append(
                    ComparedText(
                        doc=reference_doc,
                        label=f"{pair_label} (reference)" if pair_label else "Reference",
                        quote=str(row.get("reference_value", "")),
                    )
                )
            out.append(
                ComparedText(
                    doc=str(row.get("document") or "(document)"),
                    page=row.get("page") if (row.get("page") or 0) >= 1 else None,
                    label=pair_label,
                    quote=str(row.get("value", "")),
                )
            )
        return out

    if reference_doc:
        out.append(
            ComparedText(
                doc=reference_doc,
                label=f"{label} (reference)" if label else "Reference",
                quote=str(reference.get("value", "")),
            )
        )

    for row in rows:
        out.append(
            ComparedText(
                doc=str(row.get("document") or "(document)"),
                page=row.get("page") if (row.get("page") or 0) >= 1 else None,
                label=label,
                quote=str(row.get("value", "")),
            )
        )

    return out


def _delta_of(finding: Finding) -> Optional[str]:
    """The disagreement in one line, for the summary strip above the quotes."""
    payload = finding.comparison
    if not payload:
        return None
    rows = payload.get("rows") or []
    details = [
        str(row.get("detail")) for row in rows if isinstance(row, dict) and row.get("detail")
    ]
    return "; ".join(details[:3]) or None


def _policy_of(finding: Finding) -> tuple[str, List[PolicyCitation]]:
    """
    The provision the finding rests on, as a label and as a citation.

    An unverified authority — the check named a section that is not in the
    indexed corpus — yields the label but no citation. That is the point of
    the flag: the UI must not present a provision as quoted and checked when
    nothing was retrieved to check it against.
    """
    authority = finding.authority or {}
    citation = str(authority.get("citation") or "")
    if not citation:
        return "", []
    if authority.get("unverified"):
        return f"{citation} (not found in the reference library)", []

    return citation, [
        PolicyCitation(
            title=str(authority.get("doc") or ""),
            section=str(authority.get("section") or ""),
            page=int(authority.get("page") or 0),
            quote=str(authority.get("quoted_text") or ""),
        )
    ]


def to_review_finding(finding: Finding) -> ReviewFinding:
    """Translate one checker finding for storage and display."""
    policy_basis, policy_sources = _policy_of(finding)
    recommendation = ACTION_HINTS.get(finding.action_hint or "", "")

    return ReviewFinding(
        # The rule id is already unique and stable across runs, and is what
        # the fixtures and the report refer to. Prefixed so a checker finding
        # and a review finding can never collide on one procurement.
        id=f"chk-{finding.rule_id}",
        dimension=finding.rule_id.split(".")[0],
        severity=_severity_of(finding),
        title=_title_of(finding),
        analysis=_analysis_of(finding),
        recommendation=recommendation,
        source=_source_of(finding),
        policy_basis=policy_basis,
        comparison=_comparison_of(finding),
        delta=_delta_of(finding),
        policy_sources=policy_sources,
    )


def _display_order(finding: Finding) -> tuple:
    """
    Failures first, then what could not be checked, then what passed.

    Deliberately not `Finding.sort_key`, which ranks by the severity declared
    on the rule regardless of outcome. That is right for the checker report,
    where a rule's importance is the point, and wrong here: it puts a
    high-severity rule that *passed* above a medium one that failed, so the
    first thing a reviewer sees on a defective packet is a green tick.
    """
    if finding.skipped_reason is not None:
        outcome = 1
    elif finding.passed:
        outcome = 2
    else:
        outcome = 0
    return (outcome,) + finding.sort_key


def to_review_findings(findings: List[Finding]) -> List[ReviewFinding]:
    """
    Translate a whole run, most serious first.

    Ordered here rather than in the UI so the stored list reads correctly
    wherever it is consumed — the tab, the final report, and the API.
    """
    ordered = sorted(findings, key=_display_order)
    return [to_review_finding(finding) for finding in ordered]
