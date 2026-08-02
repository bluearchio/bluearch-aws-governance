"""Governance Hub local API shell."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .catalog_assets import package_data_dir, resolve_catalog_source_path
from .core_client import CoreClient
from .frameworks_api import router as frameworks_router
from .misconfig_api import router as misconfig_router
from .support import load_bluearch_executable_mapping
CATALOG_AUTO_IMPORT_DISABLED_VALUES = {"0", "false", "no", "off"}


class CatalogImportRequest(BaseModel):
    source_path: str
    bluearch_api_path: str | None = None


CORE_PUBLIC_GET_PREFIXES = (
    "/api/v1/accounts",
    "/api/v1/assume-role",
    "/api/v1/event-tracking",
    "/api/v1/infrastructure",
    "/api/v1/resources",
    "/api/v1/scans",
    "/api/v1/setup",
    "/api/v1/system/context",
    "/api/v1/system/contexts",
    "/api/v1/system/permissions",
    "/api/v1/system/templates",
)

CORE_SERVICE_TOKEN_MUTATION_PREFIXES = (
    "/api/v1/accounts",
    "/api/v1/assume-role",
    "/api/v1/event-tracking",
    "/api/v1/infrastructure",
    "/api/v1/scans",
    "/api/v1/system/context",
    "/api/v1/system/permissions",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="BlueArch Governance Hub",
        version=__version__,
        description="Governance Hub product API backed by bluearch-aws-core.",
    )
    app.include_router(frameworks_router)
    app.include_router(misconfig_router)

    @app.on_event("startup")
    async def bootstrap_catalog():
        _bootstrap_catalog_if_empty()

    @app.get("/api/v1/health")
    def health():
        core = CoreClient()
        try:
            core_health = core.health()
            return {"service": "bluearch-aws-governance", "status": "ok", "core": core_health}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"bluearch-aws-core unavailable: {exc}") from exc

    @app.get("/api/v1/system/health")
    def system_health():
        core = CoreClient()
        try:
            core_health = core.health()
            return {
                "status": "healthy" if core_health.get("status") == "ok" else "degraded",
                "version": __version__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "database": {"connected": bool(core_health.get("db_ready"))},
                "aws": {"connected": True},
                "core": core_health,
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "version": __version__,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "database": {"connected": False},
                "aws": {"connected": False, "error": str(exc)},
            }

    @app.get("/api/v1/system/stats")
    def system_stats():
        resources_count = 0
        accounts_count = 0
        try:
            resource_summary = _proxy_core("GET", "/api/v1/resources/summary")
            if isinstance(resource_summary, dict):
                resources_count = int(resource_summary.get("total") or 0)
        except Exception:
            pass
        try:
            accounts = _proxy_core("GET", "/api/v1/accounts")
            if isinstance(accounts, list):
                accounts_count = len(accounts)
            elif isinstance(accounts, dict):
                accounts_count = len(accounts.get("items") or accounts.get("accounts") or [])
        except Exception:
            pass
        try:
            catalog = CoreClient().catalog_summary()
            recommendations_count = int(catalog.get("total") or 0)
        except Exception:
            recommendations_count = 0
        return {
            "resources": resources_count,
            "recommendations": recommendations_count,
            "accounts": accounts_count,
        }

    @app.get("/api/v1/jobs")
    def list_jobs(request: Request):
        query = str(request.url.query)
        suffix = f"?{query}" if query else ""
        return _proxy_core("GET", f"/api/v1/jobs{suffix}")

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str):
        return _proxy_core("GET", f"/api/v1/jobs/{job_id}")

    @app.get("/api/v1/notifications")
    def notifications(request: Request):
        query = str(request.url.query)
        suffix = f"?{query}" if query else ""
        return _proxy_core("GET", f"/api/v1/notifications{suffix}")

    @app.post("/api/v1/governance/catalog/import")
    def import_catalog(request: CatalogImportRequest):
        try:
            mapping = load_bluearch_executable_mapping(request.bluearch_api_path)
            return CoreClient().import_catalog(request.source_path, executable_mapping=mapping)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/governance/catalog")
    def catalog(
        service: str | None = None,
        category: str | None = None,
        search: str | None = None,
        executable: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        return CoreClient().catalog(
            service=service,
            category=category,
            search=search,
            executable=executable,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/v1/governance/catalog/summary")
    def catalog_summary():
        return CoreClient().catalog_summary()

    @app.get("/api/v1/setup/validate")
    def setup_validate():
        return _proxy_core("GET", "/api/v1/setup/validate")

    @app.get("/api/v1/system/context")
    def current_context():
        try:
            return CoreClient().proxy("GET", "/api/v1/system/context")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return {
                    "account_id": "",
                    "account_alias": "",
                    "region": "",
                    "profile": "",
                    "is_current": False,
                }
            raise HTTPException(status_code=502, detail=f"bluearch-aws-core unavailable: {exc}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"bluearch-aws-core unavailable: {exc}") from exc

    @app.get("/api/v1/system/templates/{template_name:path}/raw")
    def template_raw(template_name: str):
        return _proxy_core("GET", f"/api/v1/system/templates/{template_name}/raw")

    @app.get("/api/v1/system/templates/{template_name:path}")
    def template_record(template_name: str):
        return _proxy_core("GET", f"/api/v1/system/templates/{template_name}")

    @app.post("/api/v1/infrastructure/stacks/{component}/update")
    def update_infrastructure_stack(component: str):
        return _proxy_core("POST", f"/api/v1/infrastructure/stacks/{component}/update", service_token=True)

    @app.post("/api/v1/infrastructure/stacks/cost-reports/deploy")
    def deploy_cur_stack(payload: dict[str, Any] = Body(default_factory=dict)):
        return _proxy_core("POST", "/api/v1/infrastructure/stacks/cost-reports/deploy", service_token=True, json=payload)

    @app.post("/api/v1/infrastructure/resource-group/create")
    def create_resource_group():
        return _proxy_core("POST", "/api/v1/infrastructure/resource-group/create", service_token=True)

    @app.post("/api/v1/infrastructure/resource-group/delete")
    def delete_resource_group():
        return _proxy_core("POST", "/api/v1/infrastructure/resource-group/delete", service_token=True)

    @app.post("/api/v1/infrastructure/cur-stack/delete")
    def delete_cur_stack():
        return _proxy_core("POST", "/api/v1/infrastructure/cur-stack/delete", service_token=True)

    @app.delete("/api/v1/system/context/{account_id}")
    def delete_context(account_id: str):
        return _proxy_core("DELETE", f"/api/v1/system/context/{account_id}", service_token=True)

    static_dir = _static_dir()
    if static_dir.exists() and (static_dir / "index.html").exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
    async def shared_runtime_proxy(
        path: str,
        request: Request,
        payload: dict[str, Any] | None = Body(default=None),
    ):
        core_path = f"/{path}"
        if request.method == "GET" and not core_path.startswith("/api/") and static_dir.exists():
            return _spa_response(static_dir, path)
        if request.method == "GET" and _is_core_proxy_path(core_path, CORE_PUBLIC_GET_PREFIXES):
            query = str(request.url.query)
            suffix = f"?{query}" if query else ""
            return _proxy_core("GET", f"{core_path}{suffix}")
        if request.method == "POST" and _is_core_proxy_path(core_path, CORE_SERVICE_TOKEN_MUTATION_PREFIXES):
            return _proxy_core("POST", core_path, service_token=True, json=payload or {})
        if request.method == "DELETE" and _is_core_proxy_path(core_path, CORE_SERVICE_TOKEN_MUTATION_PREFIXES):
            return _proxy_core("DELETE", core_path, service_token=True)
        raise HTTPException(status_code=404, detail="Not found")

    return app


def _proxy_core(method: str, path: str, service_token: bool = True, **kwargs):
    try:
        return CoreClient().proxy(method, path, service_token=service_token, **kwargs)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"bluearch-aws-core unavailable: {exc}") from exc


def _is_core_proxy_path(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _static_dir() -> Path:
    return package_data_dir() / "static"


def _bootstrap_catalog_if_empty() -> dict[str, Any]:
    if os.environ.get("GOVERNANCE_HUB_AUTO_IMPORT_CATALOG", "").lower() in CATALOG_AUTO_IMPORT_DISABLED_VALUES:
        return {"status": "disabled"}

    core = CoreClient(timeout=60)
    summary = core.catalog_summary()
    total = int(summary.get("total") or 0)
    if total > 0:
        return {"status": "already_loaded", "catalog_total": total}

    source_path = _catalog_source_path()
    if source_path is None:
        return {"status": "source_missing", "catalog_total": 0}

    bluearch_api_path = _bluearch_api_path()
    mapping = load_bluearch_executable_mapping(str(bluearch_api_path)) if bluearch_api_path else {}
    response = core.import_catalog(str(source_path), executable_mapping=mapping)
    entries_imported = int(response.get("entries_imported") or 0)
    return {
        "status": "imported",
        "catalog_total": entries_imported,
        "entries_imported": entries_imported,
        "files_seen": int(response.get("files_seen") or 0),
        "executable_mappings": int(response.get("executable_mappings") or 0),
    }


def _catalog_source_path() -> Path | None:
    return resolve_catalog_source_path(os.environ.get("GOVERNANCE_HUB_CATALOG_SOURCE"))


def _bluearch_api_path() -> Path | None:
    configured = os.environ.get("GOVERNANCE_HUB_BLUEARCH_API_PATH")
    candidates = [Path(configured).expanduser()] if configured else []
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


def _spa_response(static_dir: Path, path: str):
    candidate = static_dir / path
    try:
        resolved = candidate.resolve()
        root = static_dir.resolve()
        if path and str(resolved).startswith(str(root)) and resolved.exists() and resolved.is_file():
            return FileResponse(str(resolved))
    except OSError:
        pass
    return FileResponse(
        str(static_dir / "index.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


app = create_app()
