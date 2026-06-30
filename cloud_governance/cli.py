"""Governance Hub CLI."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .catalog_assets import is_catalog_source, resolve_catalog_source_path
from .config import MINIMUM_CORE_VERSION
from .core_client import CoreClient
from .event_hooks import emit_event
from .support import load_bluearch_executable_mapping

app = typer.Typer(help="BlueArch Governance Hub")
catalog_app = typer.Typer(help="Misconfiguration catalog commands")
web_app = typer.Typer(help="Local API commands managed by bluearch-core")
console = Console()

GOVERNANCE_HOME = Path(os.environ.get("GOVERNANCE_HUB_HOME", "~/.cloud-governance")).expanduser()
GOVERNANCE_RUNTIME_DIR = GOVERNANCE_HOME / "runtime"
GOVERNANCE_LOG_DIR = GOVERNANCE_HOME / "logs"
GOVERNANCE_PID_FILE = GOVERNANCE_RUNTIME_DIR / "web-server.pid"
GOVERNANCE_LOG_FILE = GOVERNANCE_LOG_DIR / "web-server.log"
GOVERNANCE_HEALTH_PATH = "/api/v1/health"
DEFAULT_WEB_READY_TIMEOUT_SECONDS = 90.0
WEB_READY_POLL_INTERVAL_SECONDS = 0.1
WEB_READY_TIMEOUT_ENV = "CLOUD_GOVERNANCE_WEB_READY_TIMEOUT_SECONDS"


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
    """Check whether bluearch-core is available."""
    try:
        core = CoreClient(timeout=3)
        status = core.dependency_status()
        health = core.health()
    except Exception as exc:
        console.print("[red]bluearch-core is required before using Governance Hub.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        console.print(f"[cyan]Required version:[/cyan] bluearch-core >= {MINIMUM_CORE_VERSION}")
        console.print("[cyan]Start it with:[/cyan] bluearch-core start --daemon")
        console.print("[cyan]Install it with:[/cyan] brew install bluearchio/tap/bluearch-aws-core")
        raise typer.Exit(1) from exc
    console.print("[green]bluearch-core is available[/green]")
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
    """Show catalog totals from bluearch-core."""
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
    """List catalog entries from bluearch-core."""
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


@web_app.command("start")
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
        emit_event(
            "web.server.start",
            surface="daemon",
            command="web_start",
            status="success",
            properties={"host": host, "port": port, "daemon": True},
        )
        return

    emit_event(
        "web.server.start",
        surface="web",
        command="web_start",
        status="success",
        properties={"host": host, "port": port, "daemon": False},
    )
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
    pid = _read_web_pid()
    if pid is None or not _is_pid_running(pid):
        GOVERNANCE_PID_FILE.unlink(missing_ok=True)
        console.print("[yellow]Governance Hub web is not running.[/yellow]")
        return
    _terminate_process(pid)
    GOVERNANCE_PID_FILE.unlink(missing_ok=True)
    emit_event("web.server.stop", surface="daemon", command="web_stop", status="success")
    console.print("[green]Stopped Governance Hub web.[/green]")


@web_app.command("status")
def status_web(host: str = "127.0.0.1", port: int = 8097):
    """Show Governance Hub web daemon status."""
    pid = _read_web_pid()
    running = _is_pid_running(pid)
    emit_event(
        "web.server.status",
        surface="daemon",
        command="web_status",
        status="success" if running else "stopped",
        properties={"running": running},
    )
    console.print(f"Process: {'running' if running else 'stopped'}")
    if pid:
        console.print(f"PID: {pid}")
    try:
        response = requests.get(f"http://{host}:{port}{GOVERNANCE_HEALTH_PATH}", timeout=2)
        console.print(f"API: {response.status_code} {response.json().get('status')}")
    except Exception as exc:
        console.print(f"API: unavailable ({exc})")


def _ensure_core_managed_web_start() -> None:
    if os.environ.get("BLUEARCH_CORE_MANAGED_WEB_START") == "1":
        return
    console.print("[yellow]Governance Hub web startup is managed by bluearch-core.[/yellow]")
    console.print("[cyan]Run:[/cyan] bluearch-core start --daemon")
    raise typer.Exit(1)


def _ensure_core_dependency() -> None:
    try:
        CoreClient(timeout=3).dependency_status()
    except Exception as exc:
        console.print("[red]bluearch-core is required before using Governance Hub.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        console.print(f"[cyan]Required version:[/cyan] bluearch-core >= {MINIMUM_CORE_VERSION}")
        console.print("[cyan]Start it with:[/cyan] bluearch-core start --daemon")
        console.print("[cyan]Install it with:[/cyan] brew install bluearchio/tap/bluearch-aws-core")
        raise typer.Exit(1) from exc


def _start_web_daemon(host: str, port: int) -> None:
    GOVERNANCE_RUNTIME_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    GOVERNANCE_LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    _stop_known_web_process()
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
    GOVERNANCE_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    _wait_for_web_daemon(process, host, port)
    console.print(f"[green]Governance Hub web started on http://{host}:{port} (pid {process.pid}).[/green]")
    console.print(f"[dim]Log: {GOVERNANCE_LOG_FILE}[/dim]")


def _run_web_server(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run("cloud_governance.web:app", host=host, port=port, workers=1)


def _build_web_daemon_cmd(host: str, port: int) -> list[str]:
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
        console.print("[dim]Run `bluearch-core start --daemon` to start the managed dashboard.[/dim]")
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
    if argv0.startswith("cloud-governance"):
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
    candidates = [
        sys.argv[0],
        shutil.which("cloud-governance"),
        Path.home() / ".local" / "bin" / "cloud-governance",
        Path("/opt/homebrew/bin/cloud-governance"),
        Path("/usr/local/bin/cloud-governance"),
    ]
    if not _is_python_executable(sys.executable):
        candidates.append(sys.executable)

    for candidate in candidates:
        if not candidate:
            continue
        candidate_text = os.fspath(candidate)
        path = candidate_text
        if not os.path.isabs(path) and not os.path.dirname(path):
            resolved = shutil.which(path)
            path = resolved or path
        else:
            path = os.path.abspath(path)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return os.path.realpath(path)
    return None


def _stop_known_web_process() -> None:
    pid = _read_web_pid()
    if pid is None:
        return
    if _is_pid_running(pid):
        _terminate_process(pid)
        console.print(f"[yellow]Stopped existing Governance Hub web process: {pid}[/yellow]")
    GOVERNANCE_PID_FILE.unlink(missing_ok=True)


def _wait_for_web_daemon(process: subprocess.Popen, host: str, port: int) -> None:
    url = f"http://{_test_host(host)}:{port}{GOVERNANCE_HEALTH_PATH}"
    deadline = time.monotonic() + _web_ready_timeout_seconds()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            GOVERNANCE_PID_FILE.unlink(missing_ok=True)
            console.print(f"[red]Governance Hub web exited before it became ready. See log: {GOVERNANCE_LOG_FILE}[/red]")
            raise typer.Exit(1)
        try:
            response = requests.get(url, timeout=0.2)
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(WEB_READY_POLL_INTERVAL_SECONDS)
    _terminate_process(process.pid)
    GOVERNANCE_PID_FILE.unlink(missing_ok=True)
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


def _read_web_pid() -> int | None:
    if not GOVERNANCE_PID_FILE.exists():
        return None
    try:
        return int(GOVERNANCE_PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


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


def _terminate_process(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(50):
        if not _is_pid_running(pid):
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


app.add_typer(catalog_app, name="catalog")
app.add_typer(web_app, name="web")
