import pytest

from cloud_governance import config
from cloud_governance.core_client import CoreClient, CoreRuntimeError


def test_minimum_core_version_is_public_core_release():
    assert config.DEFAULT_MINIMUM_CORE_VERSION == "0.2.9"


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
    trust = "brew trust --formula bluearchio/tap/bluearch-aws-core"
    install = "brew install bluearchio/tap/bluearch-aws-core"
    assert trust in message
    assert message.index(trust) < message.index(install)
    assert "bluearch-aws-core start --daemon" in message
    assert "`bluearch-core " not in message
