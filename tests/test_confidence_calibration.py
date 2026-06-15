from advocate_bot_qualtrics.config import load_confidence_scoring_calibration
from advocate_bot_qualtrics.decision_tree.confidence import (
    GENERIC_HEDGE_FALLBACK,
    clamp_answer_confidence,
    extract_latest_user_message,
    is_pure_idk,
    is_valid_hedge_reply,
    resolve_confidence_hedge_message,
    to_single_sentence,
)
from advocate_bot_qualtrics.decision_tree.schemas import CurrentNode, TreeBranch


def test_load_confidence_scoring_calibration_contains_bands():
    text = load_confidence_scoring_calibration()
    assert "CONFIDENCE SCORING CALIBRATION INDEX" in text
    assert "90–100%" in text
    assert "CRITICAL" in text
    assert "think" in text


def test_extract_latest_user_message_from_host_payload():
    payload = "Recent transcript:\n(none)\n\nLatest user message:\nUser: I think yes"
    assert extract_latest_user_message(payload) == "I think yes"


def test_clamp_answer_confidence_caps_hedge_words():
    assert clamp_answer_confidence("I think yes", 95) == 70
    assert clamp_answer_confidence("Yes, definitely", 95) == 95


def test_is_pure_idk_without_lean():
    assert is_pure_idk("I don't know")
    assert is_pure_idk("Not sure.")
    assert not is_pure_idk("I'm not sure but yes")
    assert not is_pure_idk("I think yes")


def test_to_single_sentence():
    assert to_single_sentence("First part. Second part.") == "First part."
    assert to_single_sentence("Only one") == "Only one"


def test_is_valid_hedge_reply():
    assert is_valid_hedge_reply(
        "You seemed unsure, but we'll treat that as confirming the filing date."
    )
    assert not is_valid_hedge_reply("")
    assert not is_valid_hedge_reply("Could you clarify the filing date?")
    assert not is_valid_hedge_reply(
        "First sentence. Second sentence.",
        original="First sentence. Second sentence.",
    )


def test_resolve_confidence_hedge_message_uses_llm_or_fallback():
    hedge = "You sounded tentative, but we'll proceed with that filing date."
    assert resolve_confidence_hedge_message(hedge) == hedge
    assert resolve_confidence_hedge_message("") == GENERIC_HEDGE_FALLBACK
    assert resolve_confidence_hedge_message("What is next?") == GENERIC_HEDGE_FALLBACK


def test_process_chat_payload_includes_calibration(monkeypatch):
    import importlib

    process_chat_module = importlib.import_module(
        "advocate_bot_qualtrics.decision_tree.process_chat"
    )

    captured: dict = {}

    def fake_submit(*, system, payload):
        captured.update(payload if isinstance(payload, dict) else {})
        from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse

        return ChatTurnResponse(
            user_intent="answer_node",
            assistant_reply="ok",
            next_node_id="yes",
            answer_confidence_pct=90,
        )

    monkeypatch.setattr(process_chat_module, "submit_chat_turn", fake_submit)

    node = CurrentNode(
        node_id="n1",
        question="Q?",
        branches=[TreeBranch(branch_id="yes", label="Yes")],
    )
    from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet

    process_chat_module.process_chat(
        "Latest user message:\nUser: yes", node, ComplaintFactSheet()
    )
    assert "confidence_scoring_calibration" in captured
    assert "CALIBRATION INDEX" in captured["confidence_scoring_calibration"]
    assert captured.get("confidence_hedge_threshold") == 70
