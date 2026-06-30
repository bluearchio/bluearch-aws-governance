# bluearch-aws-governance

`bluearch-aws-governance` is Governance Hub: a local API, CLI, dashboard, and bundled AWS misconfiguration catalog. It loads catalog data, evaluates supported findings, and presents governance/framework views for AWS accounts.

## What This Repo Is Not

This repo is not a separate hosted catalog service, account sign-in system, analytics pipeline, or commercial license service. It runs locally and depends on `bluearch-aws-core` for shared runtime behavior.

## How It Works With The Other Repos

- Requires `bluearch-aws-core` running locally first.
- Uses core for setup, account context, storage, inventory, scans, and service-token protected backend calls.
- Bundles the misconfiguration catalog under `catalog/by-service`.
- Complements `bluearch-aws-ops` and `bluearch-aws-tags` by turning shared AWS inventory into governance findings.

## Catalog

`catalog/by-service` is the source catalog shipped with Governance Hub. `cloud_governance/catalog_seed/by-service` is the runtime fallback for packaged installs.

Validate catalog data:

```bash
cd catalog
python scripts/validate.py by-service
```

## Install

```bash
brew tap bluearchio/tap
brew install bluearchio/tap/bluearch-aws-core
brew install bluearchio/tap/bluearch-aws-governance
bluearch-core start --daemon
cloud-governance catalog load
cloud-governance web start
```

From source:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
bluearch-core start --daemon
cloud-governance catalog load
```

## Local Development

Backend:

```bash
. .venv/bin/activate
cloud-governance web start --host 127.0.0.1 --port 8097
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Shortcut:

```bash
make setup
make backend-dev
make frontend-dev
```

## Tests

```bash
cd catalog && python scripts/validate.py by-service
python -m pytest
python -m compileall cloud_governance
cd frontend && npm run build
```

Shortcut:

```bash
make test
```

## Security And Privacy Defaults

- The dashboard binds to loopback by default.
- Calls to `bluearch-aws-core` use the local service token.
- AWS credentials stay in the user's local AWS config/credential chain.
- No BlueArch-hosted telemetry, hosted sign-in, license gates, or private release services are included.
- Inventory, findings, reports, logs, and screenshots may contain sensitive account data.
- Unsupported catalog entries stay non-executable until evaluators and IAM permissions are reviewed.
- Report suspected vulnerabilities privately; see `SECURITY.md`.

## Contributing

Keep the catalog in `catalog/by-service` and keep unsupported catalog rows non-executable until evaluators exist. Do not add hosted analytics, product sign-in, commercial gates, private AWS account IDs, private buckets, or internal release/signing automation.

See `CONTRIBUTING.md` for the full contribution workflow.
