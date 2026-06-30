def _catalog_entry(catalog_id, payload, service="iam", executable=True):
    return {
        "catalog_id": catalog_id,
        "title": payload.get("scenario") or catalog_id,
        "service": service,
        "category": payload.get("risk_detail"),
        "severity": payload.get("risk_value"),
        "executable": executable,
        "payload": {"id": catalog_id, **payload},
    }


def _install_fake_core(monkeypatch, catalog_entries, storage_records=None):
    storage_records = storage_records or []
    saved_records = []

    class FakeCoreClient:
        def __init__(self, *args, **kwargs):
            pass

        def catalog(self, limit=1000, offset=0, **kwargs):
            return {
                "entries": catalog_entries[offset:offset + limit],
                "total": len(catalog_entries),
            }

        def list_storage(self, namespace, collection, limit=10000, offset=0):
            return storage_records[offset:offset + limit]

        def proxy(self, method, path, service_token=False, **kwargs):
            if method == "GET" and path == "/api/v1/resources/summary":
                return {
                    "total": 42,
                    "by_service": [
                        {"service_name": "ec2", "count": 20},
                        {"service_name": "s3", "count": 5},
                    ],
                    "by_region": [{"region": "us-east-1", "count": 25}],
                    "by_account": [{"account_id": "111111111111", "account_name": "dev", "count": 42}],
                }
            return {}

        def upsert_storage(self, namespace, collection, record_key, payload):
            saved_records.append(
                {
                    "namespace": namespace,
                    "collection": collection,
                    "record_key": record_key,
                    "payload": payload,
                }
            )
            return {"record_key": record_key, "payload": payload}

    monkeypatch.setattr("cloud_governance.frameworks_api.CoreClient", FakeCoreClient)
    return saved_records


def test_framework_coverage_maps_catalog_risk_detail_to_well_architected(monkeypatch):
    from cloud_governance.frameworks_api import framework_coverage

    _install_fake_core(
        monkeypatch,
        [
            _catalog_entry(
                "iam-root-mfa",
                {
                    "scenario": "Root user does not have MFA",
                    "risk_detail": "security",
                    "risk_value": 3,
                },
            )
        ],
    )

    response = framework_coverage()
    security = next(row for row in response["pillars"] if row["id"] == "security")
    well_architected = next(row for row in response["frameworks"] if row["id"] == "well_architected")

    assert response["status"] == "available"
    assert response["catalog_total"] == 1
    assert response["mapped_catalog_total"] == 1
    assert response["unmapped_catalog_total"] == 0
    assert security["catalog_count"] == 1
    assert security["executable_count"] == 1
    assert well_architected["catalog_count"] == 1
    assert well_architected["explicit_count"] == 0
    assert well_architected["inferred_count"] == 1
    assert response["scan_context"]["status"] == "available"
    assert response["scan_context"]["resource_total"] == 42
    assert response["scan_context"]["service_count"] == 2


def test_framework_coverage_counts_explicit_metadata_and_open_findings(monkeypatch):
    from cloud_governance.frameworks_api import framework_coverage

    _install_fake_core(
        monkeypatch,
        [
            _catalog_entry(
                "iam-root-mfa",
                {
                    "scenario": "Root user does not have MFA",
                    "risk_detail": "security",
                    "risk_value": 3,
                    "pillars": ["security"],
                    "external_refs": {
                        "well_architected": "SEC01-BP01",
                        "attack_technique": "T1078",
                        "d3fend": ["D3-MFA"],
                        "cis_aws": ["1.5"],
                    },
                },
            ),
            _catalog_entry(
                "s3-public-read",
                {
                    "scenario": "S3 bucket allows public read",
                    "risk_detail": "security",
                    "risk_value": 3,
                },
                service="s3",
            ),
        ],
        [
            {"payload": {"id": "finding-1", "misconfig_id": "iam-root-mfa", "status": "open"}},
            {"payload": {"id": "finding-2", "misconfig_id": "iam-root-mfa", "status": "resolved"}},
        ],
    )

    response = framework_coverage()
    security = next(row for row in response["pillars"] if row["id"] == "security")
    well_architected = next(row for row in response["frameworks"] if row["id"] == "well_architected")
    attack = next(row for row in response["frameworks"] if row["id"] == "attack")
    d3fend = next(row for row in response["frameworks"] if row["id"] == "d3fend")

    assert response["status"] == "available"
    assert response["catalog_total"] == 2
    assert response["mapped_catalog_total"] == 2
    assert response["unmapped_catalog_total"] == 0
    assert response["open_findings_total"] == 1
    assert security["catalog_count"] == 2
    assert security["executable_count"] == 2
    assert security["open_findings"] == 1
    assert well_architected["catalog_count"] == 2
    assert well_architected["explicit_count"] == 1
    assert well_architected["inferred_count"] == 1
    assert well_architected["open_findings"] == 1
    assert attack["catalog_count"] == 1
    assert attack["explicit_count"] == 1
    assert d3fend["catalog_count"] == 1


