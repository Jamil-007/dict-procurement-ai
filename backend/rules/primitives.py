"""Deterministic check primitives.

Every rule in every rulepack resolves to one of these functions. They are
plain Python and take no model: whether a signature block is blank or whether
gross minus tax equals net is a fact about the document, and asking a
language model to decide it would trade a correct answer for a plausible one.

The one exception is `llm_judgment`, reserved for genuinely qualitative
questions such as whether a specification is unduly restrictive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from facts.schema import DocumentFacts
from findings import Evidence
from rules.parsing import (
    as_list,
    format_amount,
    is_blank,
    normalize,
    parse_amount,
    parse_amount_in_words,
    parse_date,
)


@dataclass
class Outcome:
    """The result of running one primitive against one document."""

    passed: bool
    detail: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    skipped_reason: Optional[str] = None
    action_hint: Optional[str] = None

    @classmethod
    def ok(cls, detail: str = "", evidence: Optional[List[Evidence]] = None) -> "Outcome":
        return cls(True, detail, evidence or [])

    @classmethod
    def fail(
        cls,
        detail: str,
        evidence: Optional[List[Evidence]] = None,
        action_hint: Optional[str] = None,
    ) -> "Outcome":
        return cls(False, detail, evidence or [], action_hint=action_hint)

    @classmethod
    def skip(cls, reason: str) -> "Outcome":
        return cls(False, "", [], skipped_reason=reason)


def _evidence(facts: DocumentFacts, field_path: str, value: Any = None) -> Evidence:
    return Evidence(
        document=facts.source.filename,
        doc_type=facts.doc_type,
        page=facts.page_of(field_path),
        field=field_path,
        value=None if value is None else str(value),
    )


# -- presence --------------------------------------------------------------


def field_present(facts: DocumentFacts, params: Dict) -> Outcome:
    """Required fields must be filled in.

    `fields` is a list of dotted paths. Reports every missing field in one
    finding rather than one finding per field, because a reviewer wants the
    list of blanks, not fifteen separate rows.
    """
    required = params.get("fields", [])
    missing = [path for path in required if is_blank(facts.get_path(path))]

    if not missing:
        return Outcome.ok(f"All {len(required)} required field(s) present.")

    return Outcome.fail(
        f"Missing required field(s): {', '.join(missing)}.",
        [_evidence(facts, path) for path in missing],
    )


def items_present(facts: DocumentFacts, params: Dict) -> Outcome:
    """The document must list at least `min_count` line items."""
    minimum = int(params.get("min_count", 1))
    count = len(facts.items)
    if count >= minimum:
        return Outcome.ok(f"{count} line item(s) found.")
    return Outcome.fail(
        f"Expected at least {minimum} line item(s); found {count}.",
        [_evidence(facts, "items")],
    )


def item_field_present(facts: DocumentFacts, params: Dict) -> Outcome:
    """Every line item must carry the named fields.

    Used for T5: a Delivery Receipt without serial numbers cannot be
    cross-checked against a PAR at all.
    """
    names = params.get("fields", [])
    if not facts.items:
        return Outcome.skip("Document has no line items to check.")

    gaps: List[str] = []
    evidence: List[Evidence] = []
    for index, item in enumerate(facts.items, start=1):
        for name in names:
            if is_blank(getattr(item, name, None)):
                gaps.append(f"item {index} ({item.description[:40] or 'unnamed'}): {name}")
                evidence.append(
                    Evidence(
                        document=facts.source.filename,
                        doc_type=facts.doc_type,
                        page=item.page,
                        field=f"items[{index}].{name}",
                    )
                )

    if not gaps:
        return Outcome.ok(f"All {len(facts.items)} line item(s) carry {', '.join(names)}.")
    shown = "; ".join(gaps[:6]) + (f"; and {len(gaps) - 6} more" if len(gaps) > 6 else "")
    return Outcome.fail(f"Line items missing required detail: {shown}.", evidence[:10])


def attachment_present(facts: DocumentFacts, params: Dict) -> Outcome:
    """The document must reference the required supporting attachments.

    This is the COA documentary-requirements check: a Disbursement Voucher
    for the delivery of goods must be supported by a specified set of papers,
    and the voucher's own attachment list is where that is declared.
    """
    required = params.get("attachments", [])
    if not required:
        return Outcome.skip("No attachment list configured.")

    declared = [normalize(a) for a in facts.attachments_referenced]
    if not declared:
        return Outcome.fail(
            f"The document lists no supporting attachments. "
            f"{len(required)} are required: {', '.join(required)}.",
            [_evidence(facts, "attachments_referenced")],
        )

    missing: List[str] = []
    for requirement in required:
        # A requirement may be satisfied by any of several names, e.g. an
        # Inspection and Acceptance Report or a Certificate of Acceptance.
        aliases = params.get("aliases", {}).get(requirement, [])
        candidates = [normalize(name) for name in [requirement, *aliases]]
        if not any(any(c in d or d in c for d in declared) for c in candidates if c):
            missing.append(requirement)

    if not missing:
        return Outcome.ok(f"All {len(required)} required attachment(s) referenced.")
    return Outcome.fail(
        f"Required supporting document(s) not referenced: {', '.join(missing)}.",
        [_evidence(facts, "attachments_referenced")],
    )


# -- signatures ------------------------------------------------------------


def signatory_present(facts: DocumentFacts, params: Dict) -> Outcome:
    """Required signature blocks must exist and, optionally, be signed.

    The distinction matters: an unsigned block with a printed name is one of
    the most common COA observations, and it is invisible unless `signed` is
    checked separately from presence.
    """
    roles = params.get("roles", [])
    require_signed = params.get("require_signed", True)
    require_date = params.get("require_date", False)

    if not facts.signatories:
        return Outcome.fail(
            f"No signature blocks were found. Required: {', '.join(roles)}.",
            [_evidence(facts, "signatories")],
        )

    absent: List[str] = []
    unsigned: List[str] = []
    undated: List[str] = []
    evidence: List[Evidence] = []

    for role in roles:
        signatory = facts.signatory_for(role)
        if signatory is None:
            absent.append(role)
            evidence.append(_evidence(facts, "signatories"))
            continue
        where = Evidence(
            document=facts.source.filename,
            doc_type=facts.doc_type,
            page=signatory.page,
            field=f"signatories[{role}]",
            value=signatory.name,
        )
        if require_signed and not signatory.signed:
            unsigned.append(f"{role} ({signatory.name or 'no printed name'})")
            evidence.append(where)
        elif require_date and is_blank(signatory.date):
            undated.append(f"{role} ({signatory.name or 'no printed name'})")
            evidence.append(where)

    problems: List[str] = []
    if absent:
        problems.append(f"no signature block for {', '.join(absent)}")
    if unsigned:
        problems.append(f"unsigned: {', '.join(unsigned)}")
    if undated:
        problems.append(f"signed but undated: {', '.join(undated)}")

    if not problems:
        return Outcome.ok(f"All {len(roles)} required signature(s) present and signed.")
    return Outcome.fail(f"Signature requirements not met - {'; '.join(problems)}.", evidence)


def signatory_order(facts: DocumentFacts, params: Dict) -> Outcome:
    """Signature dates must follow the prescribed approval sequence.

    An approval dated before the certification it relies on is a genuine
    control failure, not a clerical one -- it means the approver signed
    before the funds were certified available.
    """
    sequence = params.get("sequence", [])
    dated: List[tuple] = []

    for role in sequence:
        signatory = facts.signatory_for(role)
        if signatory is None or is_blank(signatory.date):
            continue
        parsed = parse_date(signatory.date)
        if parsed is None:
            continue
        dated.append((role, parsed, signatory))

    if len(dated) < 2:
        return Outcome.skip(
            "Fewer than two signature dates could be read; sequence not verifiable."
        )

    violations: List[str] = []
    evidence: List[Evidence] = []
    for (role_a, date_a, sig_a), (role_b, date_b, sig_b) in zip(dated, dated[1:]):
        if date_b < date_a:
            violations.append(
                f"'{role_b}' dated {date_b.isoformat()} precedes "
                f"'{role_a}' dated {date_a.isoformat()}"
            )
            evidence.extend(
                Evidence(
                    document=facts.source.filename,
                    doc_type=facts.doc_type,
                    page=sig.page,
                    field=f"signatories[{role}].date",
                    value=sig.date,
                )
                for role, sig in ((role_a, sig_a), (role_b, sig_b))
            )

    if not violations:
        return Outcome.ok(
            f"Signature dates follow the prescribed order across {len(dated)} block(s)."
        )
    return Outcome.fail(f"Approval sequence violated - {'; '.join(violations)}.", evidence)


# -- arithmetic ------------------------------------------------------------


def arithmetic_sum(facts: DocumentFacts, params: Dict) -> Outcome:
    """`result` must equal the sum of `add` minus the sum of `subtract`.

    Deductions absent from the document are treated as zero rather than
    skipping the check: a voucher with no withholding tax line genuinely has
    no withholding tax, and the net must still reconcile.
    """
    result_path = params["result"]
    tolerance = float(params.get("tolerance", 0.01))

    result = parse_amount(facts.get_path(result_path))
    if result is None:
        return Outcome.skip(f"'{result_path}' is absent; arithmetic not verifiable.")

    total = 0.0
    used: List[str] = []
    for path in params.get("add", []):
        value = parse_amount(facts.get_path(path))
        if value is not None:
            total += value
            used.append(f"+{path}={format_amount(value)}")
    for path in params.get("subtract", []):
        value = parse_amount(facts.get_path(path))
        if value is not None:
            total -= value
            used.append(f"-{path}={format_amount(value)}")

    if not used:
        return Outcome.skip("None of the operand fields are present.")

    if abs(total - result) <= tolerance:
        return Outcome.ok(
            f"{result_path} = {format_amount(result)} reconciles ({' '.join(used)})."
        )

    return Outcome.fail(
        f"Arithmetic does not reconcile: {' '.join(used)} = {format_amount(total)}, "
        f"but {result_path} states {format_amount(result)} "
        f"(difference {format_amount(abs(total - result))}).",
        [_evidence(facts, result_path, format_amount(result))],
    )


def line_item_arithmetic(facts: DocumentFacts, params: Dict) -> Outcome:
    """Each line item's amount must equal quantity x unit price."""
    tolerance = float(params.get("tolerance", 0.01))
    if not facts.items:
        return Outcome.skip("Document has no line items.")

    errors: List[str] = []
    evidence: List[Evidence] = []
    checked = 0

    for index, item in enumerate(facts.items, start=1):
        if item.qty is None or item.unit_price is None or item.amount is None:
            continue
        checked += 1
        expected = item.qty * item.unit_price
        if abs(expected - item.amount) > tolerance:
            errors.append(
                f"item {index} ({item.description[:40]}): {item.qty} x "
                f"{format_amount(item.unit_price)} = {format_amount(expected)}, "
                f"but the document states {format_amount(item.amount)}"
            )
            evidence.append(
                Evidence(
                    document=facts.source.filename,
                    doc_type=facts.doc_type,
                    page=item.page,
                    field=f"items[{index}].amount",
                    value=format_amount(item.amount),
                )
            )

    if not checked:
        return Outcome.skip("No line item has quantity, unit price and amount together.")
    if not errors:
        return Outcome.ok(f"All {checked} priced line item(s) compute correctly.")
    return Outcome.fail(f"Line item extension error(s): {'; '.join(errors)}.", evidence)


