from forms.classifier import recommendations, DOC_FORM_MAP

def test_tor_recommends_ppmp_and_contract():
    rec = recommendations(["Terms of Reference"])
    assert rec["ppmp"]["recommended"] and rec["contract"]["recommended"]
    assert rec["market"]["recommended"] is False
    assert set(rec) == set(DOC_FORM_MAP)  # all 10 forms present

def test_market_study_recommends_market():
    assert recommendations(["Market Study"])["market"]["recommended"] is True

def test_group_b_never_recommended():
    rec = recommendations(["Terms of Reference"])
    assert rec["bsd"]["recommended"] is False and rec["bsd"]["available"] is True
