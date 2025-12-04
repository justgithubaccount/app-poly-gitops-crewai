import subprocess
import sys
from pathlib import Path

import pytest

# Ensure src directory is on sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Reset environment variables before each test."""
    # Set safe defaults for testing
    monkeypatch.setenv("ALLOW_MUTATING", "false")
    monkeypatch.setenv("ENVIRONMENT", "test")


@pytest.fixture
def mock_kubectl(monkeypatch):
    """Mock kubectl subprocess calls."""

    class MockProc:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def mock_run(cmd, capture_output=True, text=True, timeout=20):
        # Return fake kubectl output
        return MockProc(0, "pod-1 1/1 Running 2d node-a\n", "")

    monkeypatch.setattr(subprocess, "run", mock_run)
