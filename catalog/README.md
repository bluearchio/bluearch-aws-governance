# Misconfiguration Catalog

This directory is the bundled catalog source for `bluearch-aws-governance`.

- `by-service/` contains the AWS misconfiguration records grouped by service.
- `schema/` contains the JSON schema used to validate catalog records.
- `scripts/validate.py` validates the catalog data.
- `scripts/generate.py` regenerates derived catalog artifacts when needed.

Governance Hub loads this directory first. The package seed under
`cloud_governance/catalog_seed/` is kept as a runtime fallback for packaged
installs.
