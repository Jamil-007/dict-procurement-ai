from utils.json_extract import extract_json_object

def test_plain(): assert extract_json_object('{"a": 1}') == {"a": 1}
def test_fenced(): assert extract_json_object('```json\n{"a": 2}\n```') == {"a": 2}
def test_surrounded(): assert extract_json_object('here:\n{"a": 3}\nthanks') == {"a": 3}
def test_garbage_returns_none(): assert extract_json_object('no json here') is None
