"""The JSON-extraction fallback in facts.llm parses model replies offline."""

from facts.llm import _loads


def test_loads_strips_code_fences():
    assert _loads('```json\n{"a": 1}\n```') == {"a": 1}


def test_loads_extracts_object_from_surrounding_prose():
    assert _loads('Here is the result: {"b": 2} — done.') == {"b": 2}
