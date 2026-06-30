<template>
  <div class="frameworks-view">
    <div v-if="loading" class="section-card">
      <div class="section-empty">
        <i class="pi pi-spin pi-spinner"></i> Loading framework coverage...
      </div>
    </div>

    <div v-else-if="error" class="section-card">
      <div class="section-empty error-state">
        <i class="pi pi-exclamation-triangle"></i>
        {{ error }}
      </div>
    </div>

    <template v-else-if="coverage">
      <div class="summary-cards">
        <div class="summary-card">
          <div class="card-value">{{ formatNumber(coverage.catalog_total) }}</div>
          <div class="card-label">Catalog Checks</div>
        </div>
        <div class="summary-card mapped">
          <div class="card-value">{{ formatNumber(coverage.mapped_catalog_total) }}</div>
          <div class="card-label">Mapped</div>
        </div>
        <div class="summary-card unmapped">
          <div class="card-value">{{ formatNumber(coverage.unmapped_catalog_total) }}</div>
          <div class="card-label">Unmapped</div>
        </div>
        <div class="summary-card findings">
          <div class="card-value">{{ formatNumber(coverage.open_findings_total) }}</div>
          <div class="card-label">Open Findings</div>
        </div>
      </div>

      <section class="section-card scan-context-card">
        <div class="section-header">
          <div>
            <h2 class="section-title">Detection Scope</h2>
            <span class="section-count">
              {{ scanContext?.status === 'available' ? 'Latest inventory loaded from core' : 'Inventory summary unavailable' }}
            </span>
          </div>
        </div>
        <div class="scan-context-grid">
          <div class="scan-context-stat">
            <strong>{{ formatNumber(scanContext?.resource_total || 0) }}</strong>
            <span>Resources in scope</span>
          </div>
          <div class="scan-context-stat">
            <strong>{{ formatNumber(scanContext?.account_count || 0) }}</strong>
            <span>Accounts</span>
          </div>
          <div class="scan-context-stat">
            <strong>{{ formatNumber(scanContext?.region_count || 0) }}</strong>
            <span>Regions</span>
          </div>
          <div class="scan-context-stat">
            <strong>{{ formatNumber(scanContext?.service_count || 0) }}</strong>
            <span>Services</span>
          </div>
        </div>
        <div v-if="topScanSignals.length" class="scan-signal-row">
          <span v-for="signal in topScanSignals" :key="signal.key" class="scan-signal">
            {{ signal.label || signal.key }}: {{ formatNumber(signal.count) }}
          </span>
        </div>
      </section>

      <section class="section-card">
        <div class="section-header">
          <div>
            <h2 class="section-title">Well-Architected Policies</h2>
            <span class="section-count">{{ policyPacks.length }} pillar policy packs</span>
          </div>
        </div>

        <div v-if="actionMessage" class="action-message">
          <i class="pi pi-check-circle"></i>
          {{ actionMessage }}
        </div>

        <div v-if="policyLoading" class="section-empty">
          <i class="pi pi-spin pi-spinner"></i> Loading policies...
        </div>
        <div v-else class="policy-pack-grid">
          <article
            v-for="pack in policyPacks"
            :key="pack.id"
            class="policy-pack"
            :class="{ active: pack.enabled, empty: pack.executable_count === 0 }"
            role="button"
            tabindex="0"
            @click="openPolicyDetails(pack)"
            @keydown.enter.prevent="openPolicyDetails(pack)"
            @keydown.space.prevent="openPolicyDetails(pack)"
          >
            <div class="policy-pack-top">
              <div>
                <h3>{{ pack.name }}</h3>
                <p>{{ policySummary(pack) }}</p>
              </div>
              <span class="policy-state" :class="{ enabled: pack.enabled }">
                {{ pack.enabled ? 'Enabled' : 'Ready' }}
              </span>
            </div>
            <span class="policy-open-hint">
              Details <i class="pi pi-arrow-right"></i>
            </span>
          </article>
        </div>
      </section>

      <div v-if="hasFrameworkMappings && !hasExplicitFrameworkRefs" class="section-card readiness-card compact">
        <div class="readiness-icon">
          <i class="pi pi-info-circle"></i>
        </div>
        <div>
          <h2>Explicit framework references are still limited</h2>
          <p>
            The Well-Architected policy packs are using catalog pillar metadata and risk-detail
            mapping. Controls with AWS Well-Architected IDs, ATT&CK, D3FEND, CIS, Config, Prowler,
            Trusted Advisor, or CWE references are labeled as explicit when those fields exist.
          </p>
        </div>
      </div>

      <div
        v-if="selectedPolicyPack"
        class="detail-backdrop"
        role="presentation"
        @click="closePolicyDetails"
      >
        <section
          class="policy-detail"
          role="dialog"
          aria-modal="true"
          :aria-label="selectedPolicyPack.name"
          @click.stop
        >
          <header class="policy-detail-header">
            <div>
              <span class="detail-eyebrow">Well-Architected Pillar</span>
              <h2>{{ selectedPolicyPack.name }}</h2>
              <p>{{ selectedPolicyPack.description }}</p>
            </div>
            <button class="icon-button" type="button" title="Close" @click="closePolicyDetails">
              <i class="pi pi-times"></i>
            </button>
          </header>

          <div class="detail-summary">
            <span :class="{ enabled: selectedPolicyPack.enabled }">
              {{ selectedPolicyPack.enabled ? 'Policy enabled' : 'Policy ready' }}
            </span>
            <span>{{ policySummary(selectedPolicyPack) }}</span>
          </div>

          <div class="detail-metrics">
            <div>
              <strong>{{ selectedPolicyPack.catalog_count }}</strong>
              <span>Catalog controls</span>
            </div>
            <div>
              <strong>{{ selectedPolicyPack.executable_count }}</strong>
              <span>Executable detectors</span>
            </div>
            <div>
              <strong>{{ selectedPolicyPack.planned_count || 0 }}</strong>
              <span>Detector candidates</span>
            </div>
            <div>
              <strong>{{ selectedPolicyPack.unsupported_count || 0 }}</strong>
              <span>Manual review only</span>
            </div>
            <div>
              <strong>{{ selectedPolicyPack.open_findings }}</strong>
              <span>Open findings</span>
            </div>
            <div>
              <strong>{{ selectedPolicyPack.resources_flagged || 0 }}</strong>
              <span>Flagged resources</span>
            </div>
          </div>

          <div class="detail-copy">
            <div>
              <h3>Executable detectors</h3>
              <p>
                These checks already have Governance Hub evaluators and can be included in scans
                and misconfiguration policies.
              </p>
            </div>
            <div>
              <h3>Detector candidates</h3>
              <p>
                These Well-Architected controls are not active yet, but should be detectable later
                from AWS resource, account, configuration, or utilization metadata.
              </p>
            </div>
            <div>
              <h3>Manual review only</h3>
              <p>
                These controls stay deactivated because they require workload design, process, or
                business-context evidence that resource metadata cannot prove reliably.
              </p>
            </div>
          </div>

          <div v-if="selectedPillarDetails" class="detail-sections">
            <section>
              <h3>Best-practice areas</h3>
              <ul>
                <li v-for="item in selectedPillarDetails.areas" :key="item">{{ item }}</li>
              </ul>
            </section>
            <section>
              <h3>Detectable signals</h3>
              <ul>
                <li v-for="item in selectedPillarDetails.signals" :key="item">{{ item }}</li>
              </ul>
            </section>
            <section>
              <h3>Detector candidates</h3>
              <ul>
                <li v-for="item in selectedPillarDetails.candidates" :key="item">{{ item }}</li>
              </ul>
            </section>
            <section>
              <h3>Manual evidence</h3>
              <ul>
                <li v-for="item in selectedPillarDetails.manualEvidence" :key="item">{{ item }}</li>
              </ul>
            </section>
          </div>

          <div v-if="selectedPillarDetails" class="reference-panel">
            <div>
              <h3>Reference links</h3>
              <p>Use these when validating why a control is mapped to this pillar.</p>
            </div>
            <div class="reference-links">
              <a
                v-for="link in selectedPillarDetails.links"
                :key="link.url"
                :href="link.url"
                target="_blank"
                rel="noreferrer"
              >
                <i class="pi pi-external-link"></i>
                {{ link.label }}
              </a>
            </div>
          </div>

          <section class="detail-controls-panel">
            <div class="detail-panel-header">
              <div>
                <h3>Mapped catalog controls</h3>
                <p>
                  Preview of the catalog controls mapped to this pillar, with support status and
                  finding drilldowns where available.
                </p>
              </div>
              <button class="btn btn-outline btn-sm" type="button" @click="viewPolicyControls(selectedPolicyPack)">
                <i class="pi pi-list"></i>
                View all {{ selectedDetailControlsTotal }}
              </button>
            </div>

            <div v-if="detailControlsLoading" class="detail-inline-state">
              <i class="pi pi-spin pi-spinner"></i> Loading mapped controls...
            </div>
            <div v-else-if="detailControlsError" class="detail-inline-state error-state">
              <i class="pi pi-exclamation-triangle"></i>
              {{ detailControlsError }}
            </div>
            <div v-else-if="!selectedDetailControls.length" class="detail-inline-state">
              No mapped controls are available for this pillar yet.
            </div>
            <div v-else class="detail-control-list">
              <article v-for="control in selectedDetailControls" :key="control.catalog_id" class="detail-control">
                <div class="detail-control-main">
                  <strong>{{ control.title }}</strong>
                  <code>{{ control.catalog_id }}</code>
                  <span v-if="control.risk_detail">{{ control.risk_detail }}</span>
                </div>
                <div class="detail-control-meta">
                  <span class="service-badge">{{ control.service || '--' }}</span>
                  <span
                    class="support-badge"
                    :class="supportStatus(control)"
                    :title="control.support_reason || supportLabel(control)"
                  >
                    <i :class="supportIcon(control)"></i>
                    {{ supportLabel(control) }}
                  </span>
                  <span class="finding-count" :class="{ active: control.open_findings > 0 }">
                    {{ control.open_findings }} open
                  </span>
                  <span
                    class="mapping-badge"
                    :class="mappingClass(control)"
                    :title="mappingTitle(control)"
                  >
                    {{ mappingLabel(control) }}
                  </span>
                </div>
                <div class="detail-control-refs">
                  <span
                    v-if="!visibleRefs(control).length"
                    class="ref-chip muted"
                  >
                    No external ref
                  </span>
                  <span
                    v-for="ref in visibleRefs(control).slice(0, 4)"
                    :key="`${control.catalog_id}-detail-${ref.key}`"
                    class="ref-chip"
                    :title="ref.values.join(', ')"
                  >
                    {{ refLabel(ref.key) }}: {{ ref.values.slice(0, 2).join(', ') }}
                    <span v-if="ref.values.length > 2">+{{ ref.values.length - 2 }}</span>
                  </span>
                </div>
                <router-link
                  v-if="control.executable || control.open_findings > 0"
                  :to="misconfigRoute(control)"
                  class="btn btn-outline btn-sm"
                >
                  <i class="pi pi-arrow-right"></i>
                  Misconfig
                </router-link>
                <span v-else class="deactivated-label" :title="control.support_reason || ''">
                  <i class="pi pi-lock"></i>
                  Deactivated
                </span>
              </article>
            </div>
          </section>

          <footer class="policy-detail-actions">
            <button
              class="btn btn-primary btn-sm"
              :disabled="selectedPolicyPack.executable_count === 0 || activatingIds.has(selectedPolicyPack.id)"
              @click="activatePolicy(selectedPolicyPack)"
            >
              <i :class="activatingIds.has(selectedPolicyPack.id) ? 'pi pi-spin pi-spinner' : 'pi pi-check'"></i>
              {{ selectedPolicyPack.enabled ? 'Update Policy' : 'Activate' }}
            </button>
            <button
              class="btn btn-outline btn-sm"
              :disabled="!selectedPolicyPack.misconfig_policy_id || scanningIds.has(selectedPolicyPack.id)"
              @click="scanPolicy(selectedPolicyPack)"
            >
              <i :class="scanningIds.has(selectedPolicyPack.id) ? 'pi pi-spin pi-spinner' : 'pi pi-sync'"></i>
              Scan
            </button>
            <button class="btn btn-outline btn-sm" @click="viewPolicyControls(selectedPolicyPack)">
              <i class="pi pi-filter"></i>
              Controls
            </button>
            <router-link
              v-if="selectedPolicyPack.misconfig_policy_id"
              :to="{ path: '/misconfig', query: { status: 'open' } }"
              class="btn btn-outline btn-sm"
            >
              <i class="pi pi-arrow-right"></i>
              Findings
            </router-link>
          </footer>
        </section>
      </div>

      <div v-if="!hasFrameworkMappings" class="section-card readiness-card">
        <div class="readiness-icon">
          <i class="pi pi-sitemap"></i>
        </div>
        <div>
          <h2>External framework references are not imported yet</h2>
          <p>
            Well-Architected policy packs are available from the Governance Hub catalog. MITRE,
            D3FEND, CIS, Config, Prowler, Trusted Advisor, and CWE references will appear here
            when catalog entries include explicit <code>external_refs</code> metadata.
          </p>
          <div class="readiness-metrics">
            <span>{{ coverage.catalog_total }} catalog checks loaded</span>
            <span>{{ coverage.unmapped_catalog_total }} checks without external references</span>
          </div>
        </div>
      </div>

      <template v-else>
        <section class="section-card">
          <div class="section-header">
            <h2 class="section-title">Well-Architected Pillars</h2>
            <button
              v-if="selectedPillar"
              class="btn btn-outline btn-sm"
              @click="selectedPillar = ''"
            >
              <i class="pi pi-filter-slash"></i>
              Clear
            </button>
          </div>
          <div class="pillar-grid">
            <button
              v-for="pillar in coverage.pillars"
              :key="pillar.id"
              class="pillar-card"
              :class="{ active: selectedPillar === pillar.id, empty: pillar.catalog_count === 0 }"
              @click="selectedPillar = selectedPillar === pillar.id ? '' : pillar.id"
            >
              <span class="pillar-name">{{ pillar.label }}</span>
              <span class="pillar-count">{{ pillar.catalog_count }}</span>
              <span class="pillar-meta">
                {{ pillar.executable_count }} executable
                <span v-if="pillar.open_findings"> - {{ pillar.open_findings }} open</span>
              </span>
            </button>
          </div>
        </section>

        <section class="section-card">
          <div class="section-header">
            <h2 class="section-title">Framework Coverage</h2>
            <button
              v-if="selectedFramework"
              class="btn btn-outline btn-sm"
              @click="selectedFramework = ''"
            >
              <i class="pi pi-filter-slash"></i>
              Clear
            </button>
          </div>
          <div class="framework-grid">
            <button
              v-for="framework in coverage.frameworks"
              :key="framework.id"
              class="framework-card"
              :class="{ active: selectedFramework === framework.id, empty: framework.catalog_count === 0 }"
              @click="selectedFramework = selectedFramework === framework.id ? '' : framework.id"
            >
              <span class="framework-name">{{ framework.label }}</span>
              <span class="framework-count">{{ formatNumber(framework.catalog_count) }}</span>
              <span class="framework-key">{{ frameworkEvidenceText(framework) }}</span>
              <span v-if="framework.open_findings" class="framework-open">
                {{ formatNumber(framework.open_findings) }} open
              </span>
            </button>
          </div>
        </section>

        <section class="section-card">
          <div class="section-header controls-header">
            <div>
              <h2 class="section-title">Mapped Controls</h2>
              <span class="section-count">{{ controlsTotal }} matching controls</span>
            </div>
            <div class="controls-actions">
              <label class="search-box">
                <i class="pi pi-search"></i>
                <input
                  v-model="search"
                  type="search"
                  placeholder="Search controls"
                  @keyup.enter="loadControls"
                />
              </label>
              <button class="btn btn-outline btn-sm" @click="loadControls">
                <i class="pi pi-search"></i>
                Search
              </button>
            </div>
          </div>

          <div v-if="controlsLoading" class="section-empty">
            <i class="pi pi-spin pi-spinner"></i> Loading controls...
          </div>
          <div v-else-if="!controls.length" class="section-empty">
            No mapped controls match the current filters.
          </div>
          <div v-else class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Service</th>
                  <th>Pillars</th>
                  <th>Framework Refs</th>
                  <th>Mapping</th>
                  <th>Support</th>
                  <th>Findings</th>
                  <th>Drilldown</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="control in controls"
                  :key="control.catalog_id"
                  :class="{ 'unsupported-row': !control.executable, 'planned-row': supportStatus(control) === 'planned' }"
                >
                  <td class="control-cell">
                    <strong>{{ control.title }}</strong>
                    <code>{{ control.catalog_id }}</code>
                    <span v-if="control.risk_detail" class="text-muted">{{ control.risk_detail }}</span>
                  </td>
                  <td>
                    <span class="service-badge">{{ control.service || '--' }}</span>
                  </td>
                  <td>
                    <div class="chip-list">
                      <span v-for="pillar in control.pillars" :key="pillar" class="type-chip">
                        {{ pillarLabel(pillar) }}
                      </span>
                    </div>
                  </td>
                  <td>
                    <div class="ref-list">
                      <span
                        v-if="!visibleRefs(control).length"
                        class="ref-chip muted"
                      >
                        No external ref
                      </span>
                      <span
                        v-for="ref in visibleRefs(control)"
                        :key="`${control.catalog_id}-${ref.key}`"
                        class="ref-chip"
                        :title="ref.values.join(', ')"
                      >
                        {{ refLabel(ref.key) }}: {{ ref.values.slice(0, 2).join(', ') }}
                        <span v-if="ref.values.length > 2">+{{ ref.values.length - 2 }}</span>
                      </span>
                    </div>
                  </td>
                  <td>
                    <span
                      class="mapping-badge"
                      :class="mappingClass(control)"
                      :title="mappingTitle(control)"
                    >
                      {{ mappingLabel(control) }}
                    </span>
                  </td>
                  <td>
                    <span
                      class="support-badge"
                      :class="supportStatus(control)"
                      :title="control.support_reason || supportLabel(control)"
                    >
                      <i :class="supportIcon(control)"></i>
                      {{ supportLabel(control) }}
                    </span>
                  </td>
                  <td>
                    <span class="finding-count" :class="{ active: control.open_findings > 0 }">
                      {{ control.open_findings }}
                    </span>
                  </td>
                  <td>
                    <router-link
                      v-if="control.executable || control.open_findings > 0"
                      :to="misconfigRoute(control)"
                      class="btn btn-outline btn-sm"
                    >
                      <i class="pi pi-arrow-right"></i>
                      Misconfig
                    </router-link>
                    <span v-else class="deactivated-label" :title="control.support_reason || ''">
                      <i class="pi pi-lock"></i>
                      Deactivated
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type {
  FrameworkControl,
  FrameworkCoverage,
  FrameworkMappingCount,
  FrameworkPolicyPack,
  FrameworkScanContextRow,
} from '@/types/api'