def items_total_matches(facts: DocumentFacts, params: Dict) -> Outcome:
    """The document total must equal the sum of its line items."""
    total_path = params.get("total", "amounts.total")
    tolerance = float(params.get("tolerance", 0.01))

    stated = parse_amount(facts.get_path(total_path))
    if stated is None:
        return Outcome.skip(f"'{total_path}' is absent.")

    amounts = [item.amount for item in facts.items if item.amount is not None]
    if not amounts:
        return Outcome.skip("No line item carries an amount.")

    computed = sum(amounts)
    if abs(computed - stated) <= tolerance:
        return Outcome.ok(
            f"{total_path} ({format_amount(stated)}) equals the sum of "
            f"{len(amounts)} line item(s)."
        )
    return Outcome.fail(
        f"Line items sum to {format_amount(computed)} across {len(amounts)} item(s), "
        f"but {total_path} states {format_amount(stated)} "
        f"(difference {format_amount(abs(computed - stated))}).",
        [_evidence(facts, total_path, format_amount(stated))],
    )


def cross_field_equal(facts: DocumentFacts, params: Dict) -> Outcome:
    """Two fields on the same document must agree."""
    path_a, path_b = params["a"], params["b"]
    tolerance = float(params.get("tolerance", 0.01))

    raw_a, raw_b = facts.get_path(path_a), facts.get_path(path_b)
    if is_blank(raw_a) or is_blank(raw_b):
        return Outcome.skip(f"'{path_a}' or '{path_b}' is absent.")

    num_a, num_b = parse_amount(raw_a), parse_amount(raw_b)
    if num_a is not None and num_b is not None:
        if abs(num_a - num_b) <= tolerance:
            return Outcome.ok(f"{path_a} and {path_b} agree at {format_amount(num_a)}.")
        return Outcome.fail(
            f"{path_a} is {format_amount(num_a)} but {path_b} is "
            f"{format_amount(num_b)} (difference {format_amount(abs(num_a - num_b))}).",
            [_evidence(facts, path_a, raw_a), _evidence(facts, path_b, raw_b)],
        )

    if normalize(raw_a) == normalize(raw_b):
        return Outcome.ok(f"{path_a} and {path_b} agree.")
    return Outcome.fail(
        f"{path_a} is '{raw_a}' but {path_b} is '{raw_b}'.",
        [_evidence(facts, path_a, raw_a), _evidence(facts, path_b, raw_b)],
    )


