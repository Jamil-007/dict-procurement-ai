from agents.feedback.models import FeedbackItem, EMBED_INPUT_LIMIT, EMBEDDING_DIM
from config import Settings


def test_constants():
    assert EMBED_INPUT_LIMIT == 20000
    assert EMBEDDING_DIM == 768


def test_config_defaults_are_inert():
    # Assert the shipped code defaults (config.py) are inert, independent of any
    # local .env override — dev/staging may enable the feedback bank via env vars,
    # so read the field defaults directly rather than the .env-loaded settings.
    f = Settings.model_fields
    assert f["FEEDBACK_BANK_ENABLED"].default is False
    assert f["FEEDBACK_BACKEND"].default == "local"
    assert f["FEEDBACK_TOP_K"].default == 3
    assert f["FEEDBACK_OVERSAMPLE"].default == 4


def test_feedback_item_defaults_and_ids():
    a = FeedbackItem(
        feature="forms", context_key="ppmp", thread_id="t1",
        signal_type="implicit", ai_value="Dept. of ICT",
        corrected_value="Department of ICT", input_context="doc text",
    )
    assert a.field_path is None and a.rating is None and a.note is None
    assert a.metadata == {}
    assert isinstance(a.id, str) and len(a.id) >= 8
    assert isinstance(a.created_at, float) and a.created_at > 0
    b = FeedbackItem(
        feature="forms", context_key="ppmp", thread_id="t1",
        signal_type="implicit", input_context="doc text",
    )
    assert a.id != b.id  # unique per item
