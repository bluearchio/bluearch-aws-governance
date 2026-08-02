import pytest

from cloud_governance import config
from cloud_governance.core_client import CoreClient, CoreRuntimeError


def test_minimum_core_version_is_public_core_release():
    assert config.DEFAULT_MINIMUM_CORE_VERSION == "0.2.6"


def test_incompatible_core_message_uses_only_public_core_command(monkeypatch):
    client = CoreClient()
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: {
            "compatible": False,
            "core_version": "0.2.5",
        },
    )

    with pytest.raises(CoreRuntimeError) as exc_info:
        client.dependency_status()

    message = str(exc_info.value)
    assert "bluearch-aws-core start --daemon" in message
    assert "`bluearch-core " not in message
