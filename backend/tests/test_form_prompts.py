from prompts import FORM_EXTRACTION_PROMPTS

def test_prompts_present_and_formattable():
    assert set(FORM_EXTRACTION_PROMPTS) == {"ppmp", "market", "app", "contract"}
    for key, tpl in FORM_EXTRACTION_PROMPTS.items():
        assert "{parsed_text}" in tpl
        assert "null" in tpl.lower()
        tpl.format(parsed_text="sample")  # no KeyError
