from docx import Document
from docxtpl import DocxTemplate
FORMS = ["bidform", "price_local", "price_abroad", "bsd", "oss", "psd"]

def test_each_has_disclaimer_var():
    for f in FORMS:
        assert "disclaimer" in DocxTemplate(f"templates/forms/{f}.docx").get_undeclared_template_variables()

def test_price_schedules_have_no_bidder_vars():
    for f in ["price_local", "price_abroad"]:
        v = DocxTemplate(f"templates/forms/{f}.docx").get_undeclared_template_variables()
        assert v <= {"disclaimer"}  # only the disclaimer, nothing else

def test_group_b_rebuilt_from_official_not_stubs():
    # Narrative annex forms must carry the full official body (guards against stub regression).
    for f in ["bidform", "bsd", "oss", "psd"]:
        doc = Document(f"templates/forms/{f}.docx")
        assert len(doc.paragraphs) > 15, (f, len(doc.paragraphs))

def test_price_schedules_have_official_tables():
    # Price schedules are table-heavy; assert the official summary tables survived.
    for f in ["price_local", "price_abroad"]:
        doc = Document(f"templates/forms/{f}.docx")
        assert len(doc.paragraphs) > 5 and len(doc.tables) >= 1, (f,)
