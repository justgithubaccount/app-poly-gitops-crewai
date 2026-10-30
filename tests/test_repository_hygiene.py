from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_task_outputs_are_not_versioned_inputs() -> None:
    ignore = (ROOT / ".gitignore").read_text().splitlines()

    assert "output/" in ignore
    assert not list((ROOT / "output").glob("*.md"))


def test_requests_is_a_direct_runtime_dependency() -> None:
    project = (ROOT / "pyproject.toml").read_text()

    assert '"requests>=' in project


def test_unused_crewai_tools_extra_is_not_installed() -> None:
    project = (ROOT / "pyproject.toml").read_text()

    assert '"crewai==1.15.33"' in project
    assert "crewai[tools]" not in project
