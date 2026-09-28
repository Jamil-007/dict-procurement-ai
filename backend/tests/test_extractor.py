from agents.doc_generation.extractor import extract_fields, extract_header, HEADER_KEYS
from agents.doc_generation.schemas import PPMPData

class _Resp:
    def __init__(self, c): self.content = c

def test_extract_ok(monkeypatch):
    monkeypatch.setattr("agents.doc_generation.extractor.get_llm",
        lambda temperature=None: type("L", (), {"invoke": lambda self, p: _Resp('{"fiscal_year": "2026"}')})())
    model, warning = extract_fields("ppmp", "doc")
    assert isinstance(model, PPMPData) and model.fiscal_year == "2026" and warning is False

def test_extract_bad_json_falls_back(monkeypatch):
    monkeypatch.setattr("agents.doc_generation.extractor.get_llm",
        lambda temperature=None: type("L", (), {"invoke": lambda self, p: _Resp("not json")})())
    model, warning = extract_fields("ppmp", "doc")
    assert isinstance(model, PPMPData) and model.fiscal_year is None and warning is True


def test_extract_header_llm(monkeypatch):
    monkeypatch.setattr("agents.doc_generation.extractor.get_llm",
        lambda temperature=None: type("L", (), {"invoke": lambda self, p: _Resp(
            '{"procuring_entity": "DICT", "project_title": "GECS", "project_reference": "ITB-001"}')})())
    header = extract_header("some doc text")
    assert header == {"procuring_entity": "DICT", "project_title": "GECS", "project_reference": "ITB-001"}


def test_extract_header_empty_text_all_none():
    header = extract_header("")
    assert set(header.keys()) == set(HEADER_KEYS)
    assert all(v is None for v in header.values())


def test_extract_header_regex_fallback_without_llm(monkeypatch):
    # Simulate no API key: get_llm raises -> regex fallback must still work.
    def _boom(temperature=None):
        raise RuntimeError("no api key")
    monkeypatch.setattr("agents.doc_generation.extractor.get_llm", _boom)
    text = "Procuring Entity: Department of ICT\nProject Title: GECS Laptops\nProject Identification No.: ITB-2026-001"
    header = extract_header(text)
    assert header["procuring_entity"] == "Department of ICT"
    assert header["project_title"] == "GECS Laptops"
    assert header["project_reference"] == "ITB-2026-001"
