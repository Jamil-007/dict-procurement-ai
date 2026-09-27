from typing import Optional, Literal
from pydantic import BaseModel

class PPMPData(BaseModel):
    fiscal_year: Optional[str] = None
    end_user_unit: Optional[str] = None
    general_description: Optional[str] = None
    project_type: Optional[Literal["Goods", "Infrastructure", "Consulting Services"]] = None
    quantity_size: Optional[str] = None
    mode_of_procurement: Optional[str] = None
    pre_procurement_conference: Optional[Literal["Yes", "No", "N/A"]] = None
    start_activity: Optional[str] = None
    end_activity: Optional[str] = None
    expected_delivery: Optional[str] = None
    source_of_funds: Optional[str] = None
    estimated_budget: Optional[str] = None
    supporting_documents: Optional[str] = None
    remarks: Optional[str] = None
    prepared_by: Optional[str] = None

class MarketActivity(BaseModel):
    checked: bool = False
    documentation: Optional[str] = None

class MarketResult(BaseModel):
    considered: Optional[Literal["Yes", "No", "N/A"]] = None
    recommendation: Optional[str] = None

class MarketScopingData(BaseModel):
    procuring_entity: Optional[str] = None
    end_user_unit: Optional[str] = None
    representative: Optional[str] = None
    project_name: Optional[str] = None
    estimated_budget: Optional[str] = None
    period: Optional[str] = None
    expected_delivery: Optional[str] = None
    activity_flags: dict[str, MarketActivity] = {}
    result_rows: dict[str, MarketResult] = {}

class ContractData(BaseModel):
    project_title: Optional[str] = None
    procuring_entity: Optional[str] = None
    project_reference: Optional[str] = None
    supplier_name: Optional[str] = None
    contract_price: Optional[str] = None
    contract_date: Optional[str] = None
    scope: Optional[str] = None

class APPData(BaseModel):
    fiscal_year: Optional[str] = None
    variant: Optional[Literal["Indicative", "Final", "Updated"]] = None
    procuring_entity: Optional[str] = None
    project_title: Optional[str] = None
    category: Optional[Literal["General Requirements", "Miscellaneous Items", "Common Use Supplies"]] = None
    mode_of_procurement: Optional[str] = None
    estimated_budget: Optional[str] = None

SCHEMAS = {"ppmp": PPMPData, "market": MarketScopingData, "app": APPData, "contract": ContractData}
