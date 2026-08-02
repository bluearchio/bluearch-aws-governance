from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-linux.sh"
BINARY_NAME = "bluearch-aws-governance"
ASSET_NAME = f"{BINARY_NAME}-linux-x86_64.tar.gz"
VERSION = "v0.2.4"


def _write_fake_uname(bin_dir: Path) -> None:
    uname = bin_dir / "uname"
    uname.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  -s) echo Linux ;;\n"
        "  -m) echo x86_64 ;;\n"
        "  *) exit 2 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    uname.chmod(0o755)


def _write_archive(path: Path, layout: str) -> None:
    if layout == "malformed":
        path.write_bytes(b"not a gzip archive")
        return

    with tarfile.open(path, "w:gz") as archive:
        names = {
            "valid": [BINARY_NAME],
            "traversal": [f"../{BINARY_NAME}"],
            "nested": [f"nested/{BINARY_NAME}"],
            "duplicate": [BINARY_NAME, BINARY_NAME],
            "symlink": [BINARY_NAME],
        }[layout]
        for name in names:
            item = tarfile.TarInfo(name)
            if layout == "symlink":
                item.type = tarfile.SYMTYPE
                item.linkname = "/bin/sh"
                item.mode = 0o755
                archive.addfile(item)
                continue
            payload = b"#!/bin/sh\necho 0.2.4\n"
            item.size = len(payload)
            item.mode = 0o755
            archive.addfile(item, io.BytesIO(payload))


def _write_manifest(release_dir: Path, state: str) -> None:
    if state == "missing":
        return
    digest = hashlib.sha256((release_dir / ASSET_NAME).read_bytes()).hexdigest()
    if state == "missing-row":
        rows = [f"{digest}  another-asset.tar.gz"]
    elif state == "duplicate-row":
        rows = [f"{digest}  {ASSET_NAME}", f"{digest}  {ASSET_NAME}"]
    elif state == "mismatch":
        rows = [f"{'0' * 64}  {ASSET_NAME}"]
    else:
        rows = [f"{digest}  {ASSET_NAME}"]
    (release_dir / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _run_installer(
    tmp_path: Path,
    *,
    archive_layout: str = "valid",
    manifest_state: str = "valid",
    asset_present: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    dist_root = tmp_path / "dist"
    release_dir = dist_root / "releases" / "bluearch-aws-governance" / VERSION
    release_dir.mkdir(parents=True)
    if asset_present:
        _write_archive(release_dir / ASSET_NAME, archive_layout)
        _write_manifest(release_dir, manifest_state)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    _write_fake_uname(fake_bin)
    install_dir = tmp_path / "installed"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            "HOME": os.fspath(tmp_path / "home"),
            "INSTALL_DIR": os.fspath(install_dir),
            "BLUEARCH_VERSION": VERSION,
            "BLUEARCH_DIST_BASE_URL": dist_root.as_uri(),
            "BLUEARCH_INSTALL_CORE": "skip",
        }
    )
    result = subprocess.run(
        ["bash", os.fspath(INSTALLER)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return result, install_dir / BINARY_NAME


def test_installer_accepts_one_verified_root_executable(tmp_path):
    result, installed = _run_installer(tmp_path)

    assert result.returncode == 0, result.stderr
    assert installed.is_file()
    assert os.access(installed, os.X_OK)


@pytest.mark.parametrize(
    ("archive_layout", "manifest_state", "asset_present"),
    [
        ("valid", "valid", False),
        ("valid", "missing", True),
        ("valid", "missing-row", True),
        ("valid", "duplicate-row", True),
        ("valid", "mismatch", True),
        ("malformed", "valid", True),
        ("traversal", "valid", True),
        ("nested", "valid", True),
        ("duplicate", "valid", True),
        ("symlink", "valid", True),
    ],
)
def test_installer_fails_closed_without_installing(
    tmp_path,
    archive_layout,
    manifest_state,
    asset_present,
):
    result, installed = _run_installer(
        tmp_path,
        archive_layout=archive_layout,
        manifest_state=manifest_state,
        asset_present=asset_present,
    )

    assert result.returncode != 0
    assert not installed.exists()
