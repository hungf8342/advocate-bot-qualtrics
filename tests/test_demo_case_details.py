"""The case card uses saved values and safely displays user-entered text."""

from pathlib import Path
import runpy


DEMO = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/interactive_chat_demo.py"))


def test_case_details_escape_user_content_and_show_effective_correction():
    html = DEMO["_case_details"]({"preliminary_fields": {
        "PLAINTIFF-NAME": {"value": '<img src=x onerror="alert(1)">', "status": "known"},
        "AMOUNT": {"value": "$25", "status": "known", "disputed": True, "complaint_value": "$500 <script>bad()</script>"},
    }})
    assert '<img src=x' not in html
    assert '<script>' not in html
    assert '&lt;img' in html
    assert '$25' in html
    assert 'Your correction' in html
    assert '$500 &lt;script&gt;' in html


def test_case_details_distinguish_missing_unknown_and_unanswered():
    html = DEMO["_case_details"]({"preliminary_fields": {
        "AMOUNT": {"value": None, "status": "missing"},
        "LAW-FIRM": {"value": None, "status": "unknown"},
        "RECOGNIZE": {"value": "no", "status": "known"},
    }})
    assert 'Not stated in complaint' in html
    assert 'Not sure' in html
    assert 'Not answered yet' in html
    assert '>No<' in html


def test_presentation_hides_internal_tags_without_changing_transcript():
    class Session:
        transcript = [("assistant", "Do you recognize the account? [RECOGNIZE]"), ("user", "My name is [EXAMPLE]")]

    engine = Session()
    history = DEMO["_chat_history"](engine)
    assert history[0]["content"] == "Do you recognize the account?"
    assert history[1]["content"] == "My name is [EXAMPLE]"
    assert engine.transcript[0][1].endswith("[RECOGNIZE]")
