from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI job
    import tomli as tomllib

from scripts.set_release_version import normalize_release_tag

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
QUALITY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "development-quality.yml"
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
    assert _needs(jobs["homebrew"]) == {"publish"}

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


def test_ci_supports_release_contract_tests_on_python_310():
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert '"tomli>=2.0; python_version < \'3.11\'"' in workflow


def test_quality_checks_support_current_permissions_and_patched_build_tooling():
    workflow = QUALITY_WORKFLOW_PATH.read_text(encoding="utf-8")
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert 'go-version: "1.24"' in workflow
    assert "actionlint@v1.7.10" in workflow
    assert '"setuptools>=83"' in workflow
    assert "setuptools>=83" in metadata["build-system"]["requires"]
    for requirements_path in (
        ROOT / "build-requirements.txt",
        ROOT / "build-requirements-macos.txt",
    ):
        assert "setuptools>=83" in requirements_path.read_text(encoding="utf-8").splitlines()

    frontend_lock = json.loads(
        (ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8")
    )
    postcss_version = frontend_lock["packages"]["node_modules/postcss"]["version"]
    assert tuple(map(int, postcss_version.split("."))) > (8, 5, 17)


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


def test_cross_repo_token_is_validated_before_github_release_publication():
    workflow = _workflow()
    publish = workflow["jobs"]["publish"]
    token_index, token = _named_step(
        publish, "Validate Homebrew tap token before publication"
    )
    release_index, release = _named_step(
        publish, "Publish draft release with all assets"
    )

    assert token_index < release_index
    assert token["env"]["GH_TOKEN"] == "${{ secrets.HOMEBREW_TAP_TOKEN_2 }}"
    assert '"repos/${HOMEBREW_TAP_REPO}"' in token["run"]
    assert ".permissions.push" in token["run"]
    assert ".allow_auto_merge" in token["run"]
    assert '"${HOMEBREW_TAP_REPO}"$\'\\ttrue\\ttrue\'' in token["run"]
    assert 'gh pr list --repo "$HOMEBREW_TAP_REPO"' in token["run"]
    assert "github.token" not in str(token)
    assert release["env"]["GH_TOKEN"] == "${{ github.token }}"


def test_release_publication_is_resumable_and_never_mutates_public_assets():
    _, release = _named_step(
        _workflow()["jobs"]["publish"], "Publish draft release with all assets"
    )
    commands = release["run"]

    assert 'release_endpoint="repos/${GITHUB_REPOSITORY}/releases/tags/${RELEASE_TAG}"' in commands
    assert 'release_is_draft="$(gh api "$release_endpoint" --jq \'.draft\')"' in commands
    assert 'if [[ "$release_is_draft" == "true" ]]' in commands
    assert 'gh release upload "$RELEASE_TAG" release-assets/* --repo "$GITHUB_REPOSITORY" --clobber' in commands
    assert 'Release $RELEASE_TAG is already public; verifying it without mutation.' in commands
    assert 'select(.state == "uploaded") | [.name, .digest]' in commands
    assert 'diff -q "$expected_assets" "$remote_assets"' in commands
    assert 'gh release edit "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --draft=false' in commands
    for subcommand in ("create", "upload", "edit"):
        assert f"gh release {subcommand}" in commands
        assert '--repo "$GITHUB_REPOSITORY"' in commands


def test_formula_inputs_are_the_exact_verified_macos_asset_and_sha():
    workflow = _workflow()
    publish = workflow["jobs"]["publish"]
    _, checksums = _named_step(publish, "Generate checksums")
    homebrew = workflow["jobs"]["homebrew"]
    _, update = _named_step(homebrew, "Update Homebrew formula from verified release")

    assert checksums["id"] == "final_checksums"
    assert 'formula_asset="${BINARY_NAME}-macos-arm64.zip"' in checksums["run"]
    assert 'sha256sum "$formula_asset"' in checksums["run"]
    assert publish["outputs"]["formula_asset"] == (
        "${{ steps.final_checksums.outputs.formula_asset }}"
    )
    assert publish["outputs"]["formula_sha256"] == (
        "${{ steps.final_checksums.outputs.formula_sha256 }}"
    )
    assert homebrew["env"]["FORMULA_ASSET"] == (
        "${{ needs.publish.outputs.formula_asset }}"
    )
    assert homebrew["env"]["FORMULA_SHA256"] == (
        "${{ needs.publish.outputs.formula_sha256 }}"
    )
    assert '"$FORMULA_ASSET" == "${BINARY_NAME}-macos-arm64.zip"' in update["run"]
    assert '"$FORMULA_SHA256" =~ ^[0-9a-f]{64}$' in update["run"]
    assert "python3 scripts/update_formula.py" in update["run"]
    assert '--repo "$GITHUB_REPOSITORY"' in update["run"]
    assert '--version "$RELEASE_TAG"' in update["run"]
    assert '--asset "$FORMULA_ASSET"' in update["run"]
    assert '--sha256 "$FORMULA_SHA256"' in update["run"]
    assert '--legacy-exceptions "config/legacy-dist-exceptions.json"' in update["run"]
    assert "https://github.com" not in update["run"]


def test_tap_pr_is_scoped_to_main_and_release_branch_from_origin_main():
    homebrew = _workflow()["jobs"]["homebrew"]
    _, checkout = _named_step(homebrew, "Checkout Homebrew tap main")
    _, update = _named_step(homebrew, "Update Homebrew formula from verified release")
    _, pull_request = _named_step(homebrew, "Create or update Homebrew tap pull request")

    assert checkout["with"] == {
        "repository": "${{ env.HOMEBREW_TAP_REPO }}",
        "token": "${{ secrets.HOMEBREW_TAP_TOKEN_2 }}",
        "ref": "main",
        "fetch-depth": "0",
        "path": "homebrew-tap",
        "persist-credentials": "false",
    }
    assert 'branch="release/${HOMEBREW_FORMULA}-${RELEASE_TAG}"' in update["run"]
    assert 'git checkout -B "$branch" refs/remotes/origin/main' in update["run"]
    assert pull_request["id"] == "homebrew_pr"
    assert 'remote_url="$(git remote get-url origin)"' in pull_request["run"]
    assert "git push --force-with-lease" in pull_request["run"]
    assert 'gh pr list --repo "$HOMEBREW_TAP_REPO" --base main --head "$branch"' in pull_request["run"]
    assert 'git add "Formula/${HOMEBREW_FORMULA}.rb" "config/legacy-dist-exceptions.json"' in pull_request["run"]
    assert "gh pr create \\" in pull_request["run"]
    assert '--repo "$HOMEBREW_TAP_REPO" \\' in pull_request["run"]
    assert "--base main \\" in pull_request["run"]
    assert '--head "$branch" \\' in pull_request["run"]
    assert "git push origin main" not in pull_request["run"]
    assert "--admin" not in pull_request["run"]


def test_tap_auto_merge_is_conditional_and_waits_for_required_checks():
    homebrew = _workflow()["jobs"]["homebrew"]
    _, pull_request = _named_step(homebrew, "Create or update Homebrew tap pull request")
    _, merge = _named_step(
        homebrew, "Request Homebrew tap auto-merge after required checks"
    )

    assert 'echo "pr_number=" >> "$GITHUB_OUTPUT"' in pull_request["run"]
    assert merge["if"] == "steps.homebrew_pr.outputs.pr_number != ''"
    assert merge["env"]["GH_TOKEN"] == "${{ secrets.HOMEBREW_TAP_TOKEN_2 }}"
    assert merge["env"]["PR_NUMBER"] == (
        "${{ steps.homebrew_pr.outputs.pr_number }}"
    )
    merge_command = 'gh pr merge "$PR_NUMBER" --repo "$HOMEBREW_TAP_REPO" --auto --squash --delete-branch'
    assert merge_command in merge["run"]
    assert "--admin" not in merge["run"]

    _, wait = _named_step(homebrew, "Wait for Homebrew formula merge")
    assert wait["if"] == "steps.homebrew_pr.outputs.pr_number != ''"
    assert wait["timeout-minutes"] == "125"
    assert wait["env"]["PR_NUMBER"] == "${{ steps.homebrew_pr.outputs.pr_number }}"
    assert 'gh pr view "$PR_NUMBER" --repo "$HOMEBREW_TAP_REPO" --json state' in wait["run"]
    assert "MERGED) exit 0" in wait["run"]
    assert "CLOSED)" in wait["run"]
    assert "Timed out waiting for Homebrew tap PR" in wait["run"]


def test_every_checkout_disables_persisted_credentials():
    steps = [
        step
        for job in _workflow()["jobs"].values()
        for step in job.get("steps", [])
        if step.get("uses") == "actions/checkout@v4"
    ]

    assert steps
    assert all(step["with"]["persist-credentials"] == "false" for step in steps)


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
