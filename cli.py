#!/usr/bin/env python3
"""CLI frontend for the coding agent harness."""
import argparse
import getpass
import sys
import tempfile

from credman.store import CredentialStore
from harness.config import load_config


def cmd_run(args):
    cfg = load_config(args.config)
    store = CredentialStore()
    key = store.get_key()
    if not key:
        print("No API key found. Run: python cli.py config set-key")
        sys.exit(1)

    from harness.models import Workspace
    from harness.agent_runner import AgentRunner, RecordingEventSink
    from harness.llm.real_client import RealLLMClient
    from harness.tools.base import ToolDispatcher
    from harness.tools.file_tools import ReadFileTool, WriteFileTool, ListFilesTool
    from harness.tools.shell_tool import RunShellTool
    from harness.tools.feedback_tools import RunTestsTool, RunLintTool, RunTypeCheckTool
    from harness.governance.guardrail import Guardrail
    from harness.governance.sandbox import Sandbox
    from harness.feedback.validators import PytestValidator
    from harness.feedback.classifier import Classifier
    from harness.feedback.feedback_loop import FeedbackLoop

    tmpdir = tempfile.mkdtemp()
    tools = [ReadFileTool(), WriteFileTool(), ListFilesTool(), RunShellTool(timeout=cfg.sandbox_timeout),
             RunTestsTool(timeout=cfg.sandbox_timeout), RunLintTool(timeout=cfg.sandbox_timeout),
             RunTypeCheckTool(timeout=cfg.sandbox_timeout)]
    guardrail = Guardrail(rules=cfg.guardrail_rules)
    sandbox = Sandbox(tools=tools, timeout=cfg.sandbox_timeout, env_whitelist=cfg.sandbox_env_whitelist)
    td = ToolDispatcher(guardrail=guardrail, sandbox=sandbox)
    llm = RealLLMClient(api_key=key, base_url="https://njusehub.info/v1", model=cfg.llm_settings.get("model", "gpt-4o-mini"))
    sink = RecordingEventSink()
    runner = AgentRunner(
        llm_client=llm, dispatcher=td, validator=PytestValidator(),
        classifier=Classifier(hints=cfg.hints),
        feedback_loop=FeedbackLoop(max_iterations=cfg.max_iterations, escalation_threshold=cfg.feedback_thresholds["escalation_threshold"]),
        config=cfg, event_sink=sink,
    )
    runner.run(args.task, Workspace(cwd=tmpdir))
    for event in sink.events:
        print(f"[{event.__class__.__name__}] {event.__dict__}")


def cmd_config(args):
    store = CredentialStore()
    if args.config_cmd == "show-key":
        print(f"API key: {store.status()}")
    elif args.config_cmd == "set-key":
        key = getpass.getpass("Enter API key: ")
        store.store_key(key)
        print("API key stored.")
    elif args.config_cmd == "clear-key":
        store.delete_key()
        print("API key cleared.")


def main():
    parser = argparse.ArgumentParser(description="Coding Agent Harness")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run the agent on a task")
    run_parser.add_argument("task", help="Task description")
    run_parser.add_argument("--config", default="config.yaml", help="Config file path")

    config_parser = sub.add_parser("config", help="Manage credentials")
    config_parser.add_argument("config_cmd", choices=["show-key", "set-key", "clear-key"])

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
