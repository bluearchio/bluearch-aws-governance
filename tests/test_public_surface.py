import re
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from cloud_governance import cli, web

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_catalog_help_exposes_import_and_not_nonexistent_load():
    result = runner.invoke(cli.app, ["catalog", "--help"])

    assert result.exit_code == 0
    assert "import" in result.stdout
    assert "verify" in result.stdout
    assert "load" not in result.stdout


def test_bundled_catalog_verification_is_read_only_and_parseable():
    result = runner.invoke(cli.app, ["catalog", "verify"])

    assert result.exit_code == 0
    assert "Bundled catalog files: 47" in result.stdout
    assert "Bundled catalog entries: 621" in result.stdout


def test_health_identifies_public_governance_service(monkeypatch):
    class FakeCoreClient:
        def __init__(self, *args, **kwargs):
            pass

        def health(self):
            return {"status": "ok", "db_ready": True}

        def catalog_summary(self):
            return {"total": 1}

    monkeypatch.setattr(web, "CoreClient", FakeCoreClient)

    with TestClient(web.create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["service"] == "bluearch-aws-governance"


def test_customer_docs_use_direct_formula_install_and_public_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    installer = (ROOT / "scripts/install-linux.sh").read_text(encoding="utf-8")

    assert "automatically adds the tap and trusts only" in readme
    assert "`brew tap bluearchio/tap` only downloads and registers" in readme
    assert "brew install bluearchio/tap/bluearch-aws-core" in readme
    assert readme.index("brew install bluearchio/tap/bluearch-aws-core") < readme.index(
        "brew install bluearchio/tap/bluearch-aws-governance"
    )
    recovery = readme.split("### Recovery for an existing tap", 1)[1]
    assert "brew trust --formula bluearchio/tap/bluearch-aws-core" in readme
    assert "brew trust --formula bluearchio/tap/bluearch-aws-governance" in readme
    assert "brew install bluearchio/tap/bluearch-aws-governance" in readme
    assert recovery.index("brew trust --formula bluearchio/tap/bluearch-aws-core") < recovery.index(
        "brew install bluearchio/tap/bluearch-aws-governance"
    )
    assert recovery.index("brew trust --formula bluearchio/tap/bluearch-aws-governance") < recovery.index(
        "brew install bluearchio/tap/bluearch-aws-governance"
    )
    assert "bluearch-aws-governance catalog import" in readme
    assert "bluearch-aws-governance catalog summary" in readme
    assert "brew trust bluearchio/tap" not in readme
    assert "HOMEBREW_NO_REQUIRE_TAP_TRUST" not in readme
    assert "catalog load" not in readme
    assert "cloud-governance " not in readme
    assert "bluearch-core " not in readme
    assert "cloud-governance " not in contributing
    assert "bluearch-core " not in contributing
    assert "brew trust --formula bluearchio/tap/bluearch-aws-core" in installer
    assert "brew trust --formula bluearchio/tap/bluearch-aws-governance" in installer
    assert "brew install bluearchio/tap/bluearch-aws-governance" in installer
    assert installer.index("brew trust --formula bluearchio/tap/bluearch-aws-core") < installer.index(
        "install bluearchio/tap/bluearch-aws-governance"
    )
    assert installer.index("brew trust --formula bluearchio/tap/bluearch-aws-governance") < installer.index(
        "install bluearchio/tap/bluearch-aws-governance"
    )


def test_setup_view_lists_only_registered_public_core_commands():
    setup_view = (ROOT / "frontend/src/views/SetupView.vue").read_text(encoding="utf-8")
    commands = set(re.findall(r"<code>(bluearch-[^<]+)</code>", setup_view))

    assert commands == {
        "bluearch-aws-core doctor",
        "bluearch-aws-core setup assume-role",
        "bluearch-aws-core setup cost-reports",
        "bluearch-aws-core setup event-tracking",
        "bluearch-aws-core setup multi-account",
        "bluearch-aws-core setup validate",
    }
