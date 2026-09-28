from agents.doc_generation.registry import FORM_REGISTRY, catalog

def test_ten_forms():
    assert len(FORM_REGISTRY) == 10
    assert {s["group"] for s in catalog()} == {"A_rich", "B_annex"}

def test_group_b_has_no_schema():
    assert FORM_REGISTRY["bsd"].schema is None
    assert FORM_REGISTRY["ppmp"].schema is not None

def test_templates_exist():
    for spec in FORM_REGISTRY.values():
        assert spec.template_path.exists()