const coverage = ref<FrameworkCoverage | null>(null)
const controls = ref<FrameworkControl[]>([])
const policyPacks = ref<FrameworkPolicyPack[]>([])
const controlsTotal = ref(0)
const loading = ref(false)
const controlsLoading = ref(false)
const policyLoading = ref(false)
const error = ref<string | null>(null)
const selectedPillar = ref('')
const selectedFramework = ref('')
const selectedPolicyPackId = ref('')
const search = ref('')
const actionMessage = ref('')
const activatingIds = ref(new Set<string>())
const scanningIds = ref(new Set<string>())
const detailControlsByPillar = ref<Record<string, FrameworkControl[]>>({})
const detailControlTotalsByPillar = ref<Record<string, number>>({})
const detailControlsLoading = ref(false)
const detailControlsError = ref('')

const pillarLabels: Record<string, string> = {
  operational_excellence: 'Operational Excellence',
  security: 'Security',
  reliability: 'Reliability',
  performance_efficiency: 'Performance Efficiency',
  cost_optimization: 'Cost Optimization',
  sustainability: 'Sustainability',
}

const refLabels: Record<string, string> = {
  well_architected: 'WA',
  attack_technique: 'ATT&CK',
  d3fend: 'D3FEND',
  cis_aws: 'CIS',
  config_rule: 'Config',
  prowler_check: 'Prowler',
  trusted_advisor: 'TA',
  cwe: 'CWE',
}

