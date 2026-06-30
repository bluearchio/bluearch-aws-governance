# Well-Architected Detector Roadmap

Governance Hub now carries full AWS Well-Architected best-practice coverage in the imported misconfiguration catalog. The catalog includes all 308 official BP IDs:

- 10 BP IDs were already represented by 11 existing catalog rows and now have explicit `pillars` and `external_refs.well_architected` metadata.
- 298 BP IDs were added as catalog-only Well-Architected rows.
- 193 Well-Architected rows are detector roadmap candidates because they can plausibly be evaluated from AWS resource, account, configuration, utilization, or inventory metadata.
- 116 Well-Architected rows are manual-review-only because resource metadata cannot prove the organizational, process, design, or business-context requirement.

Non-executable rows must stay deactivated in Governance Hub. They are visible for framework coverage, but policy activation must continue to include only catalog IDs that have evaluator mappings.

## Metadata Contract

Every Well-Architected catalog row should expose:

- `pillars`: one or more Well-Architected pillar IDs.
- `external_refs.well_architected`: one or more AWS Well-Architected BP IDs.
- `metadata.detection_status`: `planned_resource_metadata` or `unsupported_manual`.
- `metadata.detector_status`: `planned` or `manual_review`.
- `metadata.support_reason`: why the row is or is not detector-ready.

## Detector Phases

### Phase 1: Control-plane configuration

Focus on checks that can be evaluated from account and resource configuration metadata already aligned with Governance Hub discovery:

- Identity, root account, MFA, IAM policy, access key, and permissions posture.
- Public exposure, network boundary, encryption at rest, encryption in transit, logging, CloudTrail, Config, GuardDuty, Security Hub, Inspector, and WAF posture.
- Tagging, ownership, backup configuration, lifecycle policies, and obvious abandoned-resource signals.

Primary BP groups: `SEC01`-`SEC09`, `REL09`, `COST03`, `COST04`, `SUS04`.

### Phase 2: Utilization and operational evidence

Add detectors that need CloudWatch metrics, service quotas, budget metadata, scaling policies, and retention windows:

- Service quota headroom and quota monitoring.
- Alarms, dashboards, log retention, event detection, and operational health signals.
- Auto Scaling, scheduled scaling, right sizing, storage performance, database performance, and demand management.
- Budget, forecast, and cost anomaly controls where APIs provide objective account evidence.

Primary BP groups: `OPS08`-`OPS10`, `REL01`, `REL05`-`REL07`, `PERF02`-`PERF05`, `COST02`, `COST06`, `COST07`, `COST09`, `SUS02`, `SUS05`.

### Phase 3: Topology and resilience inference

Implement higher-order checks that combine multiple resources into architecture-level signals:

- Multi-AZ and multi-region coverage.
- Fault isolation boundaries.
- VPC topology and data transfer paths.
- Recovery design signals, replication, and disaster-recovery readiness.
- Managed-service migration and shared-service consolidation candidates.

Primary BP groups: `REL02`, `REL03`, `REL10`, `REL11`, `REL13`, `COST05`, `SUS01`.

## Manual-only Scope

The following categories should remain deactivated unless Governance Hub gains a questionnaire, evidence upload, or external system integration:

- Customer needs, internal stakeholder priorities, governance ownership, culture, training, and organizational structure.
- Architecture review process, deployment process maturity, runbooks, game days, post-incident learning, and improvement loops.
- Threat modeling, secure development lifecycle, code review practices, application security process, and business-value quantification.
- Sustainability culture and team process items that require workload-owner attestation.

These rows are still valuable in the Frameworks page because they show coverage gaps without pretending that Governance Hub can detect them from AWS metadata.
