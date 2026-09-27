from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from pydantic import BaseModel

from agents.doc_generation.schemas import PPMPData, MarketScopingData, APPData, ContractData
from agents.doc_generation.fillers.docx_filler import render_docx, fill_market, GROUP_A_DISCLAIMER
from agents.doc_generation.fillers.xlsx_filler import fill_ppmp, fill_app
from agents.doc_generation.classifier import DOC_FORM_MAP

# Disclaimer for Group B forms
GROUP_B_DISCLAIMER = "DRAFT — issued blank for completion by the bidder. Not an executed or notarized document."

@dataclass(frozen=True)
class FormSpec:
    key: str
    name: str
    group: str  # "A_rich" | "B_annex"
    ext: str
    engine: str  # "docx" | "xlsx"
    template_path: Path
    schema: type[BaseModel] | None  # None for Group B
    source_doc_types: list[str]
    recommended_when: list[str]
    fill_level: str  # "rich" | "annex"
    filler: Callable[..., bytes]
    disclaimer: str | None  # Set for Group B

def _build_ppmp_context(data: PPMPData) -> dict:
    return data.model_dump()

def _build_market_context(data: MarketScopingData) -> dict:
    return data.model_dump()

def _build_contract_context(data: ContractData) -> dict:
    # Pass only the vars the rebuilt contract.docx declares (disclaimer is added by
    # render_docx). Older vars like contract_date/scope caused the signature block to
    # drop, so they are intentionally no longer templatized or passed.
    return {
        "project_title": data.project_title,
        "procuring_entity": data.procuring_entity,
        "supplier_name": data.supplier_name,
        "contract_price": data.contract_price,
    }

def _build_app_context(data: APPData) -> dict:
    return data.model_dump()

# Wrapper for docx Group A forms
def _docx_filler_market(template_path: Path, data: MarketScopingData) -> bytes:
    return fill_market(template_path, data)

def _docx_filler_contract(template_path: Path, data: ContractData) -> bytes:
    return render_docx(template_path, _build_contract_context(data), disclaimer=GROUP_A_DISCLAIMER)

# Wrapper for Group B docx forms
def _docx_filler_group_b(template_path: Path, context: dict) -> bytes:
    return render_docx(template_path, context, disclaimer=GROUP_B_DISCLAIMER)

# Template base directory
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "forms"

# Form registry
FORM_REGISTRY = {
    "ppmp": FormSpec(
        key="ppmp",
        name="Project Procurement Management Plan",
        group="A_rich",
        ext=".xlsx",
        engine="xlsx",
        template_path=TEMPLATE_DIR / "ppmp.xlsx",
        schema=PPMPData,
        source_doc_types=DOC_FORM_MAP["ppmp"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["ppmp"]["recommended_when"],
        fill_level="rich",
        filler=fill_ppmp,
        disclaimer=None,
    ),
    "market": FormSpec(
        key="market",
        name="Market Scoping Form",
        group="A_rich",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "market.docx",
        schema=MarketScopingData,
        source_doc_types=DOC_FORM_MAP["market"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["market"]["recommended_when"],
        fill_level="rich",
        filler=_docx_filler_market,
        disclaimer=None,
    ),
    "app": FormSpec(
        key="app",
        name="Annual Procurement Plan",
        group="A_rich",
        ext=".xlsx",
        engine="xlsx",
        template_path=TEMPLATE_DIR / "app.xlsx",
        schema=APPData,
        source_doc_types=DOC_FORM_MAP["app"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["app"]["recommended_when"],
        fill_level="rich",
        filler=fill_app,
        disclaimer=None,
    ),
    "contract": FormSpec(
        key="contract",
        name="Contract Form",
        group="A_rich",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "contract.docx",
        schema=ContractData,
        source_doc_types=DOC_FORM_MAP["contract"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["contract"]["recommended_when"],
        fill_level="rich",
        filler=_docx_filler_contract,
        disclaimer=None,
    ),
    # Group B blank annexes
    "bidform": FormSpec(
        key="bidform",
        name="Bid Form (Goods/Infrastructure)",
        group="B_annex",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "bidform.docx",
        schema=None,
        source_doc_types=DOC_FORM_MAP["bidform"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["bidform"]["recommended_when"],
        fill_level="annex",
        filler=_docx_filler_group_b,
        disclaimer=GROUP_B_DISCLAIMER,
    ),
    "price_local": FormSpec(
        key="price_local",
        name="Price Schedule — within the Philippines",
        group="B_annex",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "price_local.docx",
        schema=None,
        source_doc_types=DOC_FORM_MAP["price_local"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["price_local"]["recommended_when"],
        fill_level="annex",
        filler=_docx_filler_group_b,
        disclaimer=GROUP_B_DISCLAIMER,
    ),
    "price_abroad": FormSpec(
        key="price_abroad",
        name="Price Schedule — Abroad",
        group="B_annex",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "price_abroad.docx",
        schema=None,
        source_doc_types=DOC_FORM_MAP["price_abroad"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["price_abroad"]["recommended_when"],
        fill_level="annex",
        filler=_docx_filler_group_b,
        disclaimer=GROUP_B_DISCLAIMER,
    ),
    "bsd": FormSpec(
        key="bsd",
        name="Bid Securing Declaration",
        group="B_annex",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "bsd.docx",
        schema=None,
        source_doc_types=DOC_FORM_MAP["bsd"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["bsd"]["recommended_when"],
        fill_level="annex",
        filler=_docx_filler_group_b,
        disclaimer=GROUP_B_DISCLAIMER,
    ),
    "oss": FormSpec(
        key="oss",
        name="Omnibus Sworn Statement",
        group="B_annex",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "oss.docx",
        schema=None,
        source_doc_types=DOC_FORM_MAP["oss"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["oss"]["recommended_when"],
        fill_level="annex",
        filler=_docx_filler_group_b,
        disclaimer=GROUP_B_DISCLAIMER,
    ),
    "psd": FormSpec(
        key="psd",
        name="Performance Securing Declaration",
        group="B_annex",
        ext=".docx",
        engine="docx",
        template_path=TEMPLATE_DIR / "psd.docx",
        schema=None,
        source_doc_types=DOC_FORM_MAP["psd"]["source_doc_types"],
        recommended_when=DOC_FORM_MAP["psd"]["recommended_when"],
        fill_level="annex",
        filler=_docx_filler_group_b,
        disclaimer=GROUP_B_DISCLAIMER,
    ),
}

def catalog() -> list[dict]:
    """Returns form catalog metadata for the API."""
    return [
        {
            "key": spec.key,
            "name": spec.name,
            "group": spec.group,
            "ext": spec.ext,
            "fill_level": spec.fill_level,
        }
        for spec in FORM_REGISTRY.values()
    ]