const frameworkKeys: Record<string, string> = {
  well_architected: 'well_architected',
  attack: 'attack_technique',
  d3fend: 'd3fend',
  cis: 'cis_aws',
  config: 'config_rule',
  prowler: 'prowler_check',
  trusted_advisor: 'trusted_advisor',
  cwe: 'cwe',
}

const pillarDetails: Record<string, {
  areas: string[]
  signals: string[]
  candidates: string[]
  manualEvidence: string[]
  links: { label: string; url: string }[]
}> = {
  operational_excellence: {
    areas: ['Organization', 'Prepare', 'Operate', 'Evolve'],
    signals: [
      'CloudTrail, AWS Config, Security Hub, and account contact configuration',
      'CloudWatch alarms, log retention, dashboards, and notification targets',
      'Resource ownership tags and inventory coverage across regions',
      'Operational findings already generated by executable misconfig detectors',
    ],
    candidates: [
      'Detect missing observability foundations for critical services',
      'Check whether operational events create notifications or alarms',
      'Identify stale platforms, unpatched services, and unsupported runtime versions',
      'Correlate repeated findings with missing runbook or automation candidates',
    ],
    manualEvidence: [
      'Business priorities, operating model, and ownership decisions',
      'Runbook quality, game-day records, and incident-review outcomes',
      'Team training, escalation paths, and process maturity evidence',
    ],
    links: [
      {
        label: 'AWS Operational Excellence Pillar',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html',
      },
      {
        label: 'Well-Architected Framework',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html',
      },
    ],
  },
  security: {
    areas: ['Security foundations', 'Identity and access management', 'Detection', 'Infrastructure protection', 'Data protection', 'Incident response', 'Application security'],
    signals: [
      'IAM root account, MFA, access keys, password policy, and permissions posture',
      'Public exposure, security group ingress, WAF, Shield, and network controls',
      'CloudTrail, GuardDuty, Security Hub, Inspector, Config, and logging coverage',
      'Encryption settings for S3, EBS, RDS, Kinesis, EFS, CloudTrail, and TLS endpoints',
    ],
    candidates: [
      'Map identity and detective-control gaps to Security pillar best practices',
      'Detect missing data protection controls by resource metadata and KMS settings',
      'Expand incident-response readiness checks from enabled security services',
      'Add ATT&CK/D3FEND references where catalog controls map cleanly',
    ],
    manualEvidence: [
      'Threat modeling, secure development practices, and application security reviews',
      'Security ownership, response procedures, and forensic readiness attestations',
      'Business-approved control objectives and exception handling',
    ],
    links: [
      {
        label: 'AWS Security Pillar',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html',
      },
      {
        label: 'AWS Security Best Practices',
        url: 'https://aws.amazon.com/architecture/security-identity-compliance/',
      },
    ],
  },
  reliability: {
    areas: ['Foundations', 'Workload architecture', 'Change management', 'Failure management'],
    signals: [
      'Backup, versioning, replication, Multi-AZ, and disaster-recovery configuration',
      'Service quota utilization, Auto Scaling configuration, and capacity headroom',
      'Health checks, load balancers, Route 53 records, and failover posture',
      'Monitoring and alerting coverage for availability-impacting resources',
    ],
    candidates: [
      'Detect missing backup automation or backup encryption',
      'Evaluate quota headroom and quota monitoring across accounts and regions',
      'Identify single-location workloads and missing failover resources',
      'Check load balancer health, stale endpoints, and recovery automation signals',
    ],
    manualEvidence: [
      'Recovery objectives, DR test results, and business continuity approvals',
      'Architecture segmentation choices and service contract design',
      'Load-test evidence and resilience game-day outcomes',
    ],
    links: [
      {
        label: 'AWS Reliability Pillar',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html',
      },
      {
        label: 'AWS Backup Documentation',
        url: 'https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html',
      },
    ],
  },
  performance_efficiency: {
    areas: ['Selection', 'Review', 'Monitoring', 'Tradeoffs'],
    signals: [
      'Instance generation, storage type, throughput, utilization, and throttling metrics',
      'CloudWatch performance alarms and service-specific capacity settings',
      'Managed service configuration for databases, Lambda, DynamoDB, ECS, and routing',
      'High-utilization or under-provisioned resources already surfaced by detectors',
    ],
    candidates: [
      'Detect old-generation compute, storage, and database resources',
      'Flag throttling, saturation, and missing autoscaling policies',
      'Compare selected service families against resource metadata and utilization',
      'Identify resources that need performance alarms or review cadence',
    ],
    manualEvidence: [
      'Architecture tradeoff decisions and workload-specific performance targets',
      'Load-test plans, benchmark results, and user-experience KPIs',
      'Service selection rationale and periodic architecture review records',
    ],
    links: [
      {
        label: 'AWS Performance Efficiency Pillar',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html',
      },
      {
        label: 'Amazon CloudWatch Metrics',
        url: 'https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/working_with_metrics.html',
      },
    ],
  },
  cost_optimization: {
    areas: ['Practice Cloud Financial Management', 'Expenditure and usage awareness', 'Cost-effective resources', 'Manage demand and supply resources', 'Optimize over time'],
    signals: [
      'Idle, unattached, unused, or oversized resources across supported AWS services',
      'Tagging coverage, ownership metadata, budgets, forecasts, and cost controls',
      'Reserved Instance, Savings Plan, lifecycle policy, and storage tiering posture',
      'NAT, data transfer, duplicate infrastructure, and shared-service opportunities',
    ],
    candidates: [
      'Expand idle-resource and right-sizing detectors across more services',
      'Detect missing cost allocation tags and ownership fields',
      'Add cost-control checks for budgets, anomaly detection, and commitment coverage',
      'Correlate utilization metrics with lifecycle, scheduling, and storage-tier policies',
    ],
    manualEvidence: [
      'FinOps ownership, finance and engineering partnership, and cost culture',
      'Business-value quantification and application-level unit economics',
      'Architecture tradeoff approvals where cost is not the only optimization target',
    ],
    links: [
      {
        label: 'AWS Cost Optimization Pillar',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html',
      },
      {
        label: 'AWS Cost Management',
        url: 'https://docs.aws.amazon.com/cost-management/',
      },
    ],
  },
  sustainability: {
    areas: ['Region selection', 'Alignment to demand', 'Software and architecture', 'Data', 'Hardware and services', 'Process and culture'],
    signals: [
      'Unused, idle, redundant, or oversized resources that increase cloud waste',
      'Storage lifecycle, retention, replication, and data deletion posture',
      'Region, instance family, autoscaling, and scheduling choices where metadata is available',
      'Managed-service usage and resource efficiency signals already visible in inventory',
    ],
    candidates: [
      'Reuse cost and performance detectors that reduce idle capacity and waste',
      'Detect missing lifecycle policies and redundant retained data',
      'Flag workloads running in regions or resource types that need sustainability review',
      'Identify opportunities to scale with demand instead of fixed always-on capacity',
    ],
    manualEvidence: [
      'Sustainability goals, region-selection tradeoffs, and carbon accounting method',
      'Product-level demand modeling and user-impact decisions',
      'Team process, culture, and workload-owner sustainability attestations',
    ],
    links: [
      {
        label: 'AWS Sustainability Pillar',
        url: 'https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/welcome.html',
      },
      {
        label: 'Customer Carbon Footprint Tool',
        url: 'https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ccft-overview.html',
      },
    ],
  },
}

