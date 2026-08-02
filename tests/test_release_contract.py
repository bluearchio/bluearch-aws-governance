from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from scripts.set_release_version import normalize_release_tag

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
MACOS_VERIFIER = ROOT / "scripts" / "verify_macos_artifact.sh"


def _workflow() -> dict:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _needs(job: dict) -> set[str]:
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else set(needs)


def _named_step(job: dict, name: str) -> tuple[int, dict]:
    for index, step in enumerate(job["steps"]):
        if step.get("name") == name:
            return index, step
    raise AssertionError(f"workflow job has no step named {name!r}")


def test_release_graph_gates_both_builds_and_publication_on_verification():
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert workflow["on"]["push"]["tags"] == ["v*"]
    assert "workflow_dispatch" not in workflow["on"]
    assert _needs(jobs["linux"]) == {"verify"}
    assert _needs(jobs["macos"]) == {"verify"}
    assert _needs(jobs["publish"]) == {"verify", "linux", "macos"}

    _, gate = _named_step(jobs["verify"], "Verify immutable tag and main commit")
    assert "GITHUB_REF_TYPE" in gate["run"]
    assert "v${committed_version}" in gate["run"]
    assert "refs/remotes/origin/main" in gate["run"]
    assert "refs/remotes/origin/dev" in gate["run"]
    assert "git merge-base --is-ancestor" in gate["run"]
    assert '"${dev_sha}" "${tag_sha}"' in gate["run"]
    _named_step(jobs["verify"], "Run Python tests")
    _named_step(jobs["verify"], "Build frontend")


def test_normal_ci_gates_both_dev_and_main_pushes():
    workflow = yaml.load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert set(workflow["on"]["push"]["branches"]) == {"dev", "main"}


def test_release_jobs_verify_final_archives_before_sbom_and_publish():
    jobs = _workflow()["jobs"]

    linux_verify_index, linux_verify = _named_step(jobs["linux"], "Verify final Linux archive")
    linux_sbom_index, linux_sbom = _named_step(jobs["linux"], "Generate Linux SBOM")
    assert linux_verify_index < linux_sbom_index
    assert linux_sbom["with"]["path"].endswith("-linux-x86_64.tar.gz")
    assert "catalog verify" in linux_verify["run"]
    assert '"$BINARY_NAME ${RELEASE_TAG#v}"' in linux_verify["run"]

    notarize_index, notarize = _named_step(jobs["macos"], "Codesign and notarize macOS asset")
    mac_verify_index, mac_verify = _named_step(jobs["macos"], "Verify final notarized macOS archive")
    mac_sbom_index, mac_sbom = _named_step(jobs["macos"], "Generate macOS SBOM")
    assert notarize_index < mac_verify_index < mac_sbom_index
    assert "--keepParent" not in notarize["run"]
    assert "--norsrc --noextattr --noqtn --noacl" in notarize["run"]
    assert "cd dist" in notarize["run"]
    assert mac_verify["run"].startswith("bash scripts/verify_macos_artifact.sh")
    assert '"${RELEASE_TAG#v}"' in mac_verify["run"]
    assert mac_sbom["with"]["path"].endswith("-macos-arm64.zip")

    checksum_index, checksum = _named_step(jobs["publish"], "Generate checksums")
    attest_index, _ = _named_step(jobs["publish"], "Generate artifact provenance attestations")
    publish_index, _ = _named_step(jobs["publish"], "Publish draft release with all assets")
    assert checksum_index < attest_index < publish_index
    assert "sha256sum -c SHA256SUMS" in checksum["run"]


def test_attestation_job_has_required_artifact_metadata_permission():
    publish = _workflow()["jobs"]["publish"]

    assert publish["permissions"]["artifact-metadata"] == "write"


def test_release_workflow_does_not_mutate_homebrew_tap():
    workflow = _workflow()
    all_steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    ]

    assert all("homebrew" not in str(step).lower() for step in all_steps)
    assert all("HOMEBREW" not in key for key in workflow.get("env", {}))


def test_every_release_shell_block_is_syntactically_valid_bash():
    workflow = _workflow()
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            command = step.get("run")
            if not command:
                continue
            result = subprocess.run(
                ["bash", "-n", "-c", command],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, (
                f"invalid shell in {job_name}/{step.get('name', 'unnamed')}: {result.stderr}"
            )


@pytest.mark.parametrize(
    "value",
    ["0.2.4", "v0.2", "v0.2.4-rc1", "main", "", " v0.2.4 "],
)
def test_release_version_setter_rejects_noncanonical_tags(value):
    with pytest.raises(ValueError):
        normalize_release_tag(value)


def test_release_version_setter_returns_bare_pep440_version():
    assert normalize_release_tag("v0.2.4") == "0.2.4"

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    namespace: dict[str, str] = {}
    exec((ROOT / "cloud_governance/__init__.py").read_text(encoding="utf-8"), namespace)
    assert metadata["project"]["version"] == "0.2.4"
    assert namespace["__version__"] == "0.2.4"


def test_release_version_setter_writes_bare_version_to_both_metadata_files(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "cloud_governance").mkdir()
    script = tmp_path / "scripts" / "set_release_version.py"
    shutil.copy2(ROOT / "scripts" / "set_release_version.py", script)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "cloud_governance/__init__.py").write_text(
        '__version__ = "0.0.0"\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, os.fspath(script), "v1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert 'version = "1.2.3"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "1.2.3"' in (
        tmp_path / "cloud_governance/__init__.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform != "darwin", reason="codesign verification requires macOS")
def test_macos_verifier_rejects_unsigned_final_archive(tmp_path):
    staging = tmp_path / "dist"
    staging.mkdir()
    unsigned = staging / "bluearch-aws-governance"
    unsigned.write_text("#!/bin/sh\necho bluearch-aws-governance 0.2.4\n", encoding="utf-8")
    unsigned.chmod(0o755)
    archive = tmp_path / "bluearch-aws-governance-macos-arm64.zip"
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--norsrc",
            "--noextattr",
            "--noqtn",
            "--noacl",
            unsigned.name,
            os.fspath(archive),
        ],
        cwd=staging,
        check=True,
    )

    result = subprocess.run(
        [
            "bash",
            os.fspath(MACOS_VERIFIER),
            os.fspath(archive),
            "bluearch-aws-governance",
            "0.2.4",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0


def test_macos_verifier_requires_expected_version_argument(tmp_path):
    result = subprocess.run(
        ["bash", os.fspath(MACOS_VERIFIER), os.fspath(tmp_path / "missing.zip"), "bluearch-aws-governance"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "EXPECTED_VERSION" in result.stderr


def test_macos_verifier_inspects_archive_before_extraction(tmp_path):
    archive = tmp_path / "traversal.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../bluearch-aws-governance", "malicious")

    result = subprocess.run(
        [
            "bash",
            os.fspath(MACOS_VERIFIER),
            os.fspath(archive),
            "bluearch-aws-governance",
            "0.2.4",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    verifier_source = MACOS_VERIFIER.read_text(encoding="utf-8")

    assert result.returncode != 0
    assert "exactly one root file" in result.stderr
    assert verifier_source.index("zipfile.ZipFile") < verifier_source.index('ditto -x -k')
    assert '"$("$BINARY_PATH" --version)" == "$PUBLIC_BINARY_NAME $EXPECTED_VERSION"' in verifier_source
