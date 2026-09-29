"""
The Compliance Checks tab: the six assigned features (T1-T6) surfaced inside
a procurement record, alongside the AI Review rather than inside it.

The two are deliberately separate. The AI Review asks five LLM dimensions to
read the documents and form a judgement. These checkers extract canonical
facts and then apply rules and comparisons that are written down in YAML and
run in deterministic Python — the same packet checked twice gives the same
answer, and every finding names the provision it rests on.

This package is the seam between them, and nothing more. The engines in
`rules/`, `consistency/` and the `checks_graph` LangGraph are untouched by it:

    catalog.py  what the six checkers are, read from the packs and profiles
    adapter.py  one Finding (findings.py) rendered as one ReviewFinding
                (review/schema.py), so both tabs store and render alike
"""

from checks.adapter import to_review_findings
from checks.catalog import CheckerInfo, all_checkers

__all__ = ["CheckerInfo", "all_checkers", "to_review_findings"]