const hasFrameworkMappings = computed(() => {
  return (coverage.value?.mapped_catalog_total || 0) > 0
})

const hasExplicitFrameworkRefs = computed(() => {
  return (coverage.value?.frameworks || []).some((framework) => (framework.explicit_count || 0) > 0)
})

const scanContext = computed(() => coverage.value?.scan_context || null)

const topScanSignals = computed<FrameworkScanContextRow[]>(() => {
  const context = scanContext.value
  if (!context || context.status !== 'available') return []
  return [
    ...(context.by_service || []).slice(0, 4),
    ...(context.by_region || []).slice(0, 2),
  ].slice(0, 6)
})

const selectedFrameworkKey = computed(() => {
  if (!selectedFramework.value) return ''
  return frameworkKeys[selectedFramework.value] || ''
})

const selectedPolicyPack = computed(() => {
  if (!selectedPolicyPackId.value) return null
  return policyPacks.value.find((pack) => pack.id === selectedPolicyPackId.value) || null
})

const activeMappingKey = computed(() => {
  if (selectedPolicyPack.value) return 'well_architected'
  return selectedFrameworkKey.value
})

const selectedPillarDetails = computed(() => {
  if (!selectedPolicyPack.value) return null
  return pillarDetails[selectedPolicyPack.value.pillar] || null
})

