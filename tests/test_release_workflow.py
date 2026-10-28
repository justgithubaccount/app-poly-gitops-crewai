from pathlib import Path


def test_release_creation_is_idempotent():
    """Publishing an image must not fail when the GitHub release already exists."""
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yaml"
    ).read_text(encoding="utf-8")

    assert 'gh release view "$GITHUB_REF_NAME"' in workflow
    assert "Release already exists" in workflow
    assert 'gh release create "$GITHUB_REF_NAME"' in workflow
