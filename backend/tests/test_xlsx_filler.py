from pathlib import Path
import io, openpyxl
from forms.fillers.xlsx_filler import fill_ppmp, fill_app
from forms.schemas import PPMPData, APPData

TPL = Path("templates/forms/ppmp.xlsx")
APP_TPL = Path("templates/forms/app.xlsx")

def test_ppmp_writes_known_cells():
    data = PPMPData(fiscal_year="2026", estimated_budget="Php 1,000,000.00", start_activity=None)
    out = fill_ppmp(TPL, data)
    wb = openpyxl.load_workbook(io.BytesIO(out))
    ws = wb["Indicative PPMP (2)"]
    assert "2026" in str(ws["A10"].value)
    row18 = [c.value for c in ws[18]]
    assert any("1,000,000" in str(v) for v in row18 if v)
    assert any(v == "[TBD]" for v in row18)  # start_activity was None


def _col_by_header(ws, needle: str) -> int:
    """Find the column index whose row-7 header contains `needle` (case-insensitive)."""
    for c in range(1, ws.max_column + 1):
        v = ws.cell(7, c).value
        if v and needle.lower() in str(v).lower():
            return c
    raise AssertionError(f"header not found: {needle}")


def test_app_writes_to_correct_columns():
    data = APPData(
        fiscal_year="2026",
        project_title="GECS Laptop Procurement",
        mode_of_procurement="Competitive Bidding",
        estimated_budget="Php 5,000,000.00",
        category="General Requirements",
    )
    out = fill_app(APP_TPL, data)
    ws = openpyxl.load_workbook(io.BytesIO(out))["APP "]

    title_col = _col_by_header(ws, "Project Title")
    mode_col = _col_by_header(ws, "Mode of Procurement")
    budget_col = _col_by_header(ws, "Estimated Budget")

    row = 11  # General Requirements data row
    assert ws.cell(row, title_col).value == "GECS Laptop Procurement"
    assert ws.cell(row, mode_col).value == "Competitive Bidding"
    assert "5,000,000" in str(ws.cell(row, budget_col).value)
    # Budget must NOT land in the timeline column (J = "Start of Procurement Activity")
    start_col = _col_by_header(ws, "Start of Procurement Activity")
    assert "5,000,000" not in str(ws.cell(row, start_col).value or "")
    # End-User column (D) must NOT receive the mode value
    enduser_col = _col_by_header(ws, "End-User")
    assert ws.cell(row, enduser_col).value != "Competitive Bidding"
    # Sample PAP example row cleared
    assert ws.cell(11, 1).value in (None, "")
