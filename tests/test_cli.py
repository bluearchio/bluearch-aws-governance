import os
import signal
import sys

import pytest
import typer
from typer.testing import CliRunner

from cloud_governance import cli

runner = CliRunner()
_REAL_PROCESS_UID = cli._process_uid


@pytest.fixture(autouse=True)
def _mocked_processes_belong_to_current_user(monkeypatch):
    monkeypatch.setattr(cli, "_process_uid", lambda pid: cli._current_uid())


def _executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _record(pid, command, *, start_token="stable-start", launcher_kind="public"):
    identity = cli.ProcessIdentity(
        pid=pid,
        start_token=start_token,
        command_sha256=cli._command_sha256(command),
        launcher_kind=launcher_kind,
    )
    return cli.WebProcessRecord(
        schema=2,
        supervisor=identity,
        listener=identity,
    )


def _runtime_record(supervisor_pid, listener_pid, command, *, launcher_kind="public"):
    supervisor = cli.ProcessIdentity(
        pid=supervisor_pid,
        start_token="supervisor-start",
        command_sha256=cli._command_sha256(command),
        launcher_kind=launcher_kind,
    )
    listener = cli.ProcessIdentity(
        pid=listener_pid,
        start_token="listener-start" if listener_pid != supervisor_pid else "supervisor-start",
        command_sha256=cli._command_sha256(command),
        launcher_kind=(
            "public-listener"
            if launcher_kind == "public" and listener_pid != supervisor_pid
            else launcher_kind
        ),
    )
    return cli.WebProcessRecord(schema=2, supervisor=supervisor, listener=listener)


def test_version_option_without_subcommand():
    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "bluearch-aws-governance 0.2.6"


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


