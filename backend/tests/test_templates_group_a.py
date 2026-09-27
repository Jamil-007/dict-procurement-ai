import io
from pathlib import Path
import openpyxl
from docx import Document
from docxtpl import DocxTemplate

def test_xlsx_present_with_sheets():
    assert "Indicative PPMP (2)" in openpyxl.load_workbook("templates/forms/ppmp.xlsx").sheetnames
    assert "APP " in openpyxl.load_workbook("templates/forms/app.xlsx").sheetnames

def test_docx_have_expected_vars():
    for f, needed in [("market.docx", {"procuring_entity", "project_name"}),
                      ("contract.docx", {"project_title", "procuring_entity", "disclaimer"})]:
        vars_ = DocxTemplate(f"templates/forms/{f}").get_undeclared_template_variables()
        assert needed.issubset(vars_), (f, vars_)


CONTRACT_TPL = "templates/forms/contract.docx"


def test_contract_declares_expected_header_vars():
    vars_ = DocxTemplate(CONTRACT_TPL).get_undeclared_template_variables()
    assert {"disclaimer", "project_title", "procuring_entity",
            "supplier_name", "contract_price"}.issubset(vars_), vars_


def test_contract_preserves_signature_prompts_after_render():
    tpl = DocxTemplate(CONTRACT_TPL)
    ctx = dict(
        disclaimer="Generated draft — verify before submission.",
        project_title="Supply of Laptops",
        procuring_entity="DICT",
        supplier_name="Acme Corp",
        contract_price="One Million Pesos (Php 1,000,000.00)",
    )
    tpl.render(ctx)
    buf = io.BytesIO()
    tpl.save(buf)
    buf.seek(0)
    doc = Document(buf)
    text = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                text += "\n" + cell.text

    # Signature-block prompts must survive as LITERAL hand-fill text (Procuring-Entity
    # side and Supplier side => >= 2 each).
    assert text.count("[Signature over Printed Name]") >= 2
    assert text.count("[Position/Designation]") >= 2
    assert text.count("[Date]") >= 2
    assert text.count("[Name and Signature]") >= 2
    # Templatized header tokens must be filled with the context values.
    assert "Supply of Laptops" in text
    assert "DICT" in text
    assert "Acme Corp" in text
    assert "One Million Pesos" in text
    # No leftover raw header tokens.
    assert "[Insert Project Title]" not in text
    # Doc still has close to the official paragraph count (not a stub).
    assert len(doc.paragraphs) >= 90
