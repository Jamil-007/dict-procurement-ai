from feedback.models import FeedbackItem
from feedback.store import LocalFeedbackStore


def _item(**kw):
    base = dict(
        feature="forms", context_key="ppmp", thread_id="t1",
        signal_type="implicit", input_context="",
    )
    base.update(kw)
    return FeedbackItem(**base)


def test_record_then_retrieve_ranks_by_similarity(tmp_path):
    store = LocalFeedbackStore(str(tmp_path / "fb.db"))
    store.record([
        _item(field_path="procuring_entity", ai_value="Dept ICT",
              corrected_value="Department of ICT",
              input_context="procuring entity department of ICT budget laptops"),
        _item(field_path="project_title", ai_value="X", corrected_value="Y",
              input_context="banana smoothie recipe with mango"),
    ])
    got = store.retrieve("forms", "ppmp",
                         "procuring entity department of ICT laptops", top_k=1)
    assert len(got) == 1
    assert got[0].field_path == "procuring_entity"


def test_retrieve_filters_by_feature_and_context(tmp_path):
    store = LocalFeedbackStore(str(tmp_path / "fb.db"))
    store.record([
        _item(context_key="ppmp", input_context="shared context"),
        _item(context_key="market", input_context="shared context"),
        _item(feature="reviewer", context_key="ppmp", input_context="shared context"),
    ])
    got = store.retrieve("forms", "ppmp", "shared context", top_k=10)
    assert len(got) == 1
    assert got[0].feature == "forms" and got[0].context_key == "ppmp"


def test_retrieve_field_path_postfilter_and_topk(tmp_path):
    store = LocalFeedbackStore(str(tmp_path / "fb.db"))
    store.record([
        _item(field_path="abc", input_context="c1"),
        _item(field_path="abc", input_context="c2"),
        _item(field_path="other", input_context="c3"),
    ])
    got = store.retrieve("forms", "ppmp", "c1", field_path="abc", top_k=1)
    assert len(got) == 1 and got[0].field_path == "abc"


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "fb.db")
    LocalFeedbackStore(path).record([_item(input_context="persist me")])
    reopened = LocalFeedbackStore(path)
    assert len(reopened.retrieve("forms", "ppmp", "persist me", top_k=10)) == 1


def test_empty_bank_returns_empty(tmp_path):
    store = LocalFeedbackStore(str(tmp_path / "fb.db"))
    assert store.retrieve("forms", "ppmp", "anything") == []