def test_framework_controls_filters_by_pillar_framework_and_search(monkeypatch):
    from cloud_governance.frameworks_api import framework_controls

    _install_fake_core(
        monkeypatch,
        [
            _catalog_entry(
                "iam-root-mfa",
                {
                    "scenario": "Root user does not have MFA",
                    "risk_detail": "security",
                    "risk_value": 3,
                    "pillars": ["security"],
                    "external_refs": {"attack_technique": "T1078"},
                },
            ),
            _catalog_entry(
                "rds-backup-disabled",
                {
                    "scenario": "RDS backups are disabled",
                    "risk_detail": "reliability",
                    "risk_value": 2,
                    "pillars": ["reliability"],
                    "external_refs": {"d3fend": "D3-Backup"},
                    "metadata": {"detector_status": "planned"},
                },
                service="rds",
                executable=False,
            ),
            _catalog_entry(
                "s3-public-read",
                {
                    "scenario": "S3 bucket allows public read",
                    "risk_detail": "security",
                    "risk_value": 3,
                },
                service="s3",
            ),
        ],
    )

    security = framework_controls(pillar="security", framework=None, search=None, limit=100)
    d3fend = framework_controls(pillar=None, framework="d3fend", search=None, limit=100)
    backup = framework_controls(pillar=None, framework=None, search="backup", limit=100)

    assert [item["catalog_id"] for item in security["items"]] == ["iam-root-mfa", "s3-public-read"]
    assert security["items"][0]["mapping_source"] == "explicit"
    assert security["items"][0]["mapping_sources"]["well_architected"] == "inferred"
    assert security["items"][0]["mapping_sources"]["attack_technique"] == "explicit"
    assert security["items"][1]["mapping_source"] == "inferred"
    assert [item["catalog_id"] for item in d3fend["items"]] == ["rds-backup-disabled"]
    assert d3fend["items"][0]["support_status"] == "planned"
    assert [item["catalog_id"] for item in backup["items"]] == ["rds-backup-disabled"]


def test_well_architected_policy_packs_and_activation(monkeypatch):
    from cloud_governance.frameworks_api import activate_well_architected_policy, well_architected_policies

    saved = _install_fake_core(
        monkeypatch,
        [
            _catalog_entry(
                "iam-root-mfa",
                {
                    "scenario": "Root user does not have MFA",
                    "risk_detail": "security",
                    "risk_value": 3,
                },
            ),
            _catalog_entry(
                "s3-public-read",
                {
                    "scenario": "S3 bucket allows public read",
                    "risk_detail": "security",
                    "risk_value": 3,
                },
                service="s3",
                executable=False,
            ),
            _catalog_entry(
                "efs-unused",
                {
                    "scenario": "Unused EFS file system",
                    "risk_detail": "cost, reliability",
                    "risk_value": 1,
                },
                service="efs",
            ),
        ],
    )

    policies = well_architected_policies()
    security = next(item for item in policies["items"] if item["pillar"] == "security")
    cost = next(item for item in policies["items"] if item["pillar"] == "cost_optimization")

    assert security["catalog_count"] == 2
    assert security["executable_count"] == 1
    assert security["unsupported_count"] == 1
    assert security["misconfig_ids"] == ["iam-root-mfa"]
    assert cost["catalog_count"] == 1
    assert cost["misconfig_ids"] == ["efs-unused"]

    activated = activate_well_architected_policy("well_architected_security")

    assert activated["enabled"] is True
    assert activated["misconfig_policy_id"]
    assert saved[0]["collection"] == "misconfig-policies"
    assert saved[0]["payload"]["framework"] == "well_architected"
    assert saved[0]["payload"]["framework_pillar"] == "security"
    assert saved[0]["payload"]["misconfig_ids"] == ["iam-root-mfa"]