const selectedDetailControls = computed(() => {
  if (!selectedPolicyPack.value) return []
  return detailControlsByPillar.value[selectedPolicyPack.value.pillar] || []
})

const selectedDetailControlsTotal = computed(() => {
  if (!selectedPolicyPack.value) return 0
  return detailControlTotalsByPillar.value[selectedPolicyPack.value.pillar] || 0
})

async function loadCoverage() {
  loading.value = true
  error.value = null
  try {
    const nextCoverage = await api.frameworkCoverage()
    coverage.value = nextCoverage
    if (nextCoverage.mapped_catalog_total > 0) {
      await loadControls()
    } else {
      controls.value = []
      controlsTotal.value = 0
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load framework coverage'
  } finally {
    loading.value = false
  }
}

async function loadPolicies() {
  policyLoading.value = true
  try {
    const response = await api.frameworkPolicies()
    policyPacks.value = response.items
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load Well-Architected policies'
  } finally {
    policyLoading.value = false
  }
}

async function activatePolicy(pack: FrameworkPolicyPack) {
  setBusy(activatingIds, pack.id, true)
  actionMessage.value = ''
  try {
    const updated = await api.activateFrameworkPolicy(pack.id)
    actionMessage.value = `${updated.name} is ready as a misconfig policy`
    await Promise.all([loadPolicies(), loadCoverage()])
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to activate policy'
  } finally {
    setBusy(activatingIds, pack.id, false)
  }
}

async function scanPolicy(pack: FrameworkPolicyPack) {
  if (!pack.misconfig_policy_id) return
  setBusy(scanningIds, pack.id, true)
  actionMessage.value = ''
  try {
    await api.scanMisconfigPolicy(pack.misconfig_policy_id)
    actionMessage.value = `${pack.name} scan completed`
    await Promise.all([loadPolicies(), loadCoverage(), loadControls()])
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to scan policy'
  } finally {
    setBusy(scanningIds, pack.id, false)
  }
}

function setBusy(target: { value: Set<string> }, id: string, value: boolean) {
  const next = new Set(target.value)
  if (value) {
    next.add(id)
  } else {
    next.delete(id)
  }
  target.value = next
}

async function loadControls() {
  if (!coverage.value || coverage.value.mapped_catalog_total === 0) return
  controlsLoading.value = true
  try {
    const params: Record<string, string> = { limit: '200' }
    if (selectedPillar.value) params.pillar = selectedPillar.value
    if (selectedFramework.value) params.framework = selectedFramework.value
    if (search.value.trim()) params.search = search.value.trim()
    const response = await api.frameworkControls(params)
    controls.value = response.items
    controlsTotal.value = response.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load mapped controls'
  } finally {
    controlsLoading.value = false
  }
}

function pillarLabel(pillar: string): string {
  return pillarLabels[pillar] || pillar
}

function refLabel(key: string): string {
  return refLabels[key] || key
}

function visibleRefs(control: FrameworkControl): { key: string; values: string[] }[] {
  return Object.entries(control.external_refs || {})
    .filter(([, values]) => values.length > 0)
    .map(([key, values]) => ({ key, values }))
}

function mappingLabel(control: FrameworkControl): string {
  const source = selectedMappingSource(control)
  if (source === 'explicit') return 'Explicit ref'
  if (source === 'inferred') return 'Pillar inferred'
  return 'Unmapped'
}

function mappingClass(control: FrameworkControl): string {
  return selectedMappingSource(control)
}

function mappingTitle(control: FrameworkControl): string {
  const source = selectedMappingSource(control)
  if (source === 'explicit') {
    return 'Catalog payload includes an explicit framework reference.'
  }
  if (source === 'inferred') {
    return 'Mapped from Well-Architected pillar metadata or risk-detail classification.'
  }
  return 'No framework mapping metadata is available for this control.'
}

function selectedMappingSource(control: FrameworkControl): 'explicit' | 'inferred' | 'none' {
  const frameworkKey = activeMappingKey.value
  if (frameworkKey) {
    return control.mapping_sources?.[frameworkKey] || 'none'
  }
  return control.mapping_source || 'none'
}

function frameworkEvidenceText(framework: FrameworkMappingCount): string {
  const explicit = framework.explicit_count || 0
  const inferred = framework.inferred_count || 0
  if (explicit && inferred) return `${formatNumber(explicit)} explicit / ${formatNumber(inferred)} inferred`
  if (explicit) return `${formatNumber(explicit)} explicit references`
  if (inferred) return `${formatNumber(inferred)} pillar inferred`
  return framework.external_ref_key
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value)
}

