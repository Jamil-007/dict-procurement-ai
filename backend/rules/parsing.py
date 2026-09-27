"""Parsing helpers shared by the rule and consistency engines.

Procurement documents are written by people, so the same value appears as
"1,250,000.00", "P1,250,000.00" and "(1,250,000.00)"; the same date as
"12/04/2024", "December 4, 2024" and "04-DEC-24". Normalising here keeps
every check in both engines comparing like with like.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, List, Optional

# -- amounts ---------------------------------------------------------------

_CURRENCY_CHARS = "₱P$Php PHP"
_AMOUNT_CLEAN_RE = re.compile(r"[^\d.\-()]")


def parse_amount(value: Any) -> Optional[float]:
    """Parse a peso amount from a string or number.

    Accounting parentheses mean negative: "(1,200.00)" is -1200.0.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")")
    text = _AMOUNT_CLEAN_RE.sub("", text).strip("()")
    if not text or text in {"-", "."}:
        return None

    try:
        amount = float(text)
    except ValueError:
        return None
    return -amount if negative else amount


def format_amount(value: Optional[float]) -> str:
    """Render an amount the way the documents do."""
    if value is None:
        return "(absent)"
    return f"{value:,.2f}"


# -- amount in words -------------------------------------------------------

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_IGNORED_WORDS = {"and", "only", "pesos", "peso", "philippine", "currency", "the", "of"}


def parse_amount_in_words(text: Optional[str]) -> Optional[float]:
    """Parse an English amount-in-words string into a number.

    Handles the form Philippine vouchers use:
    "ONE MILLION TWO HUNDRED FIFTY THOUSAND PESOS AND 50/100 ONLY".
    Returns None when the string cannot be parsed, which a rule should treat
    as "could not verify", never as a mismatch.
    """
    if not text:
        return None

    cleaned = str(text).lower().replace("-", " ").replace(",", " ")

    # Centavos are written as a fraction: "and 50/100 only".
    centavos = 0.0
    fraction = re.search(r"(\d{1,2})\s*/\s*100", cleaned)
    if fraction:
        centavos = int(fraction.group(1)) / 100.0
        cleaned = cleaned[: fraction.start()] + cleaned[fraction.end() :]

    total = 0
    current = 0
    saw_number = False

    for word in re.findall(r"[a-z]+", cleaned):
        if word in _IGNORED_WORDS:
            continue
        if word in _UNITS:
            current += _UNITS[word]
            saw_number = True
        elif word in _TENS:
            current += _TENS[word]
            saw_number = True
        elif word == "hundred":
            current = (current or 1) * 100
            saw_number = True
        elif word in _SCALES:
            total += (current or 1) * _SCALES[word]
            current = 0
            saw_number = True
        else:
            # An unknown word means this is not a plain amount-in-words
            # string; refusing to guess is safer than a false mismatch.
            return None

    if not saw_number:
        return None
    return float(total + current) + centavos


# -- dates -----------------------------------------------------------------

_DATE_FORMATS = [
    "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d/%m/%Y", "%d-%m-%Y",
    "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
    "%d %B %Y", "%d %b %Y",
    "%d-%b-%Y", "%d%b%Y", "%d-%B-%Y",
    "%m/%d/%y", "%d-%b-%y", "%b %d, %y",
]

_ORDINAL_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)


def parse_date(value: Any) -> Optional[date]:
    """Parse a date written in any of the forms these documents use.

    Ambiguous numeric dates are read as MM/DD/YYYY, the Philippine
    government standard. Returns None rather than guessing when nothing fits.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    text = _ORDINAL_RE.sub(r"\1", text)
    text = re.sub(r"[^\w\s/.,-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().strip(",")

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # Last resort: pull a recognisable date out of a longer phrase such as
    # "signed this 4th day of December 2024".
    match = re.search(
        r"(\d{1,2})\s+(?:day\s+of\s+)?([A-Za-z]{3,9})\.?,?\s+(\d{4})", text
    )
    if match:
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(
                    f"{match.group(1)} {match.group(2)} {match.group(3)}", fmt
                ).date()
            except ValueError:
                continue
    return None


def format_date(value: Optional[date]) -> str:
    return value.isoformat() if value else "(unparseable)"


# -- text ------------------------------------------------------------------

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: Any) -> str:
    """Casefold and strip punctuation, for tolerant identifier comparison.

    "PR No. 2024-11-0453" and "pr-2024-11-0453" normalise to the same string,
    which is what lets a reference number be matched across documents that
    format it differently.
    """
    if text is None:
        return ""
    return _NORMALIZE_RE.sub("", str(text).lower())


_REF_NUMBER_RE = re.compile(r"[A-Za-z]*[-\s]?\d[\d\-/]{2,}[A-Za-z0-9]*")


def extract_reference_numbers(text: Any) -> List[str]:
    """Pull candidate reference numbers out of a free-text field."""
    if not text:
        return []
    return [m.group(0).strip() for m in _REF_NUMBER_RE.finditer(str(text))]


def as_list(value: Any) -> List[Any]:
    """Coerce a scalar, None or list into a list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value]
    return [value]


def is_blank(value: Any) -> bool:
    """Whether a field counts as absent.

    An empty list, an empty string, and a string of placeholder dashes all
    mean the same thing on a government form: the field was not filled in.
    """
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped in {"-", "--", "N/A", "n/a", "NA", "None", "_"}
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False