def amount_in_words_matches(facts: DocumentFacts, params: Dict) -> Outcome:
    """The amount in words must match the amount in figures.

    Where they disagree, IRR Section 61.2.3 makes the words control -- so
    this is not a typo, it changes what the document legally says is payable.
    """
    figures_path = params.get("figures", "amounts.net")
    tolerance = float(params.get("tolerance", 0.01))

    figures = parse_amount(facts.get_path(figures_path))
    words_text = facts.amount_in_words
    if figures is None:
        return Outcome.skip(f"'{figures_path}' is absent.")
    if is_blank(words_text):
        return Outcome.fail(
            "The amount in words is blank; it cannot be reconciled against "
            f"the figure of {format_amount(figures)}.",
            [_evidence(facts, "amount_in_words")],
        )

    words_value = parse_amount_in_words(words_text)
    if words_value is None:
        return Outcome.skip(
            f"The amount in words ('{str(words_text)[:60]}') could not be parsed; "
            "verify manually."
        )

    if abs(words_value - figures) <= tolerance:
        return Outcome.ok(
            f"Amount in words matches the figure of {format_amount(figures)}."
        )
    return Outcome.fail(
        f"The amount in words reads {format_amount(words_value)} "
        f"('{str(words_text)[:70]}') but {figures_path} states "
        f"{format_amount(figures)}.",
        [
            _evidence(facts, "amount_in_words", words_text),
            _evidence(facts, figures_path, format_amount(figures)),
        ],
    )


