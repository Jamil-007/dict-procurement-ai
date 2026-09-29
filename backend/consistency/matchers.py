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


def person_name(left: Any, right: Any, params: Dict) -> MatchResult:
    """Two names that must denote the same person.

    The receiving officer is "JUAN D. CRUZ" on the delivery receipt, "Cruz,
    Juan D." on the PAR and "J. D. Cruz" on the ICS, and all three are one
    person. A `fuzzy` comparison gets this wrong in both directions: it
    scores those three low because the word order differs, and it scores
    "Juan D. Cruz" against "Juan D. Cruzada" high because the strings barely
    differ. So the words are compared as a set, honorifics and suffixes are
    dropped, and a single letter is allowed to stand for a word beginning
    with it.
    """
    if not _both_present(left, right):
        return MatchResult.not_comparable()

    a, b = _name_parts(str(left)), _name_parts(str(right))
    if not a.words or not b.words:
        return MatchResult.not_comparable()

    if a.words == b.words:
        return MatchResult.same(f"both '{left}'")

    # Compare from the sparser side: "J. D. Cruz" carries less information
    # than "Juan Dela Cruz", and it is the sparser name that must be
    # accounted for by the fuller one, not the other way round.
    fewer, more = (a, b) if len(a.words) <= len(b.words) else (b, a)
    unmatched = [w for w in fewer.words if not _name_word_matches(w, more)]
    if not unmatched:
        return MatchResult.same(f"'{left}' and '{right}' name the same person")
    return MatchResult.differ(f"'{left}' vs '{right}'")


def address_equivalent(left: Any, right: Any, params: Dict) -> MatchResult:
    """Two places that must be the same place.

    Addresses on Philippine procurement documents are written at whatever
    length the form allows: the contract says "DICT Building, C.P. Garcia
    Avenue, Diliman, Quezon City" and the delivery receipt says "DICT Bldg.,
    Diliman, Q.C.". Those agree. "DICT Regional Office IV-A, Calamba" does
    not, and delivering to the wrong place is the finding -- goods signed for
    somewhere other than the contracted point of delivery are outside the
    contract even when everything else about them is right.

    Abbreviations are expanded, filler words dropped, and what remains
    compared as a set. Digits are treated separately: a building or unit
    number that disagrees is a different address however much of the rest
    lines up.
    """
    threshold = float(params.get("threshold", 0.70))
    if not _both_present(left, right):
        return MatchResult.not_comparable()

    a, b = _address_tokens(str(left)), _address_tokens(str(right))
    if not a or not b:
        return MatchResult.not_comparable()

    a_nums, b_nums = _address_numbers(a), _address_numbers(b)
    if a_nums and b_nums and not (a_nums & b_nums):
        return MatchResult.differ(
            f"'{left}' vs '{right}' (floor, unit or building numbers do not match)"
        )

    overlap = len(a & b) / min(len(a), len(b))
    if overlap >= threshold:
        return MatchResult.same(f"'{left}' and '{right}' describe the same place")
    return MatchResult.differ(f"'{str(left)[:70]}' vs '{str(right)[:70]}'")


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


# Titles and generational suffixes are not part of who someone is, and the
# same officer carries them on one form and not on the next.
_NAME_NOISE = frozenset(
    {
        "mr", "mrs", "ms", "miss", "sir", "madam", "dr", "engr", "atty", "arch",
        "hon", "gen", "col", "capt", "prof", "rev",
        "jr", "sr", "ii", "iii", "iv", "v",
        "cpa", "ceso", "md", "rn", "phd", "mba", "llb",
        "dela", "de", "del", "los", "las", "y", "van", "von",
    }
)


@dataclass
class _NameParts:
    """A name split into whole words and bare initials."""

    words: frozenset
    initials: frozenset


def _name_parts(text: str) -> _NameParts:
    import re

    # Hyphens split: "Santos-Reyes" is one surname on the form that signed
    # for the goods and two words on the one that accepted them.
    tokens = [normalize(t) for t in re.split(r"[\s,.\-]+", text) if t.strip()]
    kept = [t for t in tokens if t and t not in _NAME_NOISE]
    return _NameParts(
        words=frozenset(t for t in kept if len(t) > 1),
        initials=frozenset(t for t in kept if len(t) == 1),
    )


def _name_word_matches(word: str, other: _NameParts) -> bool:
    if word in other.words:
        return True
    if word[0] in other.initials:
        return True
    # A single transcription slip off a scan -- "Bermudes" for "Bermudez" --
    # must not read as a different person. One edit, and only in a word long
    # enough that one edit cannot turn it into an unrelated name: "Cruz" and
    # "Cruzada" are four edits apart and stay distinct, but so would "Cruz"
    # and "Cruzs" be if it were allowed to count.
    if len(word) < 6:
        return False
    return any(_within_one_edit(word, candidate) for candidate in other.words)


def _within_one_edit(a: str, b: str) -> bool:
    """Whether `a` and `b` differ by at most one character."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(longer)):
        if longer[:i] + longer[i + 1 :] == shorter:
            return True
    return False


# Written one way on the contract and another on the receipt, always.
_ADDRESS_ABBREVIATIONS = {
    "st": "street", "str": "street", "sts": "street",
    "ave": "avenue", "av": "avenue",
    "rd": "road", "blvd": "boulevard", "hwy": "highway",
    "bldg": "building", "bldng": "building", "bldgs": "building",
    "flr": "floor", "fl": "floor", "f": "floor",
    "rm": "room", "unit": "unit",
    "brgy": "barangay", "bgy": "barangay", "bry": "barangay",
    "subd": "subdivision", "compd": "compound", "cmpd": "compound",
    "ext": "extension", "cor": "corner",
    "qc": "quezoncity", "mla": "manila", "ncr": "nationalcapitalregion",
    "prov": "province", "mun": "municipality", "brb": "barangay",
}

# Words that appear in every address and distinguish none of them.
_ADDRESS_NOISE = frozenset(
    {"no", "nos", "number", "the", "of", "and", "at", "in", "near", "philippines", "ph"}
)


def _address_tokens(text: str) -> frozenset:
    import re

    tokens: List[str] = []
    for raw in re.split(r"[\s,./\\-]+", text):
        token = normalize(raw)
        if not token or token in _ADDRESS_NOISE:
            continue
        tokens.append(_ADDRESS_ABBREVIATIONS.get(token, token))
    # "Quezon City" and "Q.C." have to reach the same token, so the pair is
    # joined after expansion rather than being matched as two loose words.
    joined = " ".join(tokens)
    for phrase, single in (("quezon city", "quezoncity"), ("metro manila", "metromanila")):
        joined = joined.replace(phrase, single)
    return frozenset(joined.split())


def _address_numbers(tokens: frozenset) -> frozenset:
    """The floor, unit and building numbers in an address.

    Read off the front of a token rather than requiring the whole token to
    be digits, because a floor is written "3rd" as often as "3" and the two
    have to reach the same number. A postal code would be picked up here
    too; in practice these forms carry floors and unit numbers far more
    often than postal codes, and a floor that disagrees is the finding.
    """
    import re

    numbers = set()
    for token in tokens:
        match = re.match(r"(\d+)", token)
        if match:
            numbers.add(match.group(1))
    return frozenset(numbers)


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
    "person_name": person_name,
    "address_equivalent": address_equivalent,
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
