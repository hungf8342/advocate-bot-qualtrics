import pytest

from advocate_bot_qualtrics.core.errors import ChatError
from advocate_bot_qualtrics.decision_tree.schemas import ChatTurnResponse
from advocate_bot_qualtrics.llm import chat_structured


def test_submit_chat_turn_zai_validates_response(monkeypatch):
    def fake_complete_with_tools(**_kwargs):
        return {
            "user_intent": "answer_node",
            "assistant_reply": "Got it.",
            "next_node_id": "yes",
            "answer_confidence_pct": 90,
        }

    monkeypatch.setattr(chat_structured, "get_zai_api_key", lambda: "test-key")
    monkeypatch.setattr(
        chat_structured.OpenAIClient,
        "complete_with_tools",
        lambda self, **_kwargs: fake_complete_with_tools(),
    )

    turn = chat_structured.submit_chat_turn(system="sys", payload={"user": "yes"})

    assert turn.user_intent == "answer_node"
    assert turn.next_node_id == "yes"
    assert turn.answer_confidence_pct == 90


def test_submit_chat_turn_zai_requires_api_key(monkeypatch):
    monkeypatch.setattr(chat_structured, "get_zai_api_key", lambda: "")

    with pytest.raises(ChatError, match="ZAI_API_KEY"):
        chat_structured.submit_chat_turn(system="sys", payload="hello")


def test_submit_chat_turn_anthropic_disabled(monkeypatch):
    monkeypatch.setattr(chat_structured, "get_chat_provider", lambda: "anthropic")

    with pytest.raises(ChatError, match="anthropic is disabled"):
        chat_structured.submit_chat_turn(system="sys", payload="hello")


def test_openai_client_complete_with_tools_parses_json():
    from advocate_bot_qualtrics.llm.client import OpenAIClient

    class FakeFunction:
        name = "submit_chat_turn"
        arguments = (
            '{"user_intent":"answer_node","assistant_reply":"ok",'
            '"next_node_id":"no","answer_confidence_pct":65}'
        )

    class FakeToolCall:
        function = FakeFunction()

    class FakeMessage:
        tool_calls = [FakeToolCall()]

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **_kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    client = OpenAIClient(api_key="k", base_url="https://example.test/v1/")
    client._client = FakeClient()

    payload = client.complete_with_tools(
        model="glm-5.2",
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        tool_choice={},
    )

    assert payload["next_node_id"] == "no"
    assert payload["answer_confidence_pct"] == 65
