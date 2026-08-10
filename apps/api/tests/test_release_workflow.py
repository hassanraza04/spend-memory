from pathlib import Path


def test_release_workflow_builds_attested_images_and_assets() -> None:
    root = Path(__file__).resolve().parents[3]
    workflow = (root / ".github/workflows/release.yml").read_text()
    security = (root / ".github/workflows/security.yml").read_text()

    assert "tags: [\"v*\"]" in workflow
    assert "packages: write" in workflow
    assert "sbom: true" in workflow
    assert "provenance: true" in workflow
    assert "gh release create" in workflow
    assert "SHA256SUMS" in workflow
    assert 'tags: ["v*"]' in security