function openPolicyDetails(pack: FrameworkPolicyPack) {
  selectedPolicyPackId.value = pack.id
  void loadPolicyDetailControls(pack)
}

function closePolicyDetails() {
  selectedPolicyPackId.value = ''
}

function viewPolicyControls(pack: FrameworkPolicyPack) {
  selectedPillar.value = pack.pillar
  selectedFramework.value = 'well_architected'
  selectedPolicyPackId.value = ''
}

async function loadPolicyDetailControls(pack: FrameworkPolicyPack) {
  if (detailControlsByPillar.value[pack.pillar]) return
  detailControlsLoading.value = true
  detailControlsError.value = ''
  try {
    const response = await api.frameworkControls({
      pillar: pack.pillar,
      framework: 'well_architected',
      limit: '8',
    })
    detailControlsByPillar.value = {
      ...detailControlsByPillar.value,
      [pack.pillar]: response.items,
    }
    detailControlTotalsByPillar.value = {
      ...detailControlTotalsByPillar.value,
      [pack.pillar]: response.total,
    }
  } catch (e) {
    detailControlsError.value = e instanceof Error ? e.message : 'Failed to load mapped controls'
  } finally {
    detailControlsLoading.value = false
  }
}

function policySummary(pack: FrameworkPolicyPack): string {
  if (pack.executable_count === 0) {
    return 'Mapped for framework coverage; no executable detector is available yet.'
  }
  if (pack.open_findings > 0) {
    return `${pack.executable_count} executable checks with ${pack.open_findings} open findings.`
  }
  return `${pack.executable_count} executable checks are ready to scan.`
}

function supportStatus(control: FrameworkControl): 'executable' | 'planned' | 'unsupported' {
  if (control.executable) return 'executable'
  return control.support_status || 'unsupported'
}

function supportLabel(control: FrameworkControl): string {
  const status = supportStatus(control)
  if (status === 'executable') return 'Executable'
  if (status === 'planned') return 'Candidate'
  return 'Unsupported'
}

function supportIcon(control: FrameworkControl): string {
  const status = supportStatus(control)
  if (status === 'executable') return 'pi pi-check-circle'
  if (status === 'planned') return 'pi pi-wrench'
  return 'pi pi-ban'
}

function misconfigRoute(control: FrameworkControl) {
  return {
    path: '/misconfig',
    query: {
      misconfig_id: control.catalog_id,
      status: control.open_findings > 0 ? 'open' : undefined,
    },
  }
}

watch([selectedPillar, selectedFramework], () => {
  loadControls()
})

onMounted(() => {
  Promise.all([loadCoverage(), loadPolicies()])
})
</script>

<style scoped>
.frameworks-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
}

.summary-card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 1rem;
}

.card-value {
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--text-color);
}

.card-label {
  margin-top: 0.25rem;
  color: var(--text-color-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-card.mapped .card-value { color: #4ade80; }
.summary-card.unmapped .card-value { color: #facc15; }
.summary-card.findings .card-value { color: #f87171; }

.scan-context-card {
  overflow: visible;
}

.scan-context-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.7rem;
  padding: 1rem 1.25rem 0;
}

.scan-context-stat {
  padding: 0.75rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-ground);
}

.scan-context-stat strong {
  display: block;
  color: var(--text-color);
  font-size: 1.15rem;
}

.scan-context-stat span {
  display: block;
  margin-top: 0.2rem;
  color: var(--text-color-secondary);
  font-size: 0.76rem;
}

.scan-signal-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  padding: 0.8rem 1.25rem 1rem;
}

.scan-signal {
  padding: 0.25rem 0.5rem;
  border: 1px solid rgba(32, 108, 245, 0.25);
  border-radius: 5px;
  color: var(--text-color-secondary);
  background: rgba(32, 108, 245, 0.06);
  font-size: 0.76rem;
}

.section-card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.section-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-color);
}

