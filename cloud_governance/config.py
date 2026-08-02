"""Configuration helpers for Governance Hub."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_CORE_URL = "http://127.0.0.1:8094"
DEFAULT_TOKEN_PATH = Path("~/.bluearch-core/runtime/api-token").expanduser()
DEFAULT_MINIMUM_CORE_VERSION = "0.2.6"
MINIMUM_CORE_VERSION = os.environ.get("GOVERNANCE_HUB_MINIMUM_CORE_VERSION", DEFAULT_MINIMUM_CORE_VERSION)


def core_url() -> str:
    return os.environ.get("BLUEARCH_CORE_URL", DEFAULT_CORE_URL).rstrip("/")


def service_token_path() -> Path:
    return Path(os.environ.get("BLUEARCH_CORE_TOKEN_PATH", str(DEFAULT_TOKEN_PATH))).expanduser()
