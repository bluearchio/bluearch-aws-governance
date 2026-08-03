"""Governance Hub CLI."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
import typer
from rich.console import Console
from rich.table import Table

try:
    import psutil
except ImportError:  # pragma: no cover - the packaged dependency is required in production
    psutil = None

from . import __version__
from .catalog_assets import is_catalog_source, resolve_catalog_source_path
from .config import MINIMUM_CORE_VERSION
from .core_client import CoreClient
from .support import load_bluearch_executable_mapping

app = typer.Typer(help="BlueArch Governance Hub")
catalog_app = typer.Typer(help="Misconfiguration catalog commands")
web_app = typer.Typer(help="Local API commands managed by bluearch-aws-core")
console = Console()

PUBLIC_GOVERNANCE_EXECUTABLE = "bluearch-aws-governance"
LEGACY_GOVERNANCE_EXECUTABLE = "cloud-governance"
PUBLIC_CORE_EXECUTABLE = "bluearch-aws-core"
GOVERNANCE_HOME = Path(os.environ.get("GOVERNANCE_HUB_HOME", "~/.cloud-governance")).expanduser()
GOVERNANCE_RUNTIME_DIR = GOVERNANCE_HOME / "runtime"
GOVERNANCE_LOG_DIR = GOVERNANCE_HOME / "logs"
GOVERNANCE_PID_FILE = GOVERNANCE_RUNTIME_DIR / "bluearch-aws-governance-web.json"
GOVERNANCE_LOG_FILE = GOVERNANCE_LOG_DIR / "web-server.log"
GOVERNANCE_HEALTH_PATH = "/api/v1/health"
DEFAULT_WEB_READY_TIMEOUT_SECONDS = 90.0
WEB_READY_POLL_INTERVAL_SECONDS = 0.1
WEB_READY_TIMEOUT_ENV = "CLOUD_GOVERNANCE_WEB_READY_TIMEOUT_SECONDS"
NUITKA_RUNTIME_DIRECTORY_PATTERN = re.compile(
    rf"^{re.escape(PUBLIC_GOVERNANCE_EXECUTABLE)}_([0-9]+)_([0-9]+)_([0-9]+)$"
)


@dataclass(frozen=True)
class ProcessIdentity:
    """Stable identity for one process in the managed Governance runtime."""

    pid: int
    start_token: str
    command_sha256: str
    launcher_kind: str
    executable: str | None = None
    parent_pid: int | None = None


@dataclass(frozen=True)
class WebProcessRecord:
    """Stable supervisor and listener identities for a Governance web runtime."""

    schema: int
    supervisor: ProcessIdentity
    listener: ProcessIdentity | None

    @property
    def pid(self) -> int:
        """Retain the legacy supervisor PID surface used by status messages."""
        return self.supervisor.pid


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
):
    if version:
        console.print(f"{PUBLIC_GOVERNANCE_EXECUTABLE} {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def doctor():
    """Check whether bluearch-aws-core is available."""
    try:
        core = CoreClient(timeout=3)
        status = core.dependency_status()
        health = core.health()
    except Exception as exc:
        console.print("[red]bluearch-aws-core is required before using Governance Hub.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        console.print(f"[cyan]Required version:[/cyan] {PUBLIC_CORE_EXECUTABLE} >= {MINIMUM_CORE_VERSION}")
        console.print(f"[cyan]Start it with:[/cyan] {PUBLIC_CORE_EXECUTABLE} start --daemon")
        console.print("[cyan]Trust it with:[/cyan] brew trust --formula bluearchio/tap/bluearch-aws-core")
        console.print("[cyan]Install it with:[/cyan] brew install bluearchio/tap/bluearch-aws-core")
        raise typer.Exit(1) from exc
    console.print("[green]bluearch-aws-core is available[/green]")
    console.print(f"Core version: {status.get('core_version') or health.get('version')}")
    console.print(f"Required version: >= {MINIMUM_CORE_VERSION}")
    console.print(f"DB ready: {health.get('db_ready')}")


@catalog_app.command("import")
def import_catalog(
    source: Path | None = typer.Option(None, "--source", help="Path to a catalog source. Defaults to the bundled Governance Hub catalog."),
    bluearch_api: Path | None = typer.Option(None, "--bluearch-api", help="Optional path to a local ops API source tree for evaluator mapping."),
):
    """Import the Governance Hub catalog into core-owned tables."""
    _ensure_core_dependency()
    if source:
        source_path = source.expanduser().resolve()
        if not is_catalog_source(source_path):
            console.print(f"[red]No by-service catalog JSON files found under {source_path}[/red]")
            raise typer.Exit(1)
    else:
        source_path = resolve_catalog_source_path()
        if source_path is None:
            console.print("[red]Bundled Governance Hub catalog is not available.[/red]")
            raise typer.Exit(1)
    bluearch_api_path = bluearch_api.expanduser().resolve() if bluearch_api else None
    mapping = load_bluearch_executable_mapping(str(bluearch_api_path)) if bluearch_api_path else {}
    response = CoreClient(timeout=60).import_catalog(str(source_path), executable_mapping=mapping)
    console.print(f"Files seen: {response['files_seen']}")
    console.print(f"Entries imported: {response['entries_imported']}")
    console.print(f"Executable mappings: {response['executable_mappings']}")


@catalog_app.command("summary")
def catalog_summary():
    """Show catalog totals from bluearch-aws-core."""
    _ensure_core_dependency()
    summary = CoreClient().catalog_summary()
    console.print(f"Total: {summary['total']}")
    console.print(f"Executable: {summary['executable']}")
    console.print(f"Unsupported: {summary['unsupported']}")


@catalog_app.command("verify")
def verify_bundled_catalog():
    """Verify that the bundled, read-only catalog is present and parseable."""
    source_path = resolve_catalog_source_path()
    if source_path is None:
        console.print("[red]Bundled Governance Hub catalog is not available.[/red]")
        raise typer.Exit(1)
    by_service = source_path / "by-service"
    if not by_service.is_dir():
        by_service = source_path / "data" / "by-service"
    files = sorted(by_service.glob("*.json"))
    entries = 0
    try:
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("misconfigurations")
            if not isinstance(rows, list):
                raise ValueError(f"{path.name} has no misconfigurations list")
            entries += len(rows)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        console.print(f"[red]Bundled catalog verification failed: {exc}[/red]")
        raise typer.Exit(1) from exc
    if not files or entries <= 0:
        console.print("[red]Bundled catalog contains no entries.[/red]")
        raise typer.Exit(1)
    console.print(f"Bundled catalog files: {len(files)}")
    console.print(f"Bundled catalog entries: {entries}")


@catalog_app.command("list")
def list_catalog(
    service: str | None = typer.Option(None, "--service"),
    executable: bool | None = typer.Option(None, "--executable/--all-support"),
    limit: int = typer.Option(25, "--limit"),
):
    """List catalog entries from bluearch-aws-core."""
    _ensure_core_dependency()
    response = CoreClient().catalog(service=service, executable=executable, limit=limit)
    table = Table(title=f"Governance Catalog ({response['total']} total)")
    table.add_column("ID", overflow="fold")
    table.add_column("Service")
    table.add_column("Support")
    table.add_column("Title", overflow="fold")
    for entry in response["entries"]:
        table.add_row(
            entry["catalog_id"],
            entry.get("service") or "",
            "executable" if entry.get("executable") else "unsupported",
            entry.get("title") or "",
        )
    console.print(table)


@web_app.command("start", hidden=True)
def start_web(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8097, "--port", help="Port to bind."),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as a background daemon."),
):
    """Start the Governance Hub local API shell."""
    _ensure_core_managed_web_start()
    _ensure_core_dependency()
    if daemon:
        _start_web_daemon(host, port)
        return

    _run_web_server(host, port)


@web_app.command("serve", hidden=True)
def serve_web(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8097, "--port", help="Port to bind."),
):
    """Run the Governance Hub web server in the foreground."""
    _run_web_server(host, port)


@web_app.command("stop")
def stop_web():
    """Stop the Governance Hub web daemon."""
    if not GOVERNANCE_PID_FILE.exists():
        console.print("[yellow]Governance Hub web is not running.[/yellow]")
        return
    record = _read_web_process_record()
    if record is None:
        if _discard_untrusted_web_process_record_if_safe("127.0.0.1", 8097):
            console.print("[yellow]Governance Hub web is not running.[/yellow]")
            return
        _print_untrusted_process_record_warning()
        return
    managed_record = _record_with_recovered_legacy_listener(
        record,
        "127.0.0.1",
        8097,
    )
    if not _record_has_live_process(managed_record):
        if not _is_port_available("127.0.0.1", 8097):
            _print_untrusted_process_record_warning(record.pid)
            return
        _unlink_web_process_record(record)
        console.print("[yellow]Governance Hub web is not running.[/yellow]")
        return
    if not _terminate_process(managed_record, host="127.0.0.1", port=8097):
        _print_untrusted_process_record_warning(record.pid)
        return
    _unlink_web_process_record(record)
    console.print("[green]Stopped Governance Hub web.[/green]")


@web_app.command("status")
def status_web(host: str = "127.0.0.1", port: int = 8097):
    """Show Governance Hub web daemon status."""
    record = _read_web_process_record()
    running = bool(record and _managed_process_matches(record))
    console.print(f"Process: {'running' if running else 'stopped'}")
    if record:
        console.print(f"PID: {record.pid}")
        if _is_pid_running(record.pid) and not running:
            console.print("[yellow]PID record does not match a managed Governance process; no signal will be sent.[/yellow]")
    try:
        response = requests.get(f"http://{host}:{port}{GOVERNANCE_HEALTH_PATH}", timeout=2)
        console.print(f"API: {response.status_code} {response.json().get('status')}")
    except Exception as exc:
        console.print(f"API: unavailable ({exc})")


def _ensure_core_managed_web_start() -> None:
    if os.environ.get("BLUEARCH_CORE_MANAGED_WEB_START") == "1":
        return
    console.print("[yellow]Governance Hub web startup is managed by bluearch-aws-core.[/yellow]")
    console.print(f"[cyan]Run:[/cyan] {PUBLIC_CORE_EXECUTABLE} start --daemon")
    raise typer.Exit(1)


def _ensure_core_dependency() -> None:
    try:
        CoreClient(timeout=3).dependency_status()
    except Exception as exc:
        console.print("[red]bluearch-aws-core is required before using Governance Hub.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        console.print(f"[cyan]Required version:[/cyan] {PUBLIC_CORE_EXECUTABLE} >= {MINIMUM_CORE_VERSION}")
        console.print(f"[cyan]Start it with:[/cyan] {PUBLIC_CORE_EXECUTABLE} start --daemon")
        console.print("[cyan]Trust it with:[/cyan] brew trust --formula bluearchio/tap/bluearch-aws-core")
        console.print("[cyan]Install it with:[/cyan] brew install bluearchio/tap/bluearch-aws-core")
        raise typer.Exit(1) from exc


def _start_web_daemon(host: str, port: int) -> None:
    GOVERNANCE_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    GOVERNANCE_LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not _stop_known_web_process(host, port):
        raise typer.Exit(1)
    if not _is_port_available(host, port):
        console.print(f"[red]Port {port} is already in use by another process.[/red]")
        raise typer.Exit(1)

    cmd = _build_web_daemon_cmd(host, port)
    env = _daemon_child_env()
    with GOVERNANCE_LOG_FILE.open("ab") as log:
        process = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    supervisor: ProcessIdentity | None = None
    try:
        supervisor = _capture_process_identity(
            process.pid,
            "source" if _is_source_daemon_command(cmd) else "public",
        )
    except RuntimeError as exc:
        _terminate_spawned_runtime(process, supervisor, None, port=port)
        console.print(f"[red]Unable to establish a stable Governance process identity: {exc}[/red]")
        raise typer.Exit(1) from exc
    record = _wait_for_web_daemon(process, supervisor, host, port)
    try:
        _write_web_process_record(record)
    except (OSError, ValueError) as exc:
        cleaned = _terminate_spawned_runtime(
            process,
            supervisor,
            record.listener,
            port=port,
        )
        console.print(
            f"[red]Unable to persist the Governance process identity: {exc}[/red]"
        )
        if not cleaned:
            console.print(
                f"[red]The failed Governance daemon could not be safely cleaned up; "
                f"inspect PID {process.pid} and port {port}.[/red]"
            )
        raise typer.Exit(1) from exc
    console.print(f"[green]Governance Hub web started on http://{host}:{port} (pid {process.pid}).[/green]")
    console.print(f"[dim]Log: {GOVERNANCE_LOG_FILE}[/dim]")


def _run_web_server(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run("cloud_governance.web:app", host=host, port=port, workers=1)


def _build_web_daemon_cmd(host: str, port: int) -> list[str]:
    if _legacy_launcher_requested():
        console.print(f"[red]Refusing deprecated executable {LEGACY_GOVERNANCE_EXECUTABLE}.[/red]")
        console.print(f"[dim]Run {PUBLIC_GOVERNANCE_EXECUTABLE} through {PUBLIC_CORE_EXECUTABLE} instead.[/dim]")
        raise typer.Exit(1)
    if _should_use_python_uvicorn_daemon():
        return [
            sys.executable,
            "-m",
            "uvicorn",
            "cloud_governance.web:app",
            "--host",
            host,
            "--port",
            str(port),
        ]

    cli_executable = _find_cli_executable()
    if cli_executable is None:
        console.print("[red]Unable to find an executable Governance Hub launcher for daemon mode.[/red]")
        console.print(f"[dim]Run `{PUBLIC_CORE_EXECUTABLE} start --daemon` to start the managed dashboard.[/dim]")
        raise typer.Exit(1)

    return [
        cli_executable,
        "web",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
    ]


def _should_use_python_uvicorn_daemon() -> bool:
    """Use python -m uvicorn only for source checkouts, not packaged CLI runs."""
    if not _is_python_executable(sys.executable):
        return False
    if hasattr(sys, "_MEIPASS") or os.environ.get("PYINSTALLER_RESET_ENVIRONMENT") == "1":
        return False
    argv0 = Path(sys.argv[0]).name.lower()
    if argv0 == PUBLIC_GOVERNANCE_EXECUTABLE:
        return False
    return True


def _daemon_child_env() -> dict[str, str]:
    env = os.environ.copy()
    if hasattr(sys, "_MEIPASS") or not _is_python_executable(sys.executable):
        # PyInstaller onefile apps otherwise let the short-lived parent own the
        # extraction directory. When the parent exits, the child keeps a stale
        # sys._MEIPASS path and bundled frontend assets disappear.
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _is_python_executable(executable: str) -> bool:
    name = Path(executable).name.lower()
    return name in ("python", "python3") or name.startswith("python3.")


def _find_cli_executable() -> str | None:
    explicit_candidates = (
        sys.argv[0] if Path(sys.argv[0]).name == PUBLIC_GOVERNANCE_EXECUTABLE else None,
        sys.executable if Path(sys.executable).name == PUBLIC_GOVERNANCE_EXECUTABLE else None,
    )
    for candidate in explicit_candidates:
        if candidate:
            return _pin_public_cli_executable(candidate)

    path_candidate = shutil.which(PUBLIC_GOVERNANCE_EXECUTABLE)
    if path_candidate:
        return _pin_public_cli_executable(path_candidate)

    for candidate in (
        Path.home() / ".local" / "bin" / PUBLIC_GOVERNANCE_EXECUTABLE,
        Path("/opt/homebrew/bin") / PUBLIC_GOVERNANCE_EXECUTABLE,
        Path("/usr/local/bin") / PUBLIC_GOVERNANCE_EXECUTABLE,
    ):
        pinned = _pin_public_cli_executable(candidate)
        if pinned:
            return pinned
    return None


def _pin_public_cli_executable(candidate: str | os.PathLike[str]) -> str | None:
    path = os.fspath(candidate)
    if not os.path.isabs(path) and not os.path.dirname(path):
        path = shutil.which(path) or path
    else:
        path = os.path.abspath(path)
    resolved = os.path.realpath(os.path.abspath(path))
    if (
        Path(path).name != PUBLIC_GOVERNANCE_EXECUTABLE
        or Path(resolved).name != PUBLIC_GOVERNANCE_EXECUTABLE
    ):
        return None
    if os.path.isfile(resolved) and os.access(resolved, os.X_OK):
        return resolved
    return None


def _legacy_launcher_requested() -> bool:
    return any(
        _is_legacy_executable_name(Path(value).name)
        for value in (sys.argv[0], sys.executable)
        if value
    )


def _is_legacy_executable_name(name: str) -> bool:
    lowered = name.lower()
    return lowered == LEGACY_GOVERNANCE_EXECUTABLE or lowered.startswith(
        f"{LEGACY_GOVERNANCE_EXECUTABLE}."
    )


def _stop_known_web_process(host: str = "127.0.0.1", port: int = 8097) -> bool:
    if not GOVERNANCE_PID_FILE.exists():
        return True
    record = _read_web_process_record()
    if record is None:
        if _discard_untrusted_web_process_record_if_safe(host, port):
            return True
        _print_untrusted_process_record_warning()
        return False
    managed_record = _record_with_recovered_legacy_listener(record, host, port)
    if not _record_has_live_process(managed_record):
        if not _is_port_available(host, port):
            _print_untrusted_process_record_warning(record.pid)
            return False
        _unlink_web_process_record(record)
        return True
    if not _terminate_process(managed_record, host=host, port=port):
        _print_untrusted_process_record_warning(record.pid)
        return False
    _unlink_web_process_record(record)
    console.print(f"[yellow]Stopped existing Governance Hub web process: {record.pid}[/yellow]")
    return True


def _wait_for_web_daemon(
    process: subprocess.Popen,
    supervisor: ProcessIdentity,
    host: str,
    port: int,
) -> WebProcessRecord:
    url = f"http://{_test_host(host)}:{port}{GOVERNANCE_HEALTH_PATH}"
    deadline = time.monotonic() + _web_ready_timeout_seconds()
    listener: ProcessIdentity | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _terminate_spawned_runtime(process, supervisor, listener, port=port)
            console.print(f"[red]Governance Hub web exited before it became ready. See log: {GOVERNANCE_LOG_FILE}[/red]")
            raise typer.Exit(1)
        candidate_listener = _owned_listener_identity(
            supervisor,
            port,
            allow_missing_public_executable=False,
        )
        if candidate_listener is not None:
            listener = candidate_listener
        elif listener is not None and not _managed_identity_matches(listener):
            listener = None
        try:
            response = requests.get(url, timeout=0.2)
            payload = response.json()
            if listener is not None and _is_valid_governance_health(
                response.status_code,
                payload,
            ):
                return WebProcessRecord(
                    schema=2,
                    supervisor=supervisor,
                    listener=listener,
                )
        except (requests.RequestException, ValueError):
            pass
        time.sleep(WEB_READY_POLL_INTERVAL_SECONDS)
    _terminate_spawned_runtime(process, supervisor, listener, port=port)
    console.print(f"[red]Governance Hub web did not become ready on {url}. See log: {GOVERNANCE_LOG_FILE}[/red]")
    raise typer.Exit(1)


def _web_ready_timeout_seconds() -> float:
    raw = os.environ.get(WEB_READY_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_WEB_READY_TIMEOUT_SECONDS
    try:
        return max(float(raw), WEB_READY_POLL_INTERVAL_SECONDS)
    except ValueError:
        return DEFAULT_WEB_READY_TIMEOUT_SECONDS


def _is_port_available(host: str, port: int) -> bool:
    try:
        with socket.create_connection((_test_host(host), port), timeout=0.2):
            return False
    except (ConnectionRefusedError, TimeoutError, OSError):
        return True


def _test_host(host: str) -> str:
    return "127.0.0.1" if host == "0.0.0.0" else host


def _is_valid_governance_health(status_code: int, payload: object) -> bool:
    return (
        200 <= status_code < 300
        and isinstance(payload, dict)
        and payload.get("service") == PUBLIC_GOVERNANCE_EXECUTABLE
        and str(payload.get("status", "")).lower() in {"healthy", "ok"}
    )


def _probe_governance_health(host: str, port: int) -> bool:
    try:
        response = requests.get(
            f"http://{_test_host(host)}:{port}{GOVERNANCE_HEALTH_PATH}",
            timeout=0.5,
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        return False
    return _is_valid_governance_health(response.status_code, payload)


def _listener_pids(port: int) -> set[int]:
    pids: set[int] = set()
    if psutil is not None:
        try:
            for connection in psutil.net_connections(kind="inet"):
                if (
                    connection.status == "LISTEN"
                    and connection.laddr
                    and connection.laddr.port == port
                    and connection.pid
                ):
                    pids.add(int(connection.pid))
        except Exception:
            pass
    if pids:
        return pids
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return pids
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return pids


def _process_parent_pid(pid: int) -> int | None:
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            text = proc_stat.read_text(encoding="utf-8")
            fields_after_name = text[text.rfind(")") + 2 :].split()
            parent_pid = int(fields_after_name[1])
            return parent_pid if parent_pid > 0 else None
        except (OSError, IndexError, ValueError):
            return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "ppid="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        parent_pid = int(result.stdout.strip())
    except ValueError:
        return None
    return parent_pid if result.returncode == 0 and parent_pid > 0 else None


def _process_executable_path(pid: int) -> str | None:
    """Return the kernel-reported executable, never an argv-derived guess."""
    if psutil is not None:
        try:
            executable = psutil.Process(pid).exe()
            if executable and os.path.isabs(executable):
                return executable
        except Exception:
            pass
    proc_executable = Path(f"/proc/{pid}/exe")
    try:
        executable = os.readlink(proc_executable)
    except OSError:
        return None
    return executable if os.path.isabs(executable) else None


def _process_identity_observation(
    pid: int,
    launcher_kind: str,
    *,
    allow_missing_public_executable: bool,
    expected_supervisor_pid: int | None = None,
) -> ProcessIdentity | None:
    current_uid = _current_uid()
    start_token = _process_start_token(pid)
    process_command = _process_command(pid)
    executable = _process_executable_path(pid)
    parent_pid = _process_parent_pid(pid)
    if not (
        current_uid is not None
        and _process_uid(pid) == current_uid
        and start_token
        and process_command
        and _is_allowed_managed_command(
            process_command,
            launcher_kind,
            allow_missing_public_executable=allow_missing_public_executable,
        )
    ):
        return None
    if launcher_kind == "public-listener":
        if not _is_expected_nuitka_listener_executable(
            executable,
            pid=pid,
            parent_pid=parent_pid,
            expected_supervisor_pid=expected_supervisor_pid,
            allow_missing=allow_missing_public_executable,
        ):
            return None
    elif launcher_kind == "public":
        argv = _command_argv(process_command)
        if (
            executable is None
            or Path(executable).name != PUBLIC_GOVERNANCE_EXECUTABLE
            or not argv
            or os.path.realpath(executable) != os.path.realpath(argv[0])
        ):
            return None
    return ProcessIdentity(
        pid=pid,
        start_token=start_token,
        command_sha256=_command_sha256(process_command),
        launcher_kind=launcher_kind,
        executable=executable,
        parent_pid=(
            expected_supervisor_pid
            if launcher_kind == "public-listener"
            else parent_pid
        ),
    )


def _capture_process_identity(pid: int, launcher_kind: str) -> ProcessIdentity:
    for _ in range(20):
        identity = _process_identity_observation(
            pid,
            launcher_kind,
            allow_missing_public_executable=False,
        )
        if identity is not None:
            return identity
        time.sleep(0.05)
    raise RuntimeError(f"process {pid} did not expose an allowed command and start token")


def _owned_listener_identity(
    supervisor: ProcessIdentity,
    port: int,
    *,
    allow_missing_public_executable: bool = True,
) -> ProcessIdentity | None:
    """Return the one listener still owned by the revalidated supervisor."""
    if not _managed_identity_matches(supervisor):
        return None
    if supervisor.launcher_kind == "source":
        return supervisor if supervisor.pid in _listener_pids(port) else None
    if supervisor.launcher_kind != "public":
        return None
    supervisor_command = _process_command(supervisor.pid)
    supervisor_arguments = _managed_command_arguments(supervisor_command)
    if supervisor_arguments is None:
        return None
    candidates: list[ProcessIdentity] = []
    for pid in sorted(_listener_pids(port)):
        if pid == supervisor.pid or _process_parent_pid(pid) != supervisor.pid:
            continue
        identity = _process_identity_observation(
            pid,
            "public-listener",
            allow_missing_public_executable=allow_missing_public_executable,
            expected_supervisor_pid=supervisor.pid,
        )
        listener_arguments = _managed_command_arguments(_process_command(pid))
        if identity is None or listener_arguments != supervisor_arguments:
            continue
        if not _managed_identity_matches(identity):
            continue
        candidates.append(identity)
    if len(candidates) != 1 or not _managed_identity_matches(supervisor):
        return None
    return candidates[0]


def _legacy_orphan_listener_identity(
    supervisor: ProcessIdentity,
    host: str,
    port: int,
) -> ProcessIdentity | None:
    """Recover the exact v0.2.5 listener after its supervisor has exited."""
    if (
        supervisor.launcher_kind != "public"
        or _is_pid_running(supervisor.pid)
        or not _probe_governance_health(host, port)
    ):
        return None
    candidates: list[ProcessIdentity] = []
    for pid in sorted(_listener_pids(port)):
        if _process_parent_pid(pid) != 1:
            continue
        identity = _process_identity_observation(
            pid,
            "public-listener",
            allow_missing_public_executable=True,
            expected_supervisor_pid=supervisor.pid,
        )
        if (
            identity is None
            or not _managed_command_targets(_process_command(pid), host, port)
            or not _managed_identity_matches(identity)
        ):
            continue
        candidates.append(identity)
    if len(candidates) != 1 or not _probe_governance_health(host, port):
        return None
    return candidates[0]


def _record_with_recovered_legacy_listener(
    record: WebProcessRecord,
    host: str,
    port: int,
) -> WebProcessRecord:
    if record.schema != 1 or record.listener is not None:
        return record
    listener = _legacy_orphan_listener_identity(record.supervisor, host, port)
    if listener is None:
        return record
    return WebProcessRecord(
        schema=2,
        supervisor=record.supervisor,
        listener=listener,
    )


def _write_web_process_record(record: WebProcessRecord) -> None:
    if (
        record.schema != 2
        or record.listener is None
        or record.supervisor.executable is None
        or record.supervisor.parent_pid is None
        or record.listener.executable is None
        or record.listener.parent_pid is None
        or not _valid_runtime_identity_pair(record.supervisor, record.listener)
    ):
        raise ValueError("Only complete supervisor/listener runtime records can be persisted")
    GOVERNANCE_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = GOVERNANCE_PID_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(record), sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(GOVERNANCE_PID_FILE)


def _read_web_process_record() -> WebProcessRecord | None:
    if not _owned_regular_web_process_record():
        return None
    try:
        payload = json.loads(GOVERNANCE_PID_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        schema = int(payload["schema"])
    except (KeyError, TypeError, ValueError):
        return None
    if schema == 1:
        supervisor = _identity_from_payload(payload)
        return (
            WebProcessRecord(schema=1, supervisor=supervisor, listener=None)
            if supervisor is not None
            else None
        )
    if schema != 2:
        return None
    supervisor = _identity_from_payload(payload.get("supervisor"), require_extended=True)
    listener = _identity_from_payload(payload.get("listener"), require_extended=True)
    if supervisor is None or listener is None:
        return None
    if not _valid_runtime_identity_pair(supervisor, listener):
        return None
    return WebProcessRecord(schema=2, supervisor=supervisor, listener=listener)


def _identity_from_payload(
    payload: object,
    *,
    require_extended: bool = False,
) -> ProcessIdentity | None:
    if not isinstance(payload, dict):
        return None
    try:
        executable_value = payload.get("executable")
        parent_pid_value = payload.get("parent_pid")
        identity = ProcessIdentity(
            pid=int(payload["pid"]),
            start_token=str(payload["start_token"]),
            command_sha256=str(payload["command_sha256"]),
            launcher_kind=str(payload["launcher_kind"]),
            executable=(
                str(executable_value) if executable_value is not None else None
            ),
            parent_pid=(
                int(parent_pid_value) if parent_pid_value is not None else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if (
        identity.pid <= 0
        or not identity.start_token
        or len(identity.command_sha256) != 64
        or identity.launcher_kind not in {"public", "public-listener", "source"}
        or (
            identity.executable is not None
            and not os.path.isabs(identity.executable)
        )
        or (identity.parent_pid is not None and identity.parent_pid < 0)
        or (
            require_extended
            and (identity.executable is None or identity.parent_pid is None)
        )
    ):
        return None
    return identity


def _valid_runtime_identity_pair(
    supervisor: ProcessIdentity,
    listener: ProcessIdentity,
) -> bool:
    if supervisor.launcher_kind == "source":
        return listener.launcher_kind == "source" and listener.pid == supervisor.pid
    return (
        supervisor.launcher_kind == "public"
        and listener.launcher_kind == "public-listener"
        and listener.pid != supervisor.pid
        and listener.parent_pid == supervisor.pid
    )


def _unlink_web_process_record(record: WebProcessRecord) -> None:
    current = _read_web_process_record()
    if current == record:
        GOVERNANCE_PID_FILE.unlink(missing_ok=True)


def _matching_managed_process_observation(
    identity: ProcessIdentity,
) -> tuple[str, str, str | None, int | None] | None:
    if not _is_pid_running(identity.pid):
        return None
    current_uid = _current_uid()
    if current_uid is None or _process_uid(identity.pid) != current_uid:
        return None
    start_token = _process_start_token(identity.pid)
    command = _process_command(identity.pid)
    executable = _process_executable_path(identity.pid)
    parent_pid = _process_parent_pid(identity.pid)
    if not (
        start_token == identity.start_token
        and command
        and _command_sha256(command) == identity.command_sha256
        and _is_allowed_managed_command(
            command,
            identity.launcher_kind,
            allow_missing_public_executable=True,
        )
    ):
        return None
    if identity.executable is not None:
        if executable is None or executable != identity.executable:
            return None
    if identity.parent_pid is not None:
        expected_parents = {identity.parent_pid}
        if identity.launcher_kind == "public-listener":
            expected_parents.add(1)
        if parent_pid not in expected_parents:
            return None
    if (
        identity.launcher_kind == "public-listener"
        and identity.executable is not None
        and not _is_expected_nuitka_listener_executable(
            executable,
            pid=identity.pid,
            parent_pid=parent_pid,
            expected_supervisor_pid=identity.parent_pid,
            allow_missing=True,
        )
    ):
        return None
    return start_token, command, executable, parent_pid


def _managed_identity_matches(identity: ProcessIdentity) -> bool:
    """Revalidate one recorded identity twice before treating its PID as signalable."""
    first = _matching_managed_process_observation(identity)
    if first is None:
        return False
    return _matching_managed_process_observation(identity) == first


def _managed_process_matches(record: WebProcessRecord) -> bool:
    supervisor_matches = _managed_identity_matches(record.supervisor)
    if record.listener is None:
        return supervisor_matches
    listener_matches = _managed_identity_matches(record.listener)
    return listener_matches and (
        supervisor_matches or not _is_pid_running(record.supervisor.pid)
    )


def _record_has_live_process(record: WebProcessRecord) -> bool:
    return _is_pid_running(record.supervisor.pid) or bool(
        record.listener is not None and _is_pid_running(record.listener.pid)
    )


def _process_start_token(pid: int) -> str | None:
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            text = proc_stat.read_text(encoding="utf-8")
            fields_after_name = text[text.rfind(")") + 2 :].split()
            return f"linux:{fields_after_name[19]}"
        except (OSError, IndexError):
            return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return f"ps:{value}" if result.returncode == 0 and value else None


def _current_uid() -> int | None:
    return os.getuid() if hasattr(os, "getuid") else None


def _process_uid(pid: int) -> int | None:
    proc_status = Path(f"/proc/{pid}/status")
    if proc_status.is_file():
        try:
            for line in proc_status.read_text(encoding="utf-8").splitlines():
                if line.startswith("Uid:"):
                    values = line.split()[1:]
                    # Match `ps -o uid=` by checking the effective UID.
                    return int(values[1]) if len(values) >= 2 else None
        except (OSError, ValueError):
            return None
        return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "uid="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    try:
        return int(value) if result.returncode == 0 and value else None
    except ValueError:
        return None


def _process_command(pid: int) -> str | None:
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if proc_cmdline.is_file():
        try:
            raw = proc_cmdline.read_bytes().rstrip(b"\0")
        except OSError:
            return None
        return raw.decode("utf-8", errors="surrogateescape") if raw else None
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _command_argv(command: str) -> list[str]:
    if "\0" in command:
        return [part for part in command.split("\0") if part]
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _command_sha256(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8", errors="surrogateescape")).hexdigest()


def _is_source_daemon_command(command: list[str]) -> bool:
    return (
        len(command) >= 4
        and _is_python_executable(command[0])
        and command[1:4] == ["-m", "uvicorn", "cloud_governance.web:app"]
    )


def _managed_command_arguments(command: str | None) -> tuple[str, ...] | None:
    if not command:
        return None
    argv = _command_argv(command)
    if len(argv) < 3 or argv[1:3] != ["web", "serve"]:
        return None
    return tuple(argv[1:])


def _managed_command_targets(command: str | None, host: str, port: int) -> bool:
    arguments = _managed_command_arguments(command)
    if arguments is None or len(arguments) != 6:
        return False
    return (
        arguments[:3] == ("web", "serve", "--host")
        and arguments[3] == host
        and arguments[4:] == ("--port", str(port))
    )


def _is_expected_nuitka_listener_executable(
    executable: str | None,
    *,
    pid: int,
    parent_pid: int | None,
    expected_supervisor_pid: int | None,
    allow_missing: bool,
) -> bool:
    """Recognize only the legacy or product-specific unique Nuitka payload."""
    if (
        not executable
        or not os.path.isabs(executable)
        or Path(executable).name != f"{PUBLIC_GOVERNANCE_EXECUTABLE}.bin"
        or os.path.islink(executable)
        or expected_supervisor_pid is None
        or expected_supervisor_pid <= 0
        or pid <= 0
        or parent_pid not in {expected_supervisor_pid, 1}
        or (not allow_missing and not os.path.isfile(executable))
    ):
        return False

    resolved = os.path.realpath(executable)
    legacy = os.path.realpath(
        Path.home()
        / f".{PUBLIC_GOVERNANCE_EXECUTABLE}"
        / "bin"
        / f"{PUBLIC_GOVERNANCE_EXECUTABLE}.bin"
    )
    if resolved == legacy:
        return True

    temp_root = os.path.realpath(tempfile.gettempdir())
    runtime_dir = os.path.dirname(resolved)
    if os.path.dirname(runtime_dir) != temp_root:
        return False
    match = NUITKA_RUNTIME_DIRECTORY_PATTERN.fullmatch(os.path.basename(runtime_dir))
    if match is None:
        return False
    extraction_pid, seconds, microseconds = (int(value) for value in match.groups())
    return (
        extraction_pid == expected_supervisor_pid
        and seconds > 0
        and 0 <= microseconds < 1_000_000
    )


def _is_allowed_managed_command(
    command: str,
    launcher_kind: str,
    *,
    allow_missing_public_executable: bool = False,
) -> bool:
    argv = _command_argv(command)
    if not argv:
        return False
    if launcher_kind == "source":
        return _is_source_daemon_command(argv)
    if launcher_kind not in {"public", "public-listener"}:
        return False
    if len(argv) < 3 or argv[1:3] != ["web", "serve"]:
        return False
    executable = Path(argv[0]).expanduser()
    expected_names = {PUBLIC_GOVERNANCE_EXECUTABLE}
    if launcher_kind == "public-listener":
        expected_names.add(f"{PUBLIC_GOVERNANCE_EXECUTABLE}.bin")
    if not executable.is_absolute() or executable.name not in expected_names:
        return False
    if launcher_kind == "public-listener":
        # The kernel-reported executable and exact extraction layout are
        # validated separately; argv[0] differs across Nuitka versions.
        return True
    try:
        resolved = executable.resolve(strict=True)
    except FileNotFoundError:
        # Homebrew may remove the N-1 Cellar path while its already-recorded
        # process is still running. PID, start token, raw command hash, parsed
        # argv and public basename are all revalidated before this exception is
        # allowed. New record creation never enables this compatibility path.
        return allow_missing_public_executable
    except (OSError, RuntimeError):
        return False
    return (
        resolved.name == PUBLIC_GOVERNANCE_EXECUTABLE
        and resolved.is_file()
        and os.access(resolved, os.X_OK)
    )


def _owned_regular_web_process_record() -> bool:
    try:
        record_stat = GOVERNANCE_PID_FILE.lstat()
    except OSError:
        return False
    if not stat.S_ISREG(record_stat.st_mode):
        return False
    if record_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return False
    current_uid = _current_uid()
    return current_uid is not None and record_stat.st_uid == current_uid


def _untrusted_web_process_record_pid(raw: str) -> int | None:
    stripped = raw.strip()
    if stripped.isdecimal():
        pid = int(stripped)
        return pid if pid > 0 else None
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        raw_pid = payload.get("pid")
        if raw_pid is None and isinstance(payload.get("supervisor"), dict):
            raw_pid = payload["supervisor"].get("pid")
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _discard_untrusted_web_process_record_if_safe(host: str, port: int) -> bool:
    """Remove stale malformed state without ever signalling its untrusted PID."""
    if not _owned_regular_web_process_record():
        return False
    try:
        original = GOVERNANCE_PID_FILE.read_text(encoding="utf-8")
    except OSError:
        return False
    untrusted_pid = _untrusted_web_process_record_pid(original)
    if untrusted_pid is not None and _is_pid_running(untrusted_pid):
        return False
    if not _is_port_available(host, port):
        return False
    try:
        if GOVERNANCE_PID_FILE.read_text(encoding="utf-8") != original:
            return False
        GOVERNANCE_PID_FILE.unlink()
    except OSError:
        return False
    console.print("[yellow]Removed stale Governance Hub web process record.[/yellow]")
    return True


def _is_pid_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_identity(identity: ProcessIdentity) -> bool:
    if not _managed_identity_matches(identity):
        return False
    try:
        os.kill(identity.pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    for _ in range(50):
        if not _is_pid_running(identity.pid):
            return True
        time.sleep(0.1)
    if not _managed_identity_matches(identity):
        return False
    try:
        os.kill(identity.pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    for _ in range(20):
        if not _is_pid_running(identity.pid):
            return True
        time.sleep(0.05)
    return not _is_pid_running(identity.pid)


def _terminate_process(
    record: WebProcessRecord,
    *,
    host: str = "127.0.0.1",
    port: int = 8097,
) -> bool:
    """Terminate a verified listener before its verified onefile supervisor."""
    supervisor_matches = _managed_identity_matches(record.supervisor)
    listener = record.listener
    listener_matches = bool(
        listener
        and (
            supervisor_matches
            if listener == record.supervisor
            else _managed_identity_matches(listener)
        )
    )

    if listener is not None and not listener_matches:
        # Never signal a reused or changed listener PID. The supervisor may be
        # stopped only when that stale identity is gone and no listener remains.
        if _is_pid_running(listener.pid) or not _is_port_available(host, port):
            return False
        listener = None
    if listener is None and supervisor_matches and record.supervisor.launcher_kind == "public":
        listener = _owned_listener_identity(record.supervisor, port)
        if listener is not None and record.schema == 1 and not _probe_governance_health(
            host,
            port,
        ):
            return False
        if listener is None and not _is_port_available(host, port):
            return False
    if listener is None and supervisor_matches:
        listener = record.supervisor

    if listener is not None and listener.pid != record.supervisor.pid:
        if not _terminate_identity(listener):
            return False
    if _is_pid_running(record.supervisor.pid):
        if not supervisor_matches:
            return False
        return _terminate_identity(record.supervisor)
    return listener is not None and not _is_pid_running(listener.pid)


def _terminate_spawned_runtime(
    process: subprocess.Popen,
    supervisor: ProcessIdentity | None,
    listener: ProcessIdentity | None,
    *,
    port: int,
) -> bool:
    """Clean up the exact Popen tree, preferring verified listener-first shutdown."""
    if supervisor is not None:
        listener = listener or _owned_listener_identity(
            supervisor,
            port,
            allow_missing_public_executable=False,
        )
    if listener is not None and listener.pid != (supervisor.pid if supervisor else None):
        if not _terminate_identity(listener):
            return False
    # Reap an already-exited onefile supervisor before PID-based validation;
    # a zombie no longer exposes the original command line.
    if process.poll() is not None:
        return True
    if supervisor is not None and _is_pid_running(supervisor.pid):
        if not _managed_identity_matches(supervisor):
            return False
        if listener is not None:
            return _terminate_spawned_supervisor(process, supervisor)

    process.terminate()
    try:
        # Nuitka's default onefile handler needs five seconds to reap its child.
        process.wait(timeout=7)
        return True
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    return True


def _terminate_spawned_supervisor(
    process: subprocess.Popen,
    supervisor: ProcessIdentity,
) -> bool:
    """Terminate and reap the exact Popen supervisor after its listener is gone."""
    if process.poll() is not None:
        return True
    if not _managed_identity_matches(supervisor):
        return False
    process.terminate()
    try:
        process.wait(timeout=5)
        return True
    except subprocess.TimeoutExpired:
        if not _managed_identity_matches(supervisor):
            return False
        process.kill()
        process.wait(timeout=2)
        return True


def _print_untrusted_process_record_warning(pid: int | None = None) -> None:
    suffix = f" for PID {pid}" if pid else ""
    console.print(
        f"[yellow]Refusing to signal or replace the unverified Governance process record{suffix}.[/yellow]"
    )
    console.print(f"[dim]Record: {GOVERNANCE_PID_FILE}[/dim]")


app.add_typer(catalog_app, name="catalog")
app.add_typer(web_app, name="web", hidden=True)


if __name__ == "__main__":
    app()
