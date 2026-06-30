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
python catalog/scripts/validate.py catalog/by-service
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
npm install
npm run dev
```

## Tests

```bash
python -m pytest
python -m compileall cloud_governance
cd frontend && npm run build
```

## Contributing

Keep the catalog in `catalog/by-service` and keep unsupported catalog rows non-executable until evaluators exist. Do not add hosted analytics, product sign-in, commercial gates, private AWS account IDs, private buckets, or internal release/signing automation.
