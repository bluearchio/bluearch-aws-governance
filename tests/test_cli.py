import os
import signal
import sys

import pytest
import typer
from typer.testing import CliRunner

from cloud_governance import cli

runner = CliRunner()


def _executable(path):
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _record(pid, command, *, start_token="stable-start", launcher_kind="public"):
    return cli.WebProcessRecord(
        schema=1,
        pid=pid,
        start_token=start_token,
        command_sha256=cli._command_sha256(command),
        launcher_kind=launcher_kind,
    )


def test_version_option_without_subcommand():
    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip()


@pytest.mark.parametrize("command", [["doctor"], ["catalog", "summary"]])
def test_core_install_recovery_trusts_exact_formula_before_install(monkeypatch, command):
    class UnavailableCore:
        def __init__(self, *args, **kwargs):
            pass

        def dependency_status(self):
            raise RuntimeError("core unavailable")

    monkeypatch.setattr(cli, "CoreClient", UnavailableCore)

    result = runner.invoke(cli.app, command)

    trust = "brew trust --formula bluearchio/tap/bluearch-aws-core"
    install = "brew install bluearchio/tap/bluearch-aws-core"
    assert result.exit_code == 1
    assert trust in result.stdout
    assert result.stdout.index(trust) < result.stdout.index(install)


def test_direct_web_start_is_hidden_and_requires_core_managed_start(monkeypatch):
    root_help = runner.invoke(cli.app, ["--help"])
    assert root_help.exit_code == 0
    assert "web" not in root_help.stdout

    monkeypatch.delenv("BLUEARCH_CORE_MANAGED_WEB_START", raising=False)
    result = runner.invoke(cli.app, ["web", "start", "--daemon"])

    assert result.exit_code == 1
    assert "bluearch-aws-core start --daemon" in result.stdout


def test_web_daemon_command_uses_uvicorn_when_running_from_python(monkeypatch, tmp_path):
    python = _executable(tmp_path / "python3.11")
    monkeypatch.setattr(sys, "argv", ["cloud_governance/cli.py"])
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


