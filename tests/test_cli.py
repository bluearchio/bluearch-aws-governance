import os
import sys

import pytest
import typer
from typer.testing import CliRunner

from cloud_governance import cli

runner = CliRunner()


def test_version_option_without_subcommand():
    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip()


def test_web_start_requires_core_managed_start(monkeypatch):
    monkeypatch.delenv("BLUEARCH_CORE_MANAGED_WEB_START", raising=False)

    with pytest.raises(typer.Exit):
        cli.start_web(host="127.0.0.1", port=8097, daemon=True)


def test_web_daemon_command_uses_uvicorn_when_running_from_python(monkeypatch, tmp_path):
    python = tmp_path / "python3.11"
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    monkeypatch.setattr(sys, "executable", os.fspath(python))

    cmd = cli._build_web_daemon_cmd("127.0.0.1", 8097)

    assert cmd == [
        os.fspath(python),
        "-m",
        "uvicorn",
        "cloud_governance.web:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8097",
    ]


def test_web_daemon_command_uses_cli_launcher_when_packaged(monkeypatch, tmp_path):
    launcher = tmp_path / "cloud-governance"
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)

    binary = tmp_path / "cloud-governance.bin"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)

    monkeypatch.setattr(sys, "argv", [os.fspath(launcher)])
    monkeypatch.setattr(sys, "executable", os.fspath(binary))
    monkeypatch.setattr(cli.shutil, "which", lambda command: None)

    cmd = cli._build_web_daemon_cmd("127.0.0.1", 8097)

    assert cmd == [
        os.fspath(launcher),
        "web",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "8097",
    ]


def test_web_daemon_command_uses_cli_launcher_when_started_from_console_script(monkeypatch, tmp_path):
    launcher = tmp_path / "cloud-governance"
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)

    python = tmp_path / "python3.11"
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)

    monkeypatch.setattr(sys, "argv", [os.fspath(launcher)])
    monkeypatch.setattr(sys, "executable", os.fspath(python))
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda command: os.fspath(launcher) if command == "cloud-governance" else None,
    )

    cmd = cli._build_web_daemon_cmd("127.0.0.1", 8097)

    assert cmd == [
        os.fspath(launcher),
        "web",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "8097",
    ]


def test_daemon_child_env_resets_pyinstaller_extraction(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", os.fspath(tmp_path / "cloud-governance.bin"))
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/cloud-governance-bundle", raising=False)

    env = cli._daemon_child_env()

    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_web_ready_timeout_uses_env_override(monkeypatch):
    monkeypatch.setenv(cli.WEB_READY_TIMEOUT_ENV, "12.5")
    assert cli._web_ready_timeout_seconds() == 12.5

    monkeypatch.setenv(cli.WEB_READY_TIMEOUT_ENV, "invalid")
    assert cli._web_ready_timeout_seconds() == cli.DEFAULT_WEB_READY_TIMEOUT_SECONDS
