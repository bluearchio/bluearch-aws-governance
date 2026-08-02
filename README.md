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

Installing a fully qualified formula automatically adds the tap and trusts only
that formula. Install Core explicitly first so Homebrew records trust for the
separate dependency before resolving Governance. A separate `brew tap` or
`brew trust` command is not needed for a first-time install. See
[Homebrew's tap-trust documentation](https://docs.brew.sh/Tap-Trust).

```bash
brew install bluearchio/tap/bluearch-aws-core
brew install bluearchio/tap/bluearch-aws-governance
bluearch-aws-core start --daemon
bluearch-aws-governance catalog import
bluearch-aws-governance catalog summary
```

`brew tap bluearchio/tap` only downloads and registers the repository; it does
not grant trust. Whole-tap trust is unnecessary.

### Recovery for an existing tap

If an existing or partially completed installation refuses to load either
formula, trust only Core and Governance, then retry the product installation:

```bash
brew trust --formula bluearchio/tap/bluearch-aws-core
brew trust --formula bluearchio/tap/bluearch-aws-governance
brew install bluearchio/tap/bluearch-aws-governance
```

Linux:

```bash
curl -fsSL https://github.com/bluearchio/bluearch-aws-governance/releases/latest/download/install-linux.sh | bash
export PATH="$HOME/.local/bin:$PATH"
bluearch-aws-core start --daemon
bluearch-aws-governance catalog import
bluearch-aws-governance catalog summary
```

The Linux installer downloads verified assets directly from GitHub Releases and
installs `bluearch-aws-core` automatically if it is missing. Set
`BLUEARCH_VERSION=vX.Y.Z` (and optionally `BLUEARCH_CORE_VERSION=vX.Y.Z`) to pin
an immutable release. `BLUEARCH_DIST_BASE_URL` is available only as an explicit
mirror override; it is not used by default.

From source:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
bluearch-aws-core start --daemon
bluearch-aws-governance catalog import
bluearch-aws-governance catalog summary
```

## Local Development

Backend:

```bash
. .venv/bin/activate
make backend-dev
```

The backend target uses the internal source server path. Installed dashboards are started and supervised by `bluearch-aws-core start --daemon`.

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

## Verifying Release Assets

Tagged releases are published from GitHub Actions after Linux and signed/notarized macOS artifacts are built. Release assets include platform archives, CycloneDX SBOMs, `SHA256SUMS`, and GitHub artifact attestations.

```bash
sha256sum -c SHA256SUMS
# macOS: shasum -a 256 -c SHA256SUMS
gh attestation verify bluearch-aws-governance-linux-x86_64.tar.gz --repo bluearchio/bluearch-aws-governance
```

For macOS, verify `bluearch-aws-governance-macos-arm64.zip` with `gh attestation verify`.

Before publishing, the release workflow validates that the dedicated
cross-repository token has the required access to `bluearchio/homebrew-tap`.
Configure that fine-grained token with least privilege: repository access only
to the tap, with Contents and Pull requests write permissions. The tap repository
must have auto-merge enabled, and tap `main` must protect the formula-validation
checks as required status checks. After the
GitHub Release is published, it checks out the tap's `main` branch with
credentials disabled, creates or updates
`release/bluearch-aws-governance-<tag>`, and runs the tap's
`scripts/update_formula.py`. That script generates the immutable GitHub Release
URL from the exact signed macOS asset and its verified SHA-256.

The workflow opens a pull request against the tap's `main` branch and requests
native GitHub auto-merge with `--auto --squash --delete-branch`. GitHub merges
only after the protected required tap checks pass; the product workflow never
bypasses checks or pushes directly to tap `main`. The release workflow remains
pending until the formula pull request is actually `MERGED`; a closed pull
request or a two-hour timeout fails the workflow. If the formula is already
current, no pull request or auto-merge is requested.

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