.section-count {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: var(--text-color-secondary);
}

.section-empty {
  padding: 2.25rem;
  text-align: center;
  color: var(--text-color-secondary);
  font-size: 0.9rem;
}

.section-empty i {
  margin-right: 0.35rem;
}

.action-message {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
  color: #4ade80;
  font-size: 0.86rem;
}

.error-state {
  color: #f87171;
}

.policy-pack-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.7rem;
  padding: 0.9rem 1.25rem 1rem;
}

.policy-pack {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  min-height: 142px;
  padding: 0.85rem;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-ground);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}

.policy-pack:hover,
.policy-pack:focus-visible {
  border-color: var(--primary-color);
  background: rgba(32, 108, 245, 0.08);
  outline: none;
}

.policy-pack.active {
  border-color: rgba(74, 222, 128, 0.45);
}

.policy-pack.empty {
  opacity: 0.62;
}

.policy-pack-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.65rem;
}

.policy-pack h3 {
  margin: 0 0 0.35rem;
  color: var(--text-color);
  font-size: 0.82rem;
  line-height: 1.3;
}

.policy-pack p {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
}

.policy-state {
  flex: 0 0 auto;
  padding: 0.25rem 0.45rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  color: var(--text-color-secondary);
  font-size: 0.72rem;
  font-weight: 700;
}

.policy-state.enabled {
  border-color: rgba(74, 222, 128, 0.45);
  color: #4ade80;
}

.policy-open-hint {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: auto;
  color: var(--primary-color);
  font-size: 0.75rem;
  font-weight: 700;
}

.detail-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.62);
}

.policy-detail {
  width: min(900px, calc(100vw - 2rem));
  max-height: calc(100vh - 2rem);
  overflow: auto;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-card);
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.45);
}

.policy-detail-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.15rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.detail-eyebrow {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--primary-color);
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.policy-detail h2 {
  margin: 0;
  color: var(--text-color);
  font-size: 1.05rem;
  line-height: 1.3;
}

.policy-detail-header p {
  margin: 0.45rem 0 0;
  max-width: 720px;
  color: var(--text-color-secondary);
  font-size: 0.86rem;
  line-height: 1.5;
}

.icon-button {
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-color-secondary);
  cursor: pointer;
}

.icon-button:hover {
  color: var(--text-color);
  border-color: var(--primary-color);
}

.detail-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
  color: var(--text-color-secondary);
  font-size: 0.82rem;
}

.detail-summary span {
  padding: 0.3rem 0.55rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
}

.detail-summary span.enabled {
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.35);
}

.detail-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
  padding: 1rem 1.25rem;
}

.detail-metrics div {
  padding: 0.75rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-ground);
}

.detail-metrics strong {
  display: block;
  margin-bottom: 0.25rem;
  color: var(--text-color);
  font-size: 1.2rem;
}

.detail-metrics span {
  color: var(--text-color-secondary);
  font-size: 0.75rem;
}

.detail-copy {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  padding: 0 1.25rem 1rem;
}

.detail-copy div {
  padding: 0.8rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.025);
}

.detail-copy h3 {
  margin: 0 0 0.35rem;
  color: var(--text-color);
  font-size: 0.82rem;
}

.detail-copy p {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
}

.detail-sections {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  padding: 0 1.25rem 1rem;
}

.detail-sections section {
  min-width: 0;
  padding: 0.9rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-ground);
}

.detail-sections h3,
.reference-panel h3 {
  margin: 0 0 0.55rem;
  color: var(--text-color);
  font-size: 0.84rem;
}

.detail-sections ul {
  display: grid;
  gap: 0.45rem;
  margin: 0;
  padding-left: 1rem;
  color: var(--text-color-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
}

.detail-sections li::marker {
  color: var(--primary-color);
}

.reference-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 0.8fr);
  gap: 0.9rem;
  padding: 0 1.25rem 1rem;
}

.reference-panel > div {
  min-width: 0;
  padding: 0.9rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: rgba(32, 108, 245, 0.055);
}

.reference-panel p {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 0.78rem;
  line-height: 1.45;
}

.reference-links {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.reference-links a {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--primary-color);
  font-size: 0.8rem;
  font-weight: 700;
  text-decoration: none;
}

.reference-links a:hover {
  text-decoration: underline;
}

.detail-controls-panel {
  margin: 0 1.25rem 1rem;
  padding: 0.95rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-ground);
}

.detail-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.85rem;
  margin-bottom: 0.8rem;
}

.detail-panel-header h3 {
  margin: 0 0 0.35rem;
  color: var(--text-color);
  font-size: 0.86rem;
}

.detail-panel-header p {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
}

.detail-inline-state {
  padding: 0.85rem;
  border: 1px dashed var(--surface-border);
  border-radius: 6px;
  color: var(--text-color-secondary);
  font-size: 0.78rem;
}

.detail-inline-state i {
  margin-right: 0.35rem;
}

.detail-control-list {
  display: grid;
  gap: 0.65rem;
}

.detail-control {
  display: grid;
  grid-template-columns: minmax(220px, 1.6fr) minmax(150px, 0.75fr) minmax(180px, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.025);
}

.detail-control-main {
  min-width: 0;
}

.detail-control-main strong,
.detail-control-main code,
.detail-control-main span {
  display: block;
}

.detail-control-main strong {
  margin-bottom: 0.25rem;
  color: var(--text-color);
  font-size: 0.8rem;
  line-height: 1.35;
}

.detail-control-main code {
  margin-bottom: 0.2rem;
  color: #5a9aff;
  font-family: var(--font-mono), monospace;
  font-size: 0.72rem;
}

.detail-control-main span {
  color: var(--text-color-secondary);
  font-size: 0.74rem;
  line-height: 1.4;
}

.detail-control-meta,
.detail-control-refs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  min-width: 0;
}

.detail-control-meta {
  align-items: center;
}

.detail-control-refs .ref-chip {
  max-width: 170px;
}

.policy-detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  padding: 1rem 1.25rem 1.25rem;
  border-top: 1px solid var(--surface-border);
}

.readiness-card {
  display: flex;
  gap: 1.1rem;
  padding: 1.5rem;
}

.readiness-card.compact {
  padding: 1rem 1.25rem;
}

.readiness-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid rgba(32, 108, 245, 0.35);
  border-radius: 8px;
  color: var(--primary-color);
  background: rgba(32, 108, 245, 0.08);
}

