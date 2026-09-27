import io
from pathlib import Path
from docxtpl import DocxTemplate

def render_docx(template_path: Path, context: dict, disclaimer: str | None = None) -> bytes:
    tpl = DocxTemplate(str(template_path))
    ctx = {k: ("[TBD]" if v is None else v) for k, v in context.items()}
    if disclaimer is not None:
        ctx["disclaimer"] = disclaimer
    tpl.render(ctx)
    buf = io.BytesIO()
    tpl.save(buf)
    return buf.getvalue()