def test_unique_nuitka_runtime_still_spawns_the_public_launcher(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    runtime = _executable(
        tmp_path
        / "runtime-tmp"
        / "bluearch-aws-governance_41001_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    monkeypatch.setattr(sys, "argv", [os.fspath(launcher)])
    monkeypatch.setattr(sys, "executable", os.fspath(runtime))
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


def test_listener_identity_accepts_only_the_exact_governance_nuitka_runtime(
    monkeypatch,
    tmp_path,
):
    runtime = _executable(
        tmp_path
        / "bluearch-aws-governance_41001_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    wrong_product = _executable(
        tmp_path
        / "bluearch-aws-ops_41001_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    home = tmp_path / "home"
    legacy_runtime = _executable(
        home
        / ".bluearch-aws-governance"
        / "bin"
        / "bluearch-aws-governance.bin"
    )
    monkeypatch.setenv("HOME", os.fspath(home))
    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: os.fspath(tmp_path))

    assert cli._is_expected_nuitka_listener_executable(
        os.fspath(legacy_runtime),
        pid=41002,
        parent_pid=41001,
        expected_supervisor_pid=41001,
        allow_missing=False,
    )
    assert cli._is_expected_nuitka_listener_executable(
        os.fspath(runtime),
        pid=41002,
        parent_pid=41001,
        expected_supervisor_pid=41001,
        allow_missing=False,
    )
    assert not cli._is_expected_nuitka_listener_executable(
        os.fspath(runtime),
        pid=41002,
        parent_pid=41001,
        expected_supervisor_pid=99999,
        allow_missing=False,
    )
    assert not cli._is_expected_nuitka_listener_executable(
        os.fspath(wrong_product),
        pid=41002,
        parent_pid=41001,
        expected_supervisor_pid=41001,
        allow_missing=False,
    )


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


def test_wait_for_web_daemon_records_only_owned_listener_with_exact_health(monkeypatch):
    command = "/tmp/bluearch-aws-governance\0web\0serve\0--port\08097"
    record = _runtime_record(4300, 4301, command)

    class Process:
        @staticmethod
        def poll():
            return None

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"service": "bluearch-aws-governance", "status": "ok"}

    monkeypatch.setattr(
        cli,
        "_owned_listener_identity",
        lambda supervisor, port, **kwargs: record.listener,
    )
    monkeypatch.setattr(cli.requests, "get", lambda url, timeout: Response())

    captured = cli._wait_for_web_daemon(Process(), record.supervisor, "127.0.0.1", 8097)

    assert captured == record


def test_failure_cleanup_terminates_listener_before_reaping_spawned_supervisor(monkeypatch):
    command = "/tmp/bluearch-aws-governance\0web\0serve\0--port\08097"
    record = _runtime_record(4302, 4303, command)
    calls = []

    class Process:
        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(
        cli,
        "_terminate_identity",
        lambda identity: calls.append(("listener", identity.pid)) or True,
    )
    monkeypatch.setattr(
        cli,
        "_managed_identity_matches",
        lambda identity: True,
    )
    monkeypatch.setattr(
        cli,
        "_terminate_spawned_supervisor",
        lambda process, identity: calls.append(("supervisor", identity.pid)) or True,
    )

    assert (
        cli._terminate_spawned_runtime(
            Process(),
            record.supervisor,
            record.listener,
            port=8097,
        )
        is True
    )
    assert calls == [("listener", 4303), ("supervisor", 4302)]


def test_process_record_write_failure_cleans_listener_and_supervisor(
    monkeypatch,
    tmp_path,
):
    command = "/tmp/bluearch-aws-governance\0web\0serve\0--port\08097"
    record = _runtime_record(4304, 4305, command)
    runtime_dir = tmp_path / "runtime"
    log_dir = tmp_path / "logs"
    log_file = log_dir / "governance.log"
    cleanup = []

    class Process:
        pid = record.supervisor.pid

    process = Process()

    monkeypatch.setattr(cli, "GOVERNANCE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(cli, "GOVERNANCE_LOG_DIR", log_dir)
    monkeypatch.setattr(cli, "GOVERNANCE_LOG_FILE", log_file)
    monkeypatch.setattr(cli, "_stop_known_web_process", lambda *_args: True)
    monkeypatch.setattr(cli, "_is_port_available", lambda *_args: True)
    monkeypatch.setattr(
        cli,
        "_build_web_daemon_cmd",
        lambda *_args: ["/tmp/bluearch-aws-governance", "web", "serve"],
    )
    monkeypatch.setattr(cli, "_daemon_child_env", lambda: {})
    monkeypatch.setattr(cli.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(
        cli,
        "_capture_process_identity",
        lambda *_args, **_kwargs: record.supervisor,
    )
    monkeypatch.setattr(cli, "_wait_for_web_daemon", lambda *_args: record)
    monkeypatch.setattr(
        cli,
        "_write_web_process_record",
        lambda _record: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(
        cli,
        "_terminate_spawned_runtime",
        lambda *args, **kwargs: cleanup.append((args, kwargs)) or True,
    )

    with pytest.raises(typer.Exit):
        cli._start_web_daemon("127.0.0.1", 8097)

    assert cleanup == [
        (
            (process, record.supervisor, record.listener),
            {"port": 8097},
        )
    ]


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


def test_public_process_record_survives_homebrew_cleanup_of_recorded_executable(
    monkeypatch,
    tmp_path,
):
    launcher = _executable(
        tmp_path / "Cellar" / "bluearch-aws-governance" / "0.2.5" / "bin" / "bluearch-aws-governance"
    )
    command = "\0".join(
        [os.fspath(launcher), "web", "serve", "--host", "127.0.0.1", "--port", "8097"]
    )
    record = _record(4317, command)
    launcher.unlink()
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

    assert cli._is_allowed_managed_command(command, "public") is False
    assert cli._terminate_process(record) is True
    assert signals == [(4317, signal.SIGTERM)]


def test_packaged_runtime_terminates_verified_listener_before_supervisor(
    monkeypatch,
    tmp_path,
):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve\0--port\08097"
    record = _runtime_record(4400, 4401, command)
    alive = {4400, 4401}
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: pid in alive)
    monkeypatch.setattr(
        cli,
        "_process_start_token",
        lambda pid: "supervisor-start" if pid == 4400 else "listener-start",
    )
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)

    def kill(pid, process_signal):
        signals.append((pid, process_signal))
        alive.discard(pid)

    monkeypatch.setattr(cli.os, "kill", kill)

    assert cli._terminate_process(record) is True
    assert signals == [(4401, signal.SIGTERM), (4400, signal.SIGTERM)]


def test_recorded_orphan_listener_is_stopped_after_supervisor_exits(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    runtime = _executable(
        tmp_path
        / "bluearch-aws-governance_4410_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    supervisor_command = f"{launcher}\0web\0serve\0--port\08097"
    listener_command = f"{runtime}\0web\0serve\0--port\08097"
    record = cli.WebProcessRecord(
        schema=2,
        supervisor=cli.ProcessIdentity(
            pid=4410,
            start_token="supervisor-start",
            command_sha256=cli._command_sha256(supervisor_command),
            launcher_kind="public",
            executable=os.fspath(launcher),
            parent_pid=1,
        ),
        listener=cli.ProcessIdentity(
            pid=4411,
            start_token="listener-start",
            command_sha256=cli._command_sha256(listener_command),
            launcher_kind="public-listener",
            executable=os.fspath(runtime),
            parent_pid=4410,
        ),
    )
    alive = {4411}
    signals = []

    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: os.fspath(tmp_path))
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: pid in alive)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "listener-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: listener_command)
    monkeypatch.setattr(cli, "_process_executable_path", lambda pid: os.fspath(runtime))
    monkeypatch.setattr(cli, "_process_parent_pid", lambda pid: 1)

    def kill(pid, process_signal):
        signals.append((pid, process_signal))
        alive.discard(pid)

    monkeypatch.setattr(cli.os, "kill", kill)

    assert cli._terminate_process(record) is True
    assert signals == [(4411, signal.SIGTERM)]


def test_changed_listener_identity_blocks_all_runtime_signals(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve\0--port\08097"
    record = _runtime_record(4420, 4421, command)
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(
        cli,
        "_process_start_token",
        lambda pid: "supervisor-start" if pid == 4420 else "reused-listener",
    )
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._terminate_process(record) is False
    assert signals == []


def test_legacy_supervisor_record_discovers_and_stops_owned_listener_first(
    monkeypatch,
    tmp_path,
):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    runtime = _executable(
        tmp_path
        / "bluearch-aws-governance_4430_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    command = f"{launcher}\0web\0serve\0--port\08097"
    listener_command = f"{runtime}\0web\0serve\0--port\08097"
    supervisor = cli.ProcessIdentity(
        pid=4430,
        start_token="supervisor-start",
        command_sha256=cli._command_sha256(command),
        launcher_kind="public",
    )
    record = cli.WebProcessRecord(schema=1, supervisor=supervisor, listener=None)
    alive = {4430, 4431}
    signals = []

    monkeypatch.setattr(cli, "_listener_pids", lambda port: {4431})
    monkeypatch.setattr(cli, "_process_parent_pid", lambda pid: 4430)
    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: os.fspath(tmp_path))
    monkeypatch.setattr(
        cli,
        "_process_executable_path",
        lambda pid: os.fspath(launcher if pid == 4430 else runtime),
    )
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: pid in alive)
    monkeypatch.setattr(
        cli,
        "_process_start_token",
        lambda pid: "supervisor-start" if pid == 4430 else "listener-start",
    )
    monkeypatch.setattr(
        cli,
        "_process_command",
        lambda pid: command if pid == 4430 else listener_command,
    )
    monkeypatch.setattr(cli, "_probe_governance_health", lambda host, port: True)

    def kill(pid, process_signal):
        signals.append((pid, process_signal))
        alive.discard(pid)

    monkeypatch.setattr(cli.os, "kill", kill)

    assert cli._terminate_process(record) is True
    assert signals == [(4431, signal.SIGTERM), (4430, signal.SIGTERM)]


def test_v025_orphan_listener_is_recovered_after_legacy_supervisor_exits(
    monkeypatch,
    tmp_path,
):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    launcher = tmp_path / "Cellar" / "bluearch-aws-governance" / "0.2.5" / "bin" / "bluearch-aws-governance"
    runtime = _executable(
        tmp_path
        / "bluearch-aws-governance_4450_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    supervisor_command = "\0".join(
        [os.fspath(launcher), "web", "serve", "--host", "127.0.0.1", "--port", "8097"]
    )
    listener_command = "\0".join(
        [os.fspath(runtime), "web", "serve", "--host", "127.0.0.1", "--port", "8097"]
    )
    record_path.write_text(
        '{"schema":1,"pid":4450,"start_token":"supervisor-start",'
        f'"command_sha256":"{cli._command_sha256(supervisor_command)}",'
        '"launcher_kind":"public"}\n',
        encoding="utf-8",
    )
    alive = {4451}
    signals = []
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: os.fspath(tmp_path))
    monkeypatch.setattr(cli, "_listener_pids", lambda port: {4451})
    monkeypatch.setattr(cli, "_process_parent_pid", lambda pid: 1)
    monkeypatch.setattr(cli, "_process_executable_path", lambda pid: os.fspath(runtime))
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "listener-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: listener_command)
    monkeypatch.setattr(cli, "_probe_governance_health", lambda host, port: True)
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: pid in alive)

    def kill(pid, process_signal):
        signals.append((pid, process_signal))
        alive.discard(pid)

    monkeypatch.setattr(cli.os, "kill", kill)

    assert cli._stop_known_web_process() is True
    assert signals == [(4451, signal.SIGTERM)]
    assert not record_path.exists()


