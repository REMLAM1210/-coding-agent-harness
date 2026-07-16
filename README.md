# Coding Agent Harness

A self-coded coding agent harness kernel with a deep feedback loop (validators -> classifier -> feedback loop).

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
See SPEC.md section 5.5 for full module breakdown.