def test_misconfig_findings_filters_by_misconfig_id(monkeypatch):
    from cloud_governance import misconfig_api

    monkeypatch.setattr(
        misconfig_api,
        "_list_findings",
        lambda: [
            {"id": "finding-1", "misconfig_id": "iam-root-mfa", "status": "open", "risk_value": 3},
            {"id": "finding-2", "misconfig_id": "s3-public-read", "status": "open", "risk_value": 3},
        ],
    )

    response = misconfig_api.list_findings(
        status="open",
        risk_type=None,
        service=None,
        tier=None,
        misconfig_id="iam-root-mfa",
        page=1,
        page_size=50,
    )

    assert response["total"] == 1
    assert response["items"][0]["id"] == "finding-1"


def test_misconfig_finding_groups_summarize_blast_radius(monkeypatch):
    from cloud_governance import misconfig_api

    monkeypatch.setattr(
        misconfig_api,
        "_list_findings",
        lambda: [
            {
                "id": "finding-1",
                "misconfig_id": "iam-root-mfa",
                "status": "open",
                "risk_value": 3,
                "risk_type": "security",
                "service_name": "iam",
                "scenario": "Root user does not have MFA",
                "recommendation": "Enable MFA on the root user.",
                "evaluation_tier": "confirmed",
                "resource_type": "aws_account",
                "resource_arn": "arn:aws:iam::111111111111:root",
                "detected_at": "2026-06-19T10:00:00Z",
            },
            {
                "id": "finding-2",
                "misconfig_id": "iam-root-mfa",
                "status": "open",
                "risk_value": 3,
                "risk_type": "security",
                "service_name": "iam",
                "scenario": "Root user does not have MFA",
                "evaluation_tier": "advisory",
                "resource_type": "aws_account",
                "resource_arn": "arn:aws:iam::222222222222:root",
                "detected_at": "2026-06-19T11:00:00Z",
            },
            {
                "id": "finding-3",
                "misconfig_id": "s3-public-read",
                "status": "resolved",
                "risk_value": 3,
                "risk_type": "security",
                "service_name": "s3",
            },
        ],
    )

    response = misconfig_api.finding_groups(
        status="open",
        risk_type=None,
        service=None,
        tier=None,
        misconfig_id=None,
        limit=25,
    )

    assert response["total"] == 1
    group = response["items"][0]
    assert group["misconfig_id"] == "iam-root-mfa"
    assert group["total_findings"] == 2
    assert group["confirmed_count"] == 1
    assert group["advisory_count"] == 1
    assert group["account_count"] == 2
    assert group["accounts"] == ["111111111111", "222222222222"]
    assert group["sample_finding_id"] == "finding-2"


def test_core_mutation_proxy_uses_service_token(monkeypatch):
    from fastapi.testclient import TestClient

    from cloud_governance.web import create_app

    calls = []

    class FakeCoreClient:
        def proxy(self, method, path, service_token=False, **kwargs):
            calls.append(
                {
                    "method": method,
                    "path": path,
                    "service_token": service_token,
                    "kwargs": kwargs,
                }
            )
            return {"ok": True}

    monkeypatch.setattr("cloud_governance.web.CoreClient", FakeCoreClient)

    client = TestClient(create_app())
    response = client.post("/api/v1/infrastructure/resource-group/create")

    assert response.status_code == 200
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/infrastructure/resource-group/create",
            "service_token": True,
            "kwargs": {},
        }
    ]
