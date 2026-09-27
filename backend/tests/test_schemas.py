from forms.schemas import PPMPData, MarketScopingData, ContractData, APPData, SCHEMAS

def test_all_optional_defaults_none():
    assert PPMPData().fiscal_year is None
    assert ContractData().contract_price is None
    assert APPData().fiscal_year is None
    m = MarketScopingData()
    assert m.activity_flags == {} and m.result_rows == {}

def test_registry_keys():
    assert set(SCHEMAS) == {"ppmp", "market", "app", "contract"}
