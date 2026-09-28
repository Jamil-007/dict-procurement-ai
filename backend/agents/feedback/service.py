import logging
from collections import defaultdict

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


def apply_trust_gate(items: list[FeedbackItem], min_repeats: int) -> list[FeedbackItem]:
    """Keep only manual corrections whose value has enough consensus to trust.

    A correction for (field, corrected_value) earns +1 per matching manual edit
    and per 👍 on that same value, and -1 per 👎 on it. Only corrections whose
    net support reaches `min_repeats` survive, so a single bad edit can't steer
    results. Raw 👍/👎 are used for counting only, never injected on their own.
    Returns trusted edit corrections, deduped by (field, value), in the input
    order (which the store already ranks by similarity)."""
    support: dict[tuple, int] = defaultdict(int)
    for it in items:
        if it.signal_type == "implicit" and it.corrected_value is not None:
            support[(it.field_path, it.corrected_value)] += 1
        elif it.signal_type == "explicit" and it.ai_value is not None:
            if it.rating == "up":
                support[(it.field_path, it.ai_value)] += 1
            elif it.rating == "down":
                support[(it.field_path, it.ai_value)] -= 1

    trusted: list[FeedbackItem] = []
    seen: set[tuple] = set()
    for it in items:
        if it.signal_type != "implicit" or it.corrected_value is None:
            continue
        key = (it.field_path, it.corrected_value)
        if key in seen:
            continue
        if support[key] >= min_repeats:
            seen.add(key)
            trusted.append(it)
    return trusted


def retrieve_feedback(feature, context_key, input_context,
                      field_path=None, top_k=None):
    if not settings.FEEDBACK_BANK_ENABLED:
        return []
    try:
        k = top_k or settings.FEEDBACK_TOP_K
        # Scan a broad, similarity-ranked window so repeats can be counted before
        # any correction is trusted, then return the top-k trusted ones.
        candidates = get_feedback_store().retrieve(
            feature, context_key, input_context,
            field_path=field_path, top_k=settings.FEEDBACK_TRUST_SCAN,
        )
        return apply_trust_gate(candidates, settings.FEEDBACK_MIN_REPEATS)[:k]
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