# -- dates and thresholds --------------------------------------------------


def date_order(facts: DocumentFacts, params: Dict) -> Outcome:
    """Dates must occur in the prescribed order.

    Only dates actually present are compared, so a document missing an
    inspection date still has its delivery-to-acceptance order checked.
    """
    sequence = params.get("sequence", [])
    allow_same_day = params.get("allow_same_day", True)

    resolved: List[tuple] = []
    unparseable: List[str] = []
    for path in sequence:
        raw = facts.get_path(path)
        if is_blank(raw):
            continue
        parsed = parse_date(raw)
        if parsed is None:
            unparseable.append(f"{path}='{raw}'")
            continue
        resolved.append((path, parsed, raw))

    if len(resolved) < 2:
        reason = "Fewer than two dates in this sequence are present"
        if unparseable:
            reason += f"; could not parse {', '.join(unparseable)}"
        return Outcome.skip(reason + ".")

    violations: List[str] = []
    evidence: List[Evidence] = []
    for (path_a, date_a, raw_a), (path_b, date_b, raw_b) in zip(resolved, resolved[1:]):
        out_of_order = date_b < date_a if allow_same_day else date_b <= date_a
        if out_of_order:
            violations.append(
                f"{path_b} ({raw_b}) precedes {path_a} ({raw_a})"
            )
            evidence.extend(
                [_evidence(facts, path_a, raw_a), _evidence(facts, path_b, raw_b)]
            )

    if not violations:
        return Outcome.ok(
            f"Dates are in the expected order: "
            f"{' -> '.join(f'{p}={d.isoformat()}' for p, d, _ in resolved)}."
        )
    return Outcome.fail(f"Dates out of sequence - {'; '.join(violations)}.", evidence)


