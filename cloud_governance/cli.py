"""Governance Hub CLI."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
import typer
from rich.console import Console
from rich.table import Table

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


@dataclass(frozen=True)
class WebProcessRecord:
    """Stable identity for a Governance web process started by this CLI."""

    schema: int
    pid: int
    start_token: str
    command_sha256: str
    launcher_kind: str


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
):
    if version:
        console.print(__version__)
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
        _print_untrusted_process_record_warning()
        return
    if not _is_pid_running(record.pid):
        _unlink_web_process_record(record)
        console.print("[yellow]Governance Hub web is not running.[/yellow]")
        return
    if not _terminate_process(record):
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
        console.print("[cyan]Install it with:[/cyan] brew install bluearchio/tap/bluearch-aws-core")
        raise typer.Exit(1) from exc


def _start_web_daemon(host: str, port: int) -> None:
    GOVERNANCE_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    GOVERNANCE_LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not _stop_known_web_process():
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
    try:
        record = _capture_web_process_record(process.pid, cmd)
    except RuntimeError as exc:
        process.terminate()
        process.wait(timeout=5)
        console.print(f"[red]Unable to establish a stable Governance process identity: {exc}[/red]")
        raise typer.Exit(1) from exc
    _write_web_process_record(record)
    _wait_for_web_daemon(process, record, host, port)
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


def _stop_known_web_process() -> bool:
    if not GOVERNANCE_PID_FILE.exists():
        return True
    record = _read_web_process_record()
    if record is None:
        _print_untrusted_process_record_warning()
        return False
    if not _is_pid_running(record.pid):
        _unlink_web_process_record(record)
        return True
    if not _terminate_process(record):
        _print_untrusted_process_record_warning(record.pid)
        return False
    _unlink_web_process_record(record)
    console.print(f"[yellow]Stopped existing Governance Hub web process: {record.pid}[/yellow]")
    return True


def _wait_for_web_daemon(
    process: subprocess.Popen,
    record: WebProcessRecord,
    host: str,
    port: int,
) -> None:
    url = f"http://{_test_host(host)}:{port}{GOVERNANCE_HEALTH_PATH}"
    deadline = time.monotonic() + _web_ready_timeout_seconds()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _unlink_web_process_record(record)
            console.print(f"[red]Governance Hub web exited before it became ready. See log: {GOVERNANCE_LOG_FILE}[/red]")
            raise typer.Exit(1)
        try:
            response = requests.get(url, timeout=0.2)
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(WEB_READY_POLL_INTERVAL_SECONDS)
    _terminate_process(record)
    _unlink_web_process_record(record)
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


def _capture_web_process_record(pid: int, command: list[str]) -> WebProcessRecord:
    launcher_kind = "source" if _is_source_daemon_command(command) else "public"
    for _ in range(20):
        start_token = _process_start_token(pid)
        process_command = _process_command(pid)
        if (
            start_token
            and process_command
            and _is_allowed_managed_command(process_command, launcher_kind)
        ):
            return WebProcessRecord(
                schema=1,
                pid=pid,
                start_token=start_token,
                command_sha256=_command_sha256(process_command),
                launcher_kind=launcher_kind,
            )
        time.sleep(0.05)
    raise RuntimeError(f"process {pid} did not expose an allowed command and start token")


def _write_web_process_record(record: WebProcessRecord) -> None:
    GOVERNANCE_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = GOVERNANCE_PID_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(record), sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(GOVERNANCE_PID_FILE)


def _read_web_process_record() -> WebProcessRecord | None:
    if not GOVERNANCE_PID_FILE.is_file():
        return None
    try:
        payload = json.loads(GOVERNANCE_PID_FILE.read_text(encoding="utf-8"))
        record = WebProcessRecord(
            schema=int(payload["schema"]),
            pid=int(payload["pid"]),
            start_token=str(payload["start_token"]),
            command_sha256=str(payload["command_sha256"]),
            launcher_kind=str(payload["launcher_kind"]),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    if (
        record.schema != 1
        or record.pid <= 0
        or not record.start_token
        or len(record.command_sha256) != 64
        or record.launcher_kind not in {"public", "source"}
    ):
        return None
    return record


def _unlink_web_process_record(record: WebProcessRecord) -> None:
    current = _read_web_process_record()
    if current == record:
        GOVERNANCE_PID_FILE.unlink(missing_ok=True)


def _managed_process_matches(record: WebProcessRecord) -> bool:
    if not _is_pid_running(record.pid):
        return False
    start_token = _process_start_token(record.pid)
    command = _process_command(record.pid)
    return bool(
        start_token == record.start_token
        and command
        and _command_sha256(command) == record.command_sha256
        and _is_allowed_managed_command(command, record.launcher_kind)
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


def _is_allowed_managed_command(command: str, launcher_kind: str) -> bool:
    argv = _command_argv(command)
    if not argv:
        return False
    if launcher_kind == "source":
        return _is_source_daemon_command(argv)
    if launcher_kind != "public":
        return False
    executable = Path(argv[0])
    if executable.name != PUBLIC_GOVERNANCE_EXECUTABLE:
        return False
    try:
        resolved = executable.expanduser().resolve(strict=True)
    except OSError:
        return False
    return resolved.name == PUBLIC_GOVERNANCE_EXECUTABLE


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


def _terminate_process(record: WebProcessRecord) -> bool:
    if not _managed_process_matches(record):
        return False
    try:
        os.kill(record.pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    for _ in range(50):
        if not _is_pid_running(record.pid):
            return True
        time.sleep(0.1)
    if not _managed_process_matches(record):
        return False
    try:
        os.kill(record.pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
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
