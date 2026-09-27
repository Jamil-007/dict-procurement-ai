import logging

from config import settings
from agents.feedback.models import FeedbackItem, EMBED_INPUT_LIMIT
from agents.feedback.store import get_feedback_store

logger = logging.getLogger(__name__)


def record_feedback(items: list[FeedbackItem]) -> int:
    if not settings.FEEDBACK_BANK_ENABLED or not items:
        return 0
    try:
        get_feedback_store().record(items)
        return len(items)
    except Exception:
        logger.exception("Failed to record feedback")
        return 0


def retrieve_feedback(feature, context_key, input_context,
                      field_path=None, top_k=None):
    if not settings.FEEDBACK_BANK_ENABLED:
        return []
    try:
        return get_feedback_store().retrieve(
            feature, context_key, input_context,
            field_path=field_path, top_k=top_k or settings.FEEDBACK_TOP_K,
        )
    except Exception:
        logger.exception("Failed to retrieve feedback")
        return []


def build_fewshot_block(items: list[FeedbackItem]) -> str:
    if not items:
        return ""
    lines = [
        "Reference corrections from similar past cases. Prefer these "
        "patterns when they apply:"
    ]
    for it in items:
        field = it.field_path or "this item"
        if it.corrected_value is not None:
            lines.append(
                f"- For '{field}', the system extracted "
                f"'{it.ai_value}' but the correct value was "
                f"'{it.corrected_value}'."
            )
        elif it.rating == "down":
            note = f" Note: {it.note}" if it.note else ""
            lines.append(f"- '{field}' value '{it.ai_value}' was marked incorrect.{note}")
        elif it.rating == "up":
            lines.append(f"- '{field}' value '{it.ai_value}' was confirmed correct.")
    return "\n".join(lines)


def inject_fewshot(prompt, feature, context_key, input_context, field_path=None, top_k=None):
    """Prepend a few-shot block of relevant past corrections to `prompt`.
    Flag-gated + fail-safe via retrieve_feedback; returns `prompt` unchanged
    when disabled, empty, or on error."""
    try:
        items = retrieve_feedback(feature, context_key, input_context, field_path=field_path, top_k=top_k)
        block = build_fewshot_block(items)
        return f"{block}\n\n{prompt}" if block else prompt
    except Exception:
        return prompt


def resolve_input_context(thread_id: str, provided, source_resolver=None) -> str:
    if provided and provided.strip():
        return provided[:EMBED_INPUT_LIMIT]
    if source_resolver is not None:
        try:
            text = source_resolver(thread_id)
        except Exception:
            text = ""
        if text and text.strip():
            return text[:EMBED_INPUT_LIMIT]
    return f"thread:{thread_id}"
