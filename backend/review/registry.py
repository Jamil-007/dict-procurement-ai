"""
Dimension registry.

A dimension registers itself by decorating its run function. The runner, the
/review/dimensions endpoint and the report sections all read from here, so
adding or renaming a dimension is a backend-only change — the frontend picks
it up without edits.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List

_REGISTRY: Dict[str, "DimensionSpec"] = {}

# Fixed display order. A dimension not listed here sorts to the end.
ORDER = [
    "compliance",
    "document_consistency",
    "document_quality",
    "procurement_market",
    "requirements_risk",
]


@dataclass(frozen=True)
class DimensionSpec:
    key: str
    label: str
    blurb: str
    owner: str
    run: Callable

    @property
    def sort_key(self) -> int:
        return ORDER.index(self.key) if self.key in ORDER else len(ORDER)


def register(key: str, label: str, blurb: str = "", owner: str = ""):
    """
    Register a dimension analyzer.

    The decorated function takes a ReviewContext and returns either a list of
    ReviewFinding or a DimensionOutput, which wraps the same findings together
    with an assessment of what was reviewed and anything it could not resolve.
    It may be sync or async — the runner handles both, running sync functions
    in a worker thread so a blocking llm.invoke() does not stall the other
    dimensions.

        @register(key="document_quality", label="Document Quality")
        def run(ctx: ReviewContext) -> list[ReviewFinding]:
            ...
    """

    def decorator(func: Callable) -> Callable:
        if key in _REGISTRY:
            raise ValueError(f"Dimension '{key}' is already registered")
        _REGISTRY[key] = DimensionSpec(
            key=key, label=label, blurb=blurb, owner=owner, run=func
        )
        return func

    return decorator


def all_dimensions() -> List[DimensionSpec]:
    """Every registered dimension, in display order."""
    return sorted(_REGISTRY.values(), key=lambda d: d.sort_key)


def get_dimension(key: str) -> DimensionSpec:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown dimension: {key}")
    return _REGISTRY[key]


def clear() -> None:
    """Reset the registry. Tests only."""
    _REGISTRY.clear()
