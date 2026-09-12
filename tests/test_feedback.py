import json

from nexora.feedback import FeedbackInput, format_feedback, save_feedback


def test_feedback_is_shareable_and_diagnostics_are_redacted(tmp_path):
    feedback = FeedbackInput(
        overall_experience=4,
        confusing="The first screen was unclear.",
        error_seen="GEMINI_API_KEY=secret-value",
        liked_feature="Chat",
        add_next="More file tools",
        attach_diagnostic=True,
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "nexora.log").write_text("GEMINI_API_KEY=secret-value\nstartup failed", encoding="utf-8")
    filename = save_feedback(tmp_path, feedback)
    payload = json.loads((tmp_path / "feedback" / filename).read_text(encoding="utf-8"))
    assert "secret-value" not in json.dumps(payload)
    assert "The first screen was unclear." in format_feedback(feedback)
    assert payload["overall_experience"] == 4


def test_feedback_rating_is_validated():
    try:
        FeedbackInput(overall_experience=6)
    except ValueError:
        pass
    else:
        raise AssertionError("ratings above five must be rejected")