_OPS: Dict[str, Callable[[float, float], bool]] = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: abs(a - b) < 0.01,
    "ne": lambda a, b: abs(a - b) >= 0.01,
}


def threshold_compare(facts: DocumentFacts, params: Dict) -> Outcome:
    """Compare a numeric field against a fixed threshold or another field."""
    path = params["field"]
    op = params.get("op", "lte")
    value = parse_amount(facts.get_path(path))
    if value is None:
        return Outcome.skip(f"'{path}' is absent or non-numeric.")

    if "value" in params:
        limit = float(params["value"])
        limit_label = format_amount(limit)
    else:
        other = params["other_field"]
        limit = parse_amount(facts.get_path(other))
        if limit is None:
            return Outcome.skip(f"'{other}' is absent or non-numeric.")
        limit_label = f"{other} ({format_amount(limit)})"

    comparator = _OPS.get(op)
    if comparator is None:
        return Outcome.skip(f"Unknown comparison operator '{op}'.")

    if comparator(value, limit):
        return Outcome.ok(f"{path} ({format_amount(value)}) {op} {limit_label}.")
    return Outcome.fail(
        f"{path} is {format_amount(value)}, which fails the requirement "
        f"'{op} {limit_label}'.",
        [_evidence(facts, path, format_amount(value))],
    )


def regex_match(facts: DocumentFacts, params: Dict) -> Outcome:
    """A field must match a pattern -- used for reference-number formats."""
    import re

    path = params["field"]
    pattern = params["pattern"]
    raw = facts.get_path(path)
    if is_blank(raw):
        return Outcome.skip(f"'{path}' is absent.")
    if re.search(pattern, str(raw), re.IGNORECASE):
        return Outcome.ok(f"{path} ('{raw}') matches the expected format.")
    return Outcome.fail(
        f"{path} is '{raw}', which does not match the expected format "
        f"({params.get('format_description', pattern)}).",
        [_evidence(facts, path, raw)],
    )


def any_field_present(facts: DocumentFacts, params: Dict) -> Outcome:
    """At least one of a set of alternative fields must be filled.

    A delivery can be evidenced by a Delivery Receipt number or a contract
    number; requiring both would report a false deficiency.
    """
    options = params.get("fields", [])
    found = [p for p in options if not is_blank(facts.get_path(p))]
    if found:
        return Outcome.ok(f"Present: {', '.join(found)}.")
    return Outcome.fail(
        f"At least one of these must be present, and none are: {', '.join(options)}.",
        [_evidence(facts, options[0])] if options else [],
    )