def test_web_daemon_command_uses_only_public_packaged_launcher(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    monkeypatch.setattr(sys, "argv", [os.fspath(launcher)])
    monkeypatch.setattr(sys, "executable", os.fspath(launcher))
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


def test_find_cli_executable_uses_public_path_and_never_queries_legacy(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    commands = []

    def which(command):
        commands.append(command)
        return os.fspath(launcher) if command == "bluearch-aws-governance" else None

    monkeypatch.setattr(sys, "argv", ["python"])
    monkeypatch.setattr(sys, "executable", sys.executable)
    monkeypatch.setattr(cli.shutil, "which", which)

    assert cli._find_cli_executable() == os.fspath(launcher)
    assert commands == ["bluearch-aws-governance"]


def test_find_cli_executable_accepts_public_absolute_argv(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    monkeypatch.setattr(sys, "argv", [os.fspath(launcher)])
    monkeypatch.setattr(sys, "executable", sys.executable)
    monkeypatch.setattr(cli.shutil, "which", lambda command: None)

    assert cli._find_cli_executable() == os.fspath(launcher)


def test_find_cli_executable_accepts_public_packaged_sys_executable(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    monkeypatch.setattr(sys, "argv", ["unrelated"])
    monkeypatch.setattr(sys, "executable", os.fspath(launcher))
    monkeypatch.setattr(cli.shutil, "which", lambda command: None)

    assert cli._find_cli_executable() == os.fspath(launcher)


def test_find_cli_executable_checks_public_fixed_location(monkeypatch):
    fixed = "/opt/homebrew/bin/bluearch-aws-governance"
    monkeypatch.setattr(sys, "argv", ["python"])
    monkeypatch.setattr(sys, "executable", sys.executable)
    monkeypatch.setattr(cli.shutil, "which", lambda command: None)
    monkeypatch.setattr(cli.os.path, "realpath", lambda path: os.fspath(path))
    monkeypatch.setattr(cli.os.path, "isfile", lambda path: os.fspath(path) == fixed)
    monkeypatch.setattr(cli.os, "access", lambda path, mode: os.fspath(path) == fixed)

    assert cli._find_cli_executable() == fixed


def test_find_cli_executable_rejects_public_symlink_to_legacy(monkeypatch, tmp_path):
    legacy = _executable(tmp_path / "cloud-governance")
    public_link = tmp_path / "bluearch-aws-governance"
    public_link.symlink_to(legacy)
    monkeypatch.setattr(sys, "argv", [os.fspath(public_link)])
    monkeypatch.setattr(sys, "executable", sys.executable)
    monkeypatch.setattr(cli.shutil, "which", lambda command: None)

    assert cli._find_cli_executable() is None


@pytest.mark.parametrize("location", ["argv", "sys_executable"])
def test_build_daemon_command_rejects_legacy_launcher(monkeypatch, tmp_path, location):
    legacy = _executable(tmp_path / "cloud-governance")
    public = _executable(tmp_path / "bluearch-aws-governance")
    monkeypatch.setattr(sys, "argv", [os.fspath(legacy)] if location == "argv" else ["python"])
    monkeypatch.setattr(
        sys,
        "executable",
        os.fspath(legacy) if location == "sys_executable" else sys.executable,
    )
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda command: os.fspath(public) if command == "bluearch-aws-governance" else None,
    )

    with pytest.raises(typer.Exit):
        cli._build_web_daemon_cmd("127.0.0.1", 8097)


def test_daemon_child_env_resets_pyinstaller_extraction(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", os.fspath(tmp_path / "bluearch-aws-governance"))
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/bluearch-aws-governance-bundle", raising=False)

    env = cli._daemon_child_env()

    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_web_ready_timeout_uses_env_override(monkeypatch):
    monkeypatch.setenv(cli.WEB_READY_TIMEOUT_ENV, "12.5")
    assert cli._web_ready_timeout_seconds() == 12.5

    monkeypatch.setenv(cli.WEB_READY_TIMEOUT_ENV, "invalid")
    assert cli._web_ready_timeout_seconds() == cli.DEFAULT_WEB_READY_TIMEOUT_SECONDS


def test_public_process_record_is_signaled_only_while_identity_matches(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve"
    record = _record(4312, command)
    alive = True
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: alive)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "stable-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)

    def kill(pid, process_signal):
        nonlocal alive
        signals.append((pid, process_signal))
        alive = False

    monkeypatch.setattr(cli.os, "kill", kill)

    assert cli._terminate_process(record) is True
    assert signals == [(4312, signal.SIGTERM)]


def test_source_uvicorn_process_record_is_signaled(monkeypatch, tmp_path):
    python = _executable(tmp_path / "python3.11")
    command = f"{python}\0-m\0uvicorn\0cloud_governance.web:app\0--port\08097"
    record = _record(4313, command, launcher_kind="source")
    alive = True
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: alive)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "stable-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)

    def kill(pid, process_signal):
        nonlocal alive
        signals.append((pid, process_signal))
        alive = False

    monkeypatch.setattr(cli.os, "kill", kill)

    assert cli._terminate_process(record) is True
    assert signals == [(4313, signal.SIGTERM)]


@pytest.mark.parametrize(
    ("actual_start", "actual_command"),
    [
        ("reused-pid", "/tmp/bluearch-aws-governance\0web\0serve"),
        ("stable-start", "/usr/local/bin/cloud-governance\0web\0serve"),
        ("stable-start", "/usr/bin/uvicorn\0unrelated.app:app"),
    ],
)
def test_stale_legacy_or_unrelated_process_is_never_signaled(
    monkeypatch,
    tmp_path,
    actual_start,
    actual_command,
):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    expected_command = f"{launcher}\0web\0serve"
    record = _record(4314, expected_command)
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: actual_start)
    monkeypatch.setattr(cli, "_process_command", lambda pid: actual_command)
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._terminate_process(record) is False
    assert signals == []


def test_conflicting_process_record_is_not_deleted_or_replaced(monkeypatch, tmp_path):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    record = _record(4315, "/opt/homebrew/bin/bluearch-aws-governance\0web\0serve")
    record_path.write_text(
        '{"schema":1,"pid":4315,"start_token":"stable-start",'
        f'"command_sha256":"{record.command_sha256}","launcher_kind":"public"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "reused-pid")
    monkeypatch.setattr(cli, "_process_command", lambda pid: "/usr/bin/unrelated")

    assert cli._stop_known_web_process() is False
    assert record_path.exists()


def test_legacy_numeric_pid_file_is_not_deleted(monkeypatch, tmp_path):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    record_path.write_text("4316\n", encoding="utf-8")
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)

    assert cli._stop_known_web_process() is False
    assert record_path.read_text(encoding="utf-8") == "4316\n"
