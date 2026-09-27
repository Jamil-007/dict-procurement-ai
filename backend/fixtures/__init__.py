"""Labelled fixture packets used to measure the checkers.

`base.py` holds one clean procurement transaction; `mutate.py` injects a
single known defect per case and records which check must catch it. Tests
read the generated JSON in `cases/`, so the ground truth is an inspectable
artifact rather than something buried in test code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from facts.schema import DocumentFacts

CASES_DIR = Path(__file__).parent / "cases"


def load_case(case_id: str) -> Dict:
    """Load one case, with its documents parsed into `DocumentFacts`."""
    with open(CASES_DIR / f"{case_id}.json", "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["documents"] = [
        DocumentFacts.model_validate(entry) for entry in payload["documents"]
    ]
    return payload


def load_cases() -> List[Dict]:
    """Every generated case, in a stable order."""
    return [load_case(path.stem) for path in sorted(CASES_DIR.glob("*.json"))]


__all__ = ["CASES_DIR", "load_case", "load_cases"]
