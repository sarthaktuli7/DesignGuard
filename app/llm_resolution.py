"""
Optional LLM-backed resolution drafting for the Resolution Agent.

By default (no ANTHROPIC_API_KEY set, or the `anthropic` package not
installed), ResolutionAgent uses the deterministic, TF-IDF-only drafting
defined in agents.py. Set ANTHROPIC_API_KEY and install `anthropic`, and
the same agent drafts its recommendation with a real model call instead,
keeping the same grounding contract: the model is told which retrieved
cases it is allowed to cite and is instructed never to invent a case_id
that wasn't retrieved.

Same pattern as PaymentGuard's app/llm_resolution.py. Could not be
exercised inside this sandbox (no outbound network access). Standard
Anthropic SDK usage - test it yourself with a real key before relying on it.
"""
import os
import json

DEFAULT_MODEL = os.environ.get("DESIGNGUARD_LLM_MODEL", "claude-sonnet-5")
VALID_ACTIONS = {"approved_exception", "auto_fixed_to_token", "changed_by_designer", "flag_for_review"}


def llm_available():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def draft_with_llm(element, triage_result, retrieved_cases):
    """
    Returns the same shape as ResolutionAgent's deterministic draft():
        {"recommended_action": ..., "rationale": ..., "cited_cases": [...],
         "grounded": bool, "method": "llm"}
    Raises on any failure - the caller catches and falls back to deterministic.
    """
    import anthropic

    client = anthropic.Anthropic()

    if retrieved_cases:
        precedent_block = "\n".join(
            f"- case_id={c['case_id']}, resolution={c['resolution_type']}, "
            f"similarity={c['similarity']}, notes={c['resolution_notes']}"
            for c in retrieved_cases
        )
    else:
        precedent_block = "(no similar past cases were retrieved)"

    system = (
        "You are the Resolution Agent inside DesignGuard, a design-system "
        "compliance platform. Recommend exactly one action from this fixed "
        "set: approved_exception, auto_fixed_to_token, changed_by_designer, "
        "flag_for_review. You may ONLY cite case_ids that appear in the "
        "retrieved precedent list you are given - never invent one. If no "
        "precedent is listed, set grounded to false and recommend "
        "flag_for_review. Respond with ONLY a JSON object: "
        '{"recommended_action": "...", "rationale": "...", "grounded": true|false}'
    )

    user_msg = (
        f"Violation type: {element['violation_type']}\n"
        f"Designer note: {element['designer_note']}\n"
        f"Severity: {element['severity']}\n"
        f"Screen: {element['screen_name']} (high visibility: {bool(element['is_high_visibility'])})\n"
        f"Prior exceptions on this file: {element['prior_exceptions_count']}\n"
        f"Model merit score (probability this deserves an exception): {triage_result['merit_score']}\n\n"
        f"Retrieved precedent:\n{precedent_block}\n"
    )

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(text)

    action = parsed["recommended_action"]
    if action not in VALID_ACTIONS:
        raise ValueError(f"Model returned an action outside the allowed set: {action}")

    return {
        "recommended_action": action,
        "rationale": parsed["rationale"],
        "cited_cases": retrieved_cases,
        "grounded": bool(parsed.get("grounded", bool(retrieved_cases))),
        "method": "llm",
    }
