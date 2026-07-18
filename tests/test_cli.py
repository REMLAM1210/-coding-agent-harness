import subprocess
import sys


def test_cli_help():
    result = subprocess.run([sys.executable, "cli.py", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "config" in result.stdout


def test_cli_config_show_key():
    result = subprocess.run([sys.executable, "cli.py", "config", "show-key"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "not set" in result.stdout or "set" in result.stdout