.readiness-card h2 {
  margin: 0 0 0.45rem;
  font-size: 1.05rem;
  color: var(--text-color);
}

.readiness-card p {
  margin: 0;
  max-width: 780px;
  color: var(--text-color-secondary);
  line-height: 1.55;
  font-size: 0.9rem;
}

.readiness-card code,
.control-cell code {
  font-family: var(--font-mono), monospace;
  color: #5a9aff;
  font-size: 0.78rem;
}

.readiness-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.readiness-metrics span {
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  color: var(--text-color-secondary);
  font-size: 0.8rem;
}

.pillar-grid,
.framework-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0.75rem;
  padding: 1rem 1.25rem 1.25rem;
}

.pillar-card,
.framework-card {
  text-align: left;
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 0.85rem;
  color: var(--text-color);
  cursor: pointer;
  min-height: 96px;
}

.pillar-card:hover,
.framework-card:hover,
.pillar-card.active,
.framework-card.active {
  border-color: var(--primary-color);
  background: rgba(32, 108, 245, 0.12);
}

.pillar-card.empty,
.framework-card.empty {
  opacity: 0.55;
}

.pillar-name,
.framework-name {
  display: block;
  min-height: 2.4em;
  font-size: 0.85rem;
  font-weight: 700;
}

.pillar-count,
.framework-count {
  display: block;
  margin-top: 0.4rem;
  font-size: 1.35rem;
  font-weight: 700;
}

.pillar-meta,
.framework-key {
  display: block;
  margin-top: 0.25rem;
  color: var(--text-color-secondary);
  font-size: 0.75rem;
}

.framework-open {
  display: inline-flex;
  margin-top: 0.45rem;
  padding: 0.18rem 0.42rem;
  border-radius: 4px;
  color: #f87171;
  background: rgba(248, 113, 113, 0.12);
  font-size: 0.72rem;
  font-weight: 700;
}

.controls-header {
  align-items: flex-end;
}

.controls-actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: var(--surface-ground);
  color: var(--text-color-secondary);
}

.search-box input {
  width: min(260px, 48vw);
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-color);
  font-size: 0.85rem;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1120px;
}

.data-table th {
  text-align: left;
  padding: 0.7rem 1rem;
  background: var(--surface-ground);
  border-bottom: 1px solid var(--surface-border);
  color: var(--text-color-secondary);
  font-size: 0.73rem;
  font-weight: 700;
  text-transform: uppercase;
}

.data-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--surface-border);
  font-size: 0.85rem;
  vertical-align: top;
}

.data-table tr.unsupported-row td {
  background: rgba(0, 0, 0, 0.22);
  color: rgba(229, 231, 235, 0.76);
}

.data-table tr.planned-row td:first-child {
  box-shadow: inset 3px 0 0 rgba(250, 204, 21, 0.42);
}

.data-table tr.unsupported-row .control-cell strong {
  color: rgba(229, 231, 235, 0.88);
}

.control-cell {
  max-width: 330px;
}

.control-cell strong,
.control-cell code,
.control-cell span {
  display: block;
}

.control-cell strong {
  margin-bottom: 0.3rem;
}

.text-muted {
  color: var(--text-color-secondary);
  font-size: 0.78rem;
}

.service-badge,
.type-chip,
.ref-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  border-radius: 4px;
  font-size: 0.75rem;
  line-height: 1.2;
}

.service-badge {
  padding: 0.2rem 0.5rem;
  color: #5a9aff;
  background: rgba(32, 108, 245, 0.16);
}

.chip-list,
.ref-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.type-chip {
  padding: 0.18rem 0.45rem;
  background: rgba(255, 255, 255, 0.07);
  color: var(--text-color-secondary);
}

.ref-chip {
  padding: 0.2rem 0.45rem;
  color: #19d5d5;
  background: rgba(25, 213, 213, 0.12);
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-chip.muted {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.1);
}

.mapping-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.48rem;
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}

.mapping-badge.explicit {
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.32);
  background: rgba(74, 222, 128, 0.1);
}

.mapping-badge.inferred {
  color: #facc15;
  border-color: rgba(250, 204, 21, 0.28);
  background: rgba(250, 204, 21, 0.1);
}

.mapping-badge.none {
  color: #9ca3af;
  background: rgba(156, 163, 175, 0.08);
}

.support-badge,
.deactivated-label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 4px;
  font-size: 0.74rem;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}

.support-badge {
  padding: 0.24rem 0.5rem;
  border: 1px solid var(--surface-border);
}

.support-badge.executable {
  color: #4ade80;
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.32);
}

.support-badge.planned {
  color: #facc15;
  background: rgba(250, 204, 21, 0.1);
  border-color: rgba(250, 204, 21, 0.28);
}

.support-badge.unsupported {
  color: #9ca3af;
  background: rgba(17, 24, 39, 0.42);
  border-color: rgba(156, 163, 175, 0.22);
}

.deactivated-label {
  color: #8b949e;
}

.finding-count {
  font-weight: 700;
  color: var(--text-color-secondary);
}

.finding-count.active {
  color: #f87171;
}

.btn {
  padding: 0.5rem 0.9rem;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  text-decoration: none;
}

.btn-sm {
  padding: 0.35rem 0.65rem;
  font-size: 0.78rem;
}

.btn-outline {
  background: transparent;
  border: 1px solid var(--surface-border);
  color: var(--primary-color);
}

.btn-primary {
  background: var(--primary-color);
  color: #ffffff;
}

.btn-outline:hover {
  background: rgba(32, 108, 245, 0.12);
  border-color: var(--primary-color);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .readiness-card,
  .section-header,
  .controls-header,
  .controls-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .search-box input {
    width: 100%;
  }

  .detail-backdrop {
    align-items: stretch;
    padding: 0.75rem;
  }

  .policy-detail {
    width: 100%;
    max-height: calc(100vh - 1.5rem);
  }

  .policy-detail-header {
    flex-direction: column;
  }

  .detail-copy {
    grid-template-columns: 1fr;
  }

  .detail-sections,
  .reference-panel {
    grid-template-columns: 1fr;
  }

  .detail-panel-header,
  .detail-control {
    align-items: stretch;
    grid-template-columns: 1fr;
  }

  .detail-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .policy-detail-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
