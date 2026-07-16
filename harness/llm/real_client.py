from __future__ import annotations
import json
from openai import OpenAI
from harness.models import Action, Context
from harness.feedback.models import FeedbackSignal, FailureItem
from harness.llm.base import LLMClient


def build_system_prompt() -> str:
    return """You are a coding agent operating in a sandboxed workspace.
Available actions:
  ReadFile(path)           - read a file
  WriteFile(path, content) - write a file
  ListFiles(pattern)       - list files matching glob pattern
  RunShell(command)        - execute a shell command
  RunTests()               - run pytest
  RunLint()                - run ruff
  RunTypeCheck()           - run mypy
  Done(summary)            - signal task completion

Respond with EXACTLY ONE JSON object per turn:
  {"type": "<ActionType>", "args": {<action-specific args>}}

Do not include any text outside the JSON object.

CRITICAL: After completing the requested task (e.g., after writing a file), you MUST respond with Done to finish. Do NOT repeat the same action. If the previous tool call succeeded, move on to the next step or finish with Done."""


def parse_action_response(raw: str) -> Action | FeedbackSignal:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return FeedbackSignal(
            source="llm", passed=False,
            failures=[FailureItem(loc="llm_response", message=f"Non-JSON response: {raw[:200]}", category="UNKNOWN")],
            summary="LLM returned non-JSON response", raw=raw, reason="llm_parse_error",
        )
    if "type" not in data:
        return FeedbackSignal(
            source="llm", passed=False,
            failures=[FailureItem(loc="llm_response", message="Missing 'type' field in JSON", category="UNKNOWN")],
            summary="LLM returned JSON without type field", raw=raw, reason="llm_parse_error",
        )
    return Action(type=data["type"], args=data.get("args", {}))


class RealLLMClient(LLMClient):
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature

    def propose_action(self, context: Context) -> Action:
        messages = [{"role": "system", "content": build_system_prompt()}]
        messages.append({"role": "user", "content": context.system_prompt})
        for msg in context.history:
            messages.append({"role": msg.role, "content": msg.content})

        response = self._client.chat.completions.create(
            model=self._model, temperature=self._temperature, messages=messages,
        )
        raw = response.choices[0].message.content
        result = parse_action_response(raw)
        if isinstance(result, FeedbackSignal):
            # Inject parse error as feedback for next round
            context.feedback_signals.append(result)
            # Re-prompt once with error feedback
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Your response was not valid JSON. Error: {result.failures[0].message}. Please respond with a valid JSON action."})
            response = self._client.chat.completions.create(
                model=self._model, temperature=self._temperature, messages=messages,
            )
            raw = response.choices[0].message.content
            result = parse_action_response(raw)
            if isinstance(result, FeedbackSignal):
                return Action(type="Done", args={"summary": "LLM parse error - giving up"})
        return result
