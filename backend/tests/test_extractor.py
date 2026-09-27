from forms.extractor import extract_fields
from forms.schemas import PPMPData

class _Resp:
    def __init__(self, c): self.content = c

def test_extract_ok(monkeypatch):
    monkeypatch.setattr("forms.extractor.get_llm",
        lambda temperature=None: type("L", (), {"invoke": lambda self, p: _Resp('{"fiscal_year": "2026"}')})())
    model, warning = extract_fields("ppmp", "doc")
    assert isinstance(model, PPMPData) and model.fiscal_year == "2026" and warning is False

def test_extract_bad_json_falls_back(monkeypatch):
    monkeypatch.setattr("forms.extractor.get_llm",
        lambda temperature=None: type("L", (), {"invoke": lambda self, p: _Resp("not json")})())
    model, warning = extract_fields("ppmp", "doc")
    assert isinstance(model, PPMPData) and model.fiscal_year is None and warning is True
