"""HTTP client for bluearch-aws-core governance APIs."""

from __future__ import annotations

import re
from typing import Any

import requests

from .config import MINIMUM_CORE_VERSION, core_url, service_token_path


class CoreRuntimeError(RuntimeError):
    """Raised when the required local core runtime is unavailable."""


class CoreClient:
    def __init__(self, base_url: str | None = None, timeout: int = 15):
        self.base_url = (base_url or core_url()).rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/core/health", service_token=False)

    def dependency_status(
        self,
        app_name: str = "governance-hub",
        minimum_version: str = MINIMUM_CORE_VERSION,
    ) -> dict[str, Any]:
        try:
            status = self._request(
                "GET",
                "/api/v1/core/dependency/status",
                service_token=False,
                params={"app": app_name, "minimum_version": minimum_version},
            )
        except requests.HTTPError:
            health = self.health()
            version = health.get("version", "unknown")
            status = {
                "app": app_name,
                "core_installed": True,
                "core_running": True,
                "compatible": _is_development_version(version)
                or _version_tuple(version) >= _version_tuple(minimum_version),
                "core_version": version,
                "minimum_required_core_version": minimum_version,
                "message": "BlueArch Core is running.",
            }
        if not status.get("compatible"):
            raise CoreRuntimeError(_format_core_update_message(app_name, status, minimum_version))
        return status

    def import_catalog(
        self,
        source_path: str,
        executable_mapping: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/governance/catalog/import",
            json={
                "source_path": source_path,
                "executable_mapping": executable_mapping or {},
            },
        )

    def catalog(
        self,
        service: str | None = None,
        category: str | None = None,
        search: str | None = None,
        executable: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        params = {
            "service": service,
            "category": category,
            "search": search,
            "executable": executable,
            "limit": limit,
            "offset": offset,
        }
        return self._request("GET", "/api/v1/governance/catalog", params={k: v for k, v in params.items() if v is not None})

    def catalog_summary(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/governance/catalog/summary")

    def list_resources(self, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/resources",
            params={"limit": limit, "offset": offset},
        )

    def list_storage(
        self,
        namespace: str,
        collection: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/api/v1/storage/{namespace}/{collection}",
            params={"limit": limit, "offset": offset},
        )

    def upsert_storage(
        self,
        namespace: str,
        collection: str,
        record_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "PUT",
            f"/api/v1/storage/{namespace}/{collection}/{record_key}",
            json={"record_key": record_key, "payload": payload},
        )

    def delete_storage(self, namespace: str, collection: str, record_key: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/storage/{namespace}/{collection}/{record_key}")

    def proxy(self, method: str, path: str, service_token: bool = True, **kwargs) -> Any:
        """Proxy a product-backend request to bluearch-aws-core."""
        return self._request(method, path, service_token=service_token, **kwargs)

    def _request(self, method: str, path: str, service_token: bool = True, **kwargs):
        headers = kwargs.pop("headers", {})
        if service_token:
            headers["Authorization"] = f"Bearer {self._read_service_token()}"
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise CoreRuntimeError(f"bluearch-aws-core is not reachable at {self.base_url}: {exc}") from exc
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _read_service_token() -> str:
        path = service_token_path()
        if not path.exists():
            raise CoreRuntimeError(f"BlueArch Core service token not found at {path}")
        return path.read_text(encoding="utf-8").strip()


def _format_core_update_message(app_name: str, status: dict[str, Any], minimum_version: str) -> str:
    core_version = status.get("core_version") or "unknown"
    app_label = app_name.replace("-", " ")
    return (
        f"bluearch-aws-core {core_version} is too old for {app_label}. "
        f"Required version: >= {minimum_version}. "
        "Install or update BlueArch AWS Core with your installer, or with Homebrew: "
        "`brew install bluearchio/tap/bluearch-aws-core`; then restart it with "
        "`bluearch-aws-core start --daemon`."
    )


def _version_tuple(version: str) -> tuple[int, int, int]:
    cleaned = str(version).lstrip("v").split("-", 1)[0]
    values = []
    for part in cleaned.split(".")[:3]:
        try:
            values.append(int(part))
        except ValueError:
            values.append(0)
    while len(values) < 3:
        values.append(0)
    return tuple(values)


def _is_development_version(version: str) -> bool:
    value = str(version or "").strip()
    return value.upper() in {"LOCAL", "DEVELOPMENT"} or bool(re.fullmatch(r"[0-9a-f]{7,40}", value, re.IGNORECASE))
