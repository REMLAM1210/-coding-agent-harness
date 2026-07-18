# Coding Agent Harness

A self-coded coding agent harness kernel with a deep feedback loop (validators -> classifier -> feedback loop).

## Live Deployment

**WebUI:** https://coding-agent-harness-syqp.onrender.com

- `/` — WebUI (task input, real-time event log, HITL approval)
- `/health` — health check
- `/docs` — FastAPI auto-docs (OpenAPI)
- `POST /sessions` — create a coding task session
- `GET /sessions/{id}` — query session status
- `POST /sessions/{id}/approve` — HITL approval
- `GET /sessions/{id}/stream` — WebSocket event stream

> Free-tier: service sleeps after 15 min idle; first request takes ~30s cold start.

## Install

```bash
pip install -e ".[dev]"
```

## Run

### CLI
```bash
python cli.py config set-key   # Enter your API key (stored in OS keyring)
python cli.py config show-key   # Check status (no plaintext)
python cli.py run "Fix the failing test in test_foo.py"
```

### Web UI
```bash
uvicorn webui.app:create_app --factory --host 0.0.0.0 --port 8000
```
Open http://localhost:8000/static/index.html

### Docker
```bash
docker build -t coding-agent-harness .
docker run -p 8000:8000 -e HARNESS_API_KEY=your-key coding-agent-harness
```
The container reads `$PORT` (defaults to 8000) and exposes a `/health` endpoint.

### Cloud Deployment (Render)
Deployed via `render.yaml` (Docker runtime, free tier). The `HARNESS_API_KEY` env var is set in the Render dashboard (never baked into the image). See `render.yaml` for the service blueprint.

## Tests
```bash
pytest tests/ -v          # All tests
pytest tests/test_demos.py -v  # Mechanism demos
```

## Key Configuration
- Local: OS keyring (recommended)
- Cloud: `HARNESS_API_KEY` environment variable
- Dev: `.env` file (plaintext, gitignored)

## Security
- Secrets never enter source code, logs, git, or agent tool environment
- Sandbox uses env whitelist (PATH/HOME/LANG only)
- Credential access controlled by harness, not LLM

## Directory Structure

```
agentproject/
├── harness/                      # Harness kernel (deliverable主体)
│   ├── agent_runner.py           #   Main loop (context→LLM→dispatch→feedback→stop)
│   ├── config.py                 #   YAML config loader
│   ├── models.py                 #   Action/ActionResult/RawExecutionResult/Context/AgentEvent/...
│   ├── llm/
│   │   ├── base.py               #   LLMClient ABC: propose_action(ctx)->Action
│   │   ├── mock_client.py        #   MockLLMClient (queue + responder modes, offline tests)
│   │   └── real_client.py        #   RealLLMClient (NJU endpoint, OpenAI-compatible)
│   ├── tools/
│   │   ├── base.py               #   Tool ABC + ToolDispatcher (single-point: guardrail→sandbox)
│   │   ├── file_tools.py         #   ReadFile/WriteFile/ListFiles (path traversal protection)
│   │   ├── shell_tool.py         #   RunShell (env whitelist + timeout)
│   │   └── feedback_tools.py     #   RunTests/RunLint/RunTypeCheck (→ RawExecutionResult)
│   ├── governance/
│   │   ├── guardrail.py          #   Guardrail rule engine (regex patterns → Decision)
│   │   ├── sandbox.py             #   Sandbox (cwd lock + env whitelist + tool delegation)
│   │   └── hitl.py               #   HITL state machine (IDLE→PENDING→APPROVED|DENIED|TIMEOUT)
│   ├── feedback/                 # ★ Focus dimension (main contribution)
│   │   ├── models.py             #   FeedbackSignal/FailureItem/FailureClassification/RetryDecision
│   │   ├── validators.py         #   PytestValidator/RuffValidator/MypyValidator
│   │   ├── classifier.py         #   Failure classification + priority merging
│   │   └── feedback_loop.py      #   Retry/escalate/stagnation-oscillation detection
│   └── memory/
│   │   └── store.py              #   Key-value memory (persists to .harness/memory.json)
├── webui/                        # Thin layer (FastAPI + frontend)
│   ├── app.py                    #   FastAPI app factory
│   ├── routes.py                 #   REST + WebSocket endpoints
│   ├── session_registry.py       #   Session state + WebSocket reconnect/replay
│   └── static/                   #   Vanilla HTML/CSS/JS frontend
├── credman/
│   └── store.py                  # Credential store (keyring → env → .env fallback)
├── cli.py                        # Thin CLI frontend
├── tests/                        # 118 mock-LLM offline unit tests + 3 mechanism demos
│   └── test_demos.py             #   A.6 mechanism demos (guardrail/feedback/stagnation)
├── config.yaml                   # Declarative config (guardrail rules, hints, thresholds)
├── Dockerfile                    # Container image build
├── .dockerignore
├── .gitlab-ci.yml                # CI: unit-test (every push) + build-image (main)
├── render.yaml                   # Render deployment blueprint
├── pyproject.toml
├── SPEC.md / PLAN.md / SPEC_PROCESS.md / AGENT_LOG.md / REFLECTION.md
└── README.md
```

See SPEC.md §5.5 for the module boundary rationale and §5.6 for the three design conventions.
