"""How two values from two different documents are compared.

Every comparison in the consistency engine resolves to one of these. They are
deliberately deterministic: whether the delivery receipt says 25 units and the
contract says 20 is arithmetic, and a language model asked to scan a hundred
scanned pages for "any inconsistencies" will find some real ones, invent
others, and give no account of which is which.

The model's job comes afterwards -- explaining why a confirmed discrepancy
matters and what remedy it calls for. Finding it is this module's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence

from rules.parsing import format_amount, is_blank, normalize, parse_amount, parse_date


@dataclass
class MatchResult:
    """The outcome of comparing one field across two documents."""

    agree: bool
    detail: str = ""
    # None when the comparison could not be made -- a field absent on one
    # side is not evidence of a discrepancy, and reporting it as one is how
    # a checker earns a reputation for crying wolf.
    comparable: bool = True

    @classmethod
    def same(cls, detail: str = "") -> "MatchResult":
        return cls(True, detail)

    @classmethod
    def differ(cls, detail: str) -> "MatchResult":
        return cls(False, detail)

    @classmethod
    def not_comparable(cls, detail: str = "") -> "MatchResult":
        return cls(True, detail, comparable=False)


def _both_present(left: Any, right: Any) -> bool:
    return not is_blank(left) and not is_blank(right)


# -- scalar matchers -------------------------------------------------------


def exact(left: Any, right: Any, params: Dict) -> MatchResult:
    """Character-for-character equality."""
    if not _both_present(left, right):
        return MatchResult.not_comparable()
    if str(left) == str(right):
        return MatchResult.same(f"both '{left}'")
    return MatchResult.differ(f"'{left}' vs '{right}'")


def normalized_exact(left: Any, right: Any, params: Dict) -> MatchResult:
    """Equality after case-folding, punctuation and whitespace normalisation.

    The right comparison for reference numbers, which are written
    DICT-GECS-2024-001, DICT GECS 2024 001 and dict/gecs/2024/001 across three
    documents in the same packet and mean the same thing every time.
    """
    if not _both_present(left, right):
        return MatchResult.not_comparable()
    if normalize(left) == normalize(right):
        return MatchResult.same(f"both '{left}'")
    return MatchResult.differ(f"'{left}' vs '{right}'")


def fuzzy(left: Any, right: Any, params: Dict) -> MatchResult:
    """Approximate string equality, for descriptions transcribed by hand.

    Item descriptions drift between documents in ways that do not matter
    ("w/ power supply" vs "with power supply") and in ways that do ("50W" vs
    "25W"). The threshold separates the two; it defaults high because a
    description that has genuinely changed is the finding T5 and T6 exist for.
    """
    threshold = float(params.get("threshold", 0.85))
    if not _both_present(left, right):
        return MatchResult.not_comparable()

    score = similarity(str(left), str(right))
    if score >= threshold:
        return MatchResult.same(f"{score:.0%} similar")
    return MatchResult.differ(
        f"'{str(left)[:70]}' vs '{str(right)[:70]}' ({score:.0%} similar)"
    )


def numeric_tolerance(left: Any, right: Any, params: Dict) -> MatchResult:
    """Numeric equality within an absolute tolerance."""
    tolerance = float(params.get("tolerance", 0.01))
    a, b = parse_amount(left), parse_amount(right)
    if a is None or b is None:
        return MatchResult.not_comparable()
    if abs(a - b) <= tolerance:
        return MatchResult.same(f"both {format_amount(a)}")
    return MatchResult.differ(
        f"{format_amount(a)} vs {format_amount(b)} "
        f"(difference {format_amount(abs(a - b))})"
    )


def numeric_not_exceeding(left: Any, right: Any, params: Dict) -> MatchResult:
    """`right` must not exceed `left` -- e.g. paid must not exceed contracted.

    Asymmetric on purpose. Paying less than the contract amount is a partial
    payment; paying more is an unauthorised disbursement, and only the second
    is a finding.
    """
    tolerance = float(params.get("tolerance", 0.01))
    a, b = parse_amount(left), parse_amount(right)
    if a is None or b is None:
        return MatchResult.not_comparable()
    if b <= a + tolerance:
        return MatchResult.same(f"{format_amount(b)} within {format_amount(a)}")
    return MatchResult.differ(
        f"{format_amount(b)} exceeds {format_amount(a)} by "
        f"{format_amount(b - a)}"
    )


def date_within(left: Any, right: Any, params: Dict) -> MatchResult:
    """Two dates must fall within `days` of each other."""
    window = int(params.get("days", 0))
    a, b = parse_date(left), parse_date(right)
    if a is None or b is None:
        return MatchResult.not_comparable()
    gap = abs((b - a).days)
    if gap <= window:
        return MatchResult.same(f"{a.isoformat()} and {b.isoformat()}, {gap} day(s) apart")
    return MatchResult.differ(
        f"{a.isoformat()} vs {b.isoformat()} ({gap} days apart, "
        f"tolerance is {window})"
    )


def date_not_before(left: Any, right: Any, params: Dict) -> MatchResult:
    """`right` must not fall before `left`.

    Acceptance before delivery, or delivery before the notice to proceed, are
    the sequencing failures this catches across documents -- the single
    document version lives in `rules.primitives.date_order`.
    """
    a, b = parse_date(left), parse_date(right)
    if a is None or b is None:
        return MatchResult.not_comparable()
    if b >= a:
        return MatchResult.same(f"{b.isoformat()} follows {a.isoformat()}")
    return MatchResult.differ(
        f"{b.isoformat()} precedes {a.isoformat()} by {(a - b).days} day(s)"
    )


def date_not_after(left: Any, right: Any, params: Dict) -> MatchResult:
    """`right` must not fall after `left` -- e.g. delivery after its due date."""
    grace = int(params.get("days", 0))
    a, b = parse_date(left), parse_date(right)
    if a is None or b is None:
        return MatchResult.not_comparable()
    if (b - a).days <= grace:
        return MatchResult.same(f"{b.isoformat()} is within {a.isoformat()}")
    return MatchResult.differ(
        f"{b.isoformat()} is {(b - a).days} day(s) after {a.isoformat()}"
    )


# -- collection matchers ---------------------------------------------------


def serial_set(left: Any, right: Any, params: Dict) -> MatchResult:
    """Serial numbers recorded on two documents must describe the same units.

    Serials are normalised before comparison because the same unit is written
    NBT-VHF-24001 on the delivery receipt and NBT VHF 24001 on the PAR often
    enough that a literal comparison would report every packet as defective.
    """
    # Keep the serial as it was written so the finding quotes what a reviewer
    # will actually read off the page, not the normalised comparison key.
    left_map = {normalize(s): s for s in _as_str_list(left) if normalize(s)}
    right_map = {normalize(s): s for s in _as_str_list(right) if normalize(s)}
    if not left_map or not right_map:
        return MatchResult.not_comparable()

    only_left = set(left_map) - set(right_map)
    only_right = set(right_map) - set(left_map)
    if not only_left and not only_right:
        return MatchResult.same(f"{len(left_map)} serial(s) match")

    parts: List[str] = []
    if only_left:
        sample = ", ".join(sorted(left_map[k] for k in only_left)[:3])
        parts.append(
            f"{len(only_left)} serial(s) on the reference document are absent "
            f"from the other ({sample})"
        )
    if only_right:
        sample = ", ".join(sorted(right_map[k] for k in only_right)[:3])
        parts.append(
            f"{len(only_right)} serial(s) appear only on the other document "
            f"({sample})"
        )
    return MatchResult.differ("; ".join(parts))


def list_covers(left: Any, right: Any, params: Dict) -> MatchResult:
    """Every entry on the left must have a counterpart on the right.

    Directional: the TOR's deliverables must all appear in the bidding
    documents, but the bidding documents may add boilerplate the TOR omits.
    A requirement that quietly disappears between the two is the T6 finding.
    """
    threshold = float(params.get("threshold", 0.75))
    left_items = [str(v) for v in _as_str_list(left) if not is_blank(v)]
    right_items = [str(v) for v in _as_str_list(right) if not is_blank(v)]
    if not left_items or not right_items:
        return MatchResult.not_comparable()

    dropped = [
        entry
        for entry in left_items
        if max((similarity(entry, other) for other in right_items), default=0.0) < threshold
    ]
    if not dropped:
        return MatchResult.same(f"all {len(left_items)} entries are carried over")
    shown = "; ".join(f'"{d[:70]}"' for d in dropped[:3])
    more = f" and {len(dropped) - 3} more" if len(dropped) > 3 else ""
    return MatchResult.differ(
        f"{len(dropped)} of {len(left_items)} entries have no counterpart: {shown}{more}"
    )


def text_equivalent(left: Any, right: Any, params: Dict) -> MatchResult:
    """Free-text clauses that must say the same thing.

    Used for delivery periods and warranty terms, where "Ninety (90) calendar
    days" and "90 calendar days" agree but "Sixty (60) calendar days" does
    not. Numbers found in the text are compared first, because that is where
    the disagreement always is.
    """
    threshold = float(params.get("threshold", 0.80))
    if not _both_present(left, right):
        return MatchResult.not_comparable()

    left_nums, right_nums = _numbers_in(str(left)), _numbers_in(str(right))
    if left_nums and right_nums and left_nums != right_nums:
        return MatchResult.differ(f"'{left}' vs '{right}'")

    score = similarity(str(left), str(right))
    if score >= threshold:
        return MatchResult.same(f"{score:.0%} similar")
    return MatchResult.differ(f"'{str(left)[:70]}' vs '{str(right)[:70]}'")


# -- support ---------------------------------------------------------------


def similarity(a: str, b: str) -> float:
    """Normalised similarity in [0, 1]. Falls back if rapidfuzz is absent."""
    left, right = normalize(a), normalize(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    try:
        from rapidfuzz import fuzz

        return fuzz.token_set_ratio(left, right) / 100.0
    except ImportError:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, left, right).ratio()


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        flat: List[str] = []
        for entry in value:
            if isinstance(entry, (list, tuple, set)):
                flat.extend(str(sub) for sub in entry)
            elif entry is not None:
                flat.append(str(entry))
        return flat
    return [str(value)]


def _numbers_in(text: str) -> List[str]:
    """Digits in a clause, ignoring the spelled-out duplicate in parentheses."""
    import re

    return re.findall(r"\d+(?:\.\d+)?", text)


MATCHERS: Dict[str, Callable[[Any, Any, Dict], MatchResult]] = {
    "exact": exact,
    "normalized_exact": normalized_exact,
    "fuzzy": fuzzy,
    "numeric_tolerance": numeric_tolerance,
    "numeric_not_exceeding": numeric_not_exceeding,
    "date_within": date_within,
    "date_not_before": date_not_before,
    "date_not_after": date_not_after,
    "serial_set": serial_set,
    "list_covers": list_covers,
    "text_equivalent": text_equivalent,
}


# -- line item alignment ---------------------------------------------------


@dataclass
class ItemPair:
    """Two line items from two documents judged to be the same item."""

    left_index: int
    right_index: int
    left: Any
    right: Any
    score: float


def align_items(
    left_items: Sequence,
    right_items: Sequence,
    threshold: float = 0.70,
) -> tuple:
    """Pair line items across two documents.

    Returns `(pairs, unmatched_left, unmatched_right)`.

    Alignment is by description similarity, with the line number breaking
    ties. This has to be right before any field can be compared: pairing the
    wrong two rows produces a confident report that 25 transceivers were
    delivered as 60 handhelds.
    """
    pairs: List[ItemPair] = []
    taken: set = set()

    scored: List[tuple] = []
    for i, left in enumerate(left_items):
        for j, right in enumerate(right_items):
            score = similarity(
                getattr(left, "description", "") or "",
                getattr(right, "description", "") or "",
            )
            left_no = str(getattr(left, "line_no", "") or "")
            right_no = str(getattr(right, "line_no", "") or "")
            if left_no and left_no == right_no:
                score = min(1.0, score + 0.05)
            scored.append((score, i, j))

    # Greedy: best pair first, then the best remaining, and so on. Adequate
    # at the size of a real schedule of requirements and, unlike a global
    # optimum, explainable when someone asks why two rows were paired.
    for score, i, j in sorted(scored, key=lambda t: -t[0]):
        if score < threshold:
            break
        if any(p.left_index == i for p in pairs) or j in taken:
            continue
        pairs.append(ItemPair(i, j, left_items[i], right_items[j], score))
        taken.add(j)

    matched_left = {p.left_index for p in pairs}
    unmatched_left = [i for i in range(len(left_items)) if i not in matched_left]
    unmatched_right = [j for j in range(len(right_items)) if j not in taken]
    return sorted(pairs, key=lambda p: p.left_index), unmatched_left, unmatched_right