def test_runtime_record_round_trip_preserves_supervisor_and_listener(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    record_path = runtime_dir / "bluearch-aws-governance-web.json"
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    listener_executable = _executable(
        tmp_path
        / "bluearch-aws-governance_4440_1234567890_123456"
        / "bluearch-aws-governance.bin"
    )
    command = f"{launcher}\0web\0serve\0--port\08097"
    listener_command = f"{listener_executable}\0web\0serve\0--port\08097"
    supervisor = cli.ProcessIdentity(
        pid=4440,
        start_token="supervisor-start",
        command_sha256=cli._command_sha256(command),
        launcher_kind="public",
        executable=os.fspath(launcher),
        parent_pid=1,
    )
    listener = cli.ProcessIdentity(
        pid=4441,
        start_token="listener-start",
        command_sha256=cli._command_sha256(listener_command),
        launcher_kind="public-listener",
        executable=os.fspath(listener_executable),
        parent_pid=4440,
    )
    record = cli.WebProcessRecord(schema=2, supervisor=supervisor, listener=listener)
    monkeypatch.setattr(cli, "GOVERNANCE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)

    cli._write_web_process_record(record)

    assert cli._read_web_process_record() == record
    assert record_path.stat().st_mode & 0o777 == 0o600


def test_record_creation_rejects_missing_public_executable(monkeypatch, tmp_path):
    launcher = tmp_path / "bluearch-aws-governance"
    command = f"{launcher}\0web\0serve"
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "stable-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError):
        cli._capture_process_identity(4318, "public")


def test_record_creation_rejects_process_owned_by_another_uid(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve"
    current_uid = cli._current_uid()
    assert current_uid is not None
    monkeypatch.setattr(cli, "_process_uid", lambda pid: current_uid + 1)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "stable-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError):
        cli._capture_process_identity(4318, "public")


def test_process_uid_uses_ps_effective_uid_when_proc_is_unavailable(monkeypatch):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return cli.subprocess.CompletedProcess(command, 0, stdout="501\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", run)

    assert _REAL_PROCESS_UID(99999999) == 501
    assert commands == [["ps", "-p", "99999999", "-o", "uid="]]


def test_public_process_validation_rejects_symlink_loop(tmp_path):
    launcher = tmp_path / "bluearch-aws-governance"
    launcher.symlink_to(launcher)
    command = f"{launcher}\0web\0serve"

    assert cli._is_allowed_managed_command(command, "public") is False


def test_pid_reuse_during_immediate_revalidation_is_never_signaled(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve"
    record = _record(4319, command)
    start_tokens = iter(["stable-start", "reused-pid"])
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: next(start_tokens))
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._terminate_process(record) is False
    assert signals == []


def test_process_uid_mismatch_is_never_signaled(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve"
    record = _record(4321, command)
    current_uid = cli._current_uid()
    assert current_uid is not None
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_uid", lambda pid: current_uid + 1)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "stable-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._terminate_process(record) is False
    assert signals == []


def test_process_uid_is_revalidated_immediately_before_sigterm(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve"
    record = _record(4322, command)
    current_uid = cli._current_uid()
    assert current_uid is not None
    process_uids = iter([current_uid, current_uid + 1])
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_uid", lambda pid: next(process_uids))
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "stable-start")
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._terminate_process(record) is False
    assert signals == []


def test_process_identity_is_revalidated_before_sigkill(monkeypatch, tmp_path):
    launcher = _executable(tmp_path / "bluearch-aws-governance")
    command = f"{launcher}\0web\0serve"
    record = _record(4320, command)
    start_tokens = iter(
        [
            "stable-start",
            "stable-start",
            "stable-start",
            "stable-start",
            "stable-start",
            "reused-pid",
        ]
    )
    signals = []

    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: next(start_tokens))
    monkeypatch.setattr(cli, "_process_command", lambda pid: command)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._terminate_process(record) is False
    assert signals == [(4320, signal.SIGTERM)]


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
        f'"command_sha256":"{record.supervisor.command_sha256}","launcher_kind":"public"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_process_start_token", lambda pid: "reused-pid")
    monkeypatch.setattr(cli, "_process_command", lambda pid: "/usr/bin/unrelated")

    assert cli._stop_known_web_process() is False
    assert record_path.exists()


def test_live_legacy_numeric_pid_file_is_not_deleted_or_signaled(monkeypatch, tmp_path):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    record_path.write_text("4316\n", encoding="utf-8")
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: True)
    monkeypatch.setattr(cli, "_is_port_available", lambda host, port: True)
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._stop_known_web_process() is False
    assert record_path.read_text(encoding="utf-8") == "4316\n"
    assert signals == []


@pytest.mark.parametrize("mode", [0o620, 0o602])
def test_writable_process_record_is_not_trusted_deleted_or_signaled(
    monkeypatch,
    tmp_path,
    mode,
):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    record_path.write_text("4316\n", encoding="utf-8")
    record_path.chmod(mode)
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: False)
    monkeypatch.setattr(cli, "_is_port_available", lambda host, port: True)
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._stop_known_web_process() is False
    assert record_path.exists()
    assert signals == []


@pytest.mark.parametrize(
    "record_text",
    [
        "4316\n",
        "{malformed\n",
        '{"schema":1,"pid":4316}\n',
    ],
)
def test_stale_untrusted_record_is_cleaned_in_one_start_when_port_is_free(
    monkeypatch,
    tmp_path,
    record_text,
):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    record_path.write_text(record_text, encoding="utf-8")
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "_is_pid_running", lambda pid: False)
    monkeypatch.setattr(cli, "_is_port_available", lambda host, port: True)
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._stop_known_web_process() is True
    assert not record_path.exists()
    assert signals == []


def test_corrupt_record_is_retained_when_foreign_listener_occupies_port(monkeypatch, tmp_path):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    record_path.write_text("{malformed\n", encoding="utf-8")
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "_is_port_available", lambda host, port: False)
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    assert cli._stop_known_web_process() is False
    assert record_path.exists()
    assert signals == []


def test_listener_without_record_is_never_signaled(monkeypatch, tmp_path):
    record_path = tmp_path / "bluearch-aws-governance-web.json"
    monkeypatch.setattr(cli, "GOVERNANCE_PID_FILE", record_path)
    monkeypatch.setattr(cli, "GOVERNANCE_RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(cli, "GOVERNANCE_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cli, "_is_port_available", lambda host, port: False)
    signals = []
    monkeypatch.setattr(cli.os, "kill", lambda pid, process_signal: signals.append((pid, process_signal)))

    with pytest.raises(typer.Exit):
        cli._start_web_daemon("127.0.0.1", 8097)

    assert signals == []
