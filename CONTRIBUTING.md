# Contributing

Thanks for helping improve `bluearch-aws-governance`.

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e . pytest httpx2 PyYAML

cd frontend
npm ci
```

## Run Locally

Start core first:

```bash
bluearch-aws-core start --daemon
```

Import the catalog and run the source dashboard:

```bash
bluearch-aws-governance catalog import
make backend-dev
```

Run the frontend:

```bash
cd frontend
npm run dev
```

## Test

```bash
cd catalog && python scripts/validate.py by-service
python -m pytest
python -m compileall cloud_governance
cd frontend && npm run build
```

Or use:

```bash
make setup
make test
```

## Catalog Contributions

- Keep source catalog entries in `catalog/by-service`.
- Keep package fallback data in `cloud_governance/catalog_seed/by-service` synchronized when needed.
- Keep unsupported entries non-executable until evaluators, IAM permissions, and tests exist.
- Include clear remediation text and references for new catalog entries.

## Pull Requests

- Keep changes small and focused.
- Include tests or explain why a test is not practical.
- Update the README when commands, configuration, APIs, frontend behavior, catalog shape, or AWS permissions change.
- Do not commit secrets, AWS account IDs, local databases, generated reports, screenshots with account data, or local `.env` files.
- Do not add hosted telemetry, hosted sign-in, private release URLs, license gates, internal AWS account IDs, Slack ops hooks, or private deployment automation.

## Security-Sensitive Changes

Changes to AWS credential handling, executable evaluators, service-token handling, local persistence, or generated reports need extra review. Describe the security impact in the PR.