def value_in_set(facts: DocumentFacts, params: Dict) -> Outcome:
    """A field's value must be one of an allowed set (e.g. modes of procurement)."""
    path = params["field"]
    allowed = params.get("allowed", [])
    raw = facts.get_path(path)
    if is_blank(raw):
        return Outcome.skip(f"'{path}' is absent.")

    normalized_allowed = {normalize(a): a for a in allowed}
    needle = normalize(raw)
    for key, original in normalized_allowed.items():
        if key and (key in needle or needle in key):
            return Outcome.ok(f"{path} is '{raw}', a recognised value ({original}).")
    return Outcome.fail(
        f"{path} is '{raw}', which is not among the values recognised under "
        f"RA 12009: {', '.join(allowed)}.",
        [_evidence(facts, path, raw)],
    )


def classification_confident(facts: DocumentFacts, params: Dict) -> Outcome:
    """The document must have been recognised as a known procurement form.

    An unrecognised document is a gap in coverage, not a compliance defect --
    but it has to be surfaced, because silently applying no checks to a file
    the user uploaded looks identical to finding nothing wrong with it.
    """
    minimum = float(params.get("min_confidence", 0.5))

    if facts.doc_type == "other":
        return Outcome.fail(
            "The document type could not be determined, so no type-specific "
            "checks were applied to this file.",
            [_evidence(facts, "doc_type", facts.doc_type)],
        )
    if facts.doc_type_confidence < minimum:
        return Outcome.fail(
            f"Classified as '{facts.type_label}' with low confidence "
            f"({facts.doc_type_confidence:.0%}); the checks applied to it may "
            "be the wrong ones.",
            [_evidence(facts, "doc_type", facts.doc_type)],
        )
    return Outcome.ok(
        f"Recognised as {facts.type_label} "
        f"({facts.doc_type_confidence:.0%} confidence)."
    )


def text_absent(facts: DocumentFacts, params: Dict) -> Outcome:
    """Prohibited wording must not appear in the listed fields.

    This catches brand-name specification, the classic restrictive-
    specification finding, without needing a model.
    """
    phrases = params.get("phrases", [])
    paths = params.get("fields", ["items[].description", "deliverables"])

    hits: List[str] = []
    evidence: List[Evidence] = []
    for path in paths:
        for value in as_list(facts.get_path(path)):
            if value is None:
                continue
            haystack = str(value).lower()
            for phrase in phrases:
                if phrase.lower() in haystack:
                    hits.append(f"'{phrase}' in {path}: \"{str(value)[:60]}\"")
                    evidence.append(_evidence(facts, path, str(value)[:120]))

    if not hits:
        return Outcome.ok(f"None of the {len(phrases)} prohibited phrase(s) appear.")
    return Outcome.fail(
        f"Prohibited wording found - {'; '.join(hits[:5])}.", evidence[:5]
    )


# Registry. `engine.py` dispatches a rule's `check:` key through this.
PRIMITIVES: Dict[str, Callable[[DocumentFacts, Dict], Outcome]] = {
    "field_present": field_present,
    "any_field_present": any_field_present,
    "items_present": items_present,
    "item_field_present": item_field_present,
    "attachment_present": attachment_present,
    "signatory_present": signatory_present,
    "signatory_order": signatory_order,
    "arithmetic_sum": arithmetic_sum,
    "line_item_arithmetic": line_item_arithmetic,
    "items_total_matches": items_total_matches,
    "cross_field_equal": cross_field_equal,
    "amount_in_words_matches": amount_in_words_matches,
    "date_order": date_order,
    "threshold_compare": threshold_compare,
    "regex_match": regex_match,
    "value_in_set": value_in_set,
    "text_absent": text_absent,
    "classification_confident": classification_confident,
}
