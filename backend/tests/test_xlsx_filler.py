from pathlib import Path
import io, openpyxl
from forms.fillers.xlsx_filler import fill_ppmp
from forms.schemas import PPMPData

TPL = Path("templates/forms/ppmp.xlsx")

def test_ppmp_writes_known_cells():
    data = PPMPData(fiscal_year="2026", estimated_budget="Php 1,000,000.00", start_activity=None)
    out = fill_ppmp(TPL, data)
    wb = openpyxl.load_workbook(io.BytesIO(out))
    ws = wb["Indicative PPMP (2)"]
    assert "2026" in str(ws["A10"].value)
    row18 = [c.value for c in ws[18]]
    assert any("1,000,000" in str(v) for v in row18 if v)
    assert any(v == "[TBD]" for v in row18)  # start_activity was None
