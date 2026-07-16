import json
from unittest.mock import MagicMock, patch
from harness.models import Action, Context
from harness.feedback.models import FeedbackSignal
from harness.llm.real_client import RealLLMClient, parse_action_response, build_system_prompt


def test_parse_valid_json():
    raw = '{"type": "WriteFile", "args": {"path": "foo.py", "content": "x"}}'
    result = parse_action_response(raw)
    assert isinstance(result, Action)
    assert result.type == "WriteFile"
    assert result.args["path"] == "foo.py"


def test_parse_done():
    raw = '{"type": "Done", "args": {"summary": "fixed"}}'
    result = parse_action_response(raw)
    assert isinstance(result, Action)
    assert result.type == "Done"


def test_parse_invalid_json_returns_feedback_signal():
    raw = "This is not JSON"
    result = parse_action_response(raw)
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "llm_parse_error"
    assert "Non-JSON" in result.failures[0].message


def test_parse_missing_type():
    raw = '{"args": {"path": "foo.py"}}'
    result = parse_action_response(raw)
    assert isinstance(result, FeedbackSignal)
    assert result.reason == "llm_parse_error"


def test_build_system_prompt_contains_actions():
    prompt = build_system_prompt()
    assert "ReadFile" in prompt
    assert "WriteFile" in prompt
    assert "RunTests" in prompt
    assert "Done" in prompt
    assert "JSON" in prompt


def test_real_client_uses_mock_api():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"type": "Done", "args": {"summary": "done"}}'

    with patch("harness.llm.real_client.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        client = RealLLMClient(api_key="fake", base_url="http://test", model="test-model")
        action = client.propose_action(Context(system_prompt="test"))
        assert isinstance(action, Action)
        assert action.type == "Done"
