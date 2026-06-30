# Security Policy

## Supported Versions

Security fixes are provided for the latest released version. If you are running from source, test against the current `main` branch before reporting.

## Reporting A Vulnerability

Do not open a public issue for a suspected vulnerability. Report it privately through GitHub Security Advisories for this repository, or email the maintainers if advisories are not enabled yet.

Include:

- Affected version or commit.
- Reproduction steps.
- Expected and actual impact.
- Whether AWS credentials, local files, service tokens, catalog data, generated reports, or account metadata are exposed.

## Security Boundaries

- The dashboard must bind to loopback by default.
- Product backend calls to `bluearch-aws-core` must use the local service token.
- User AWS credentials stay on the user's machine and must not be sent to BlueArch-hosted services.
- Do not add hosted telemetry, hosted sign-in, license gates, private release services, internal AWS account IDs, Slack ops hooks, or private bucket URLs.
- Unsupported catalog entries must remain non-executable until evaluators and IAM requirements are reviewed.

## Maintainer Checklist

- Keep GitHub secret scanning and Dependabot enabled.
- Run the secret scan workflow before publishing releases.
- Validate catalog changes in CI.
- Treat inventory, findings, screenshots, and generated reports as potentially sensitive.
