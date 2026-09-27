from docxtpl import DocxTemplate
FORMS = ["bidform", "price_local", "price_abroad", "bsd", "oss", "psd"]

def test_each_has_disclaimer_var():
    for f in FORMS:
        assert "disclaimer" in DocxTemplate(f"templates/forms/{f}.docx").get_undeclared_template_variables()

def test_price_schedules_have_no_bidder_vars():
    for f in ["price_local", "price_abroad"]:
        v = DocxTemplate(f"templates/forms/{f}.docx").get_undeclared_template_variables()
        assert v <= {"disclaimer"}  # only the disclaimer, nothing else
