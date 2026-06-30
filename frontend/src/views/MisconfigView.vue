<template>
  <div class="misconfig-view">
    <!-- Actions Bar -->
    <div class="actions-bar">
      <button
        class="btn btn-primary"
        :disabled="scanInProgress"
        @click="triggerScan"
      >
        <i :class="scanInProgress ? 'pi pi-spin pi-spinner' : 'pi pi-sync'"></i>
        {{ scanInProgress ? 'Scanning...' : 'Scan Resources' }}
      </button>
    </div>

    <!-- Scan Result Banner -->
    <div v-if="scanBanner" class="scan-banner">
      <i class="pi pi-check-circle"></i>
      <span>
        Scan complete -- misconfig evaluation finished
      </span>
      <button class="banner-dismiss" @click="scanBanner = null">
        <i class="pi pi-times"></i>
      </button>
    </div>

    <!-- Dashboard Summary Cards -->
    <div v-if="store.dashboard" class="summary-cards">
      <div class="summary-card">
        <div class="card-value">{{ totalFindings }}</div>
        <div class="card-label">Total Findings</div>
      </div>
      <div class="summary-card card-open">
        <div class="card-value">{{ store.dashboard.total_open }}</div>
        <div class="card-label">Open</div>
      </div>
      <div class="summary-card card-acknowledged">
        <div class="card-value">{{ store.dashboard.total_acknowledged }}</div>
        <div class="card-label">Acknowledged</div>
      </div>
      <div class="summary-card card-resolved">
        <div class="card-value">{{ store.dashboard.total_resolved }}</div>
        <div class="card-label">Resolved</div>
      </div>
      <div class="summary-card card-suppressed">
        <div class="card-value">{{ store.dashboard.total_suppressed }}</div>
        <div class="card-label">Suppressed</div>
      </div>
      <div v-for="tier in store.dashboard.by_tier" :key="tier.tier" class="summary-card" :class="'card-' + tier.tier">
        <div class="card-value">{{ tier.count }}</div>
        <div class="card-label" style="text-transform: capitalize">{{ tier.tier }}</div>
      </div>
    </div>

    <!-- Risk Breakdown -->
    <div v-if="store.dashboard && hasRiskData" class="section-card">
      <div class="section-header">
        <h2 class="section-title">Risk Breakdown</h2>
      </div>
      <div class="risk-breakdown">
        <div v-for="sev in store.dashboard.by_severity" :key="sev.risk_value" class="risk-bar-item">
          <span class="risk-label" :style="{ color: severityColor(sev.risk_value) }">{{ severityLabel(sev.risk_value) }}</span>
          <div class="risk-bar-bg">
            <div
              class="risk-bar-fill"
              :style="{ width: riskPercent(sev.count) + '%', background: severityColor(sev.risk_value) }"
            ></div>
          </div>
          <span class="risk-count">{{ sev.count }}</span>
        </div>
      </div>
    </div>

    <!-- Policies Section -->
    <div class="section-card">
      <div class="section-header">
        <h2 class="section-title">Misconfig Policies</h2>
        <div class="section-controls">
          <span class="section-count">{{ store.policies.length }} {{ store.policies.length === 1 ? 'policy' : 'policies' }}</span>
          <button class="btn btn-primary btn-sm" @click="openCreateForm">
            <i class="pi pi-plus"></i> New Policy
          </button>
        </div>
      </div>
      <div v-if="store.loading && !store.policies.length" class="section-empty">
        <i class="pi pi-spin pi-spinner"></i> Loading...
      </div>
      <div v-else-if="!store.policies.length" class="section-empty">
        No misconfig policies configured. Create one to start detecting misconfigurations.
      </div>
      <div v-else class="table-wrap">
        <table class="data-table policies-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Resource Types</th>
              <th>Checks</th>
              <th>Flagged</th>
              <th>Last Scanned</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="policy in store.policies" :key="policy.id">
              <td>
                <div class="policy-name">{{ policy.name }}</div>
                <div v-if="policy.description" class="policy-desc">{{ policy.description }}</div>
              </td>
              <td>
                <div class="type-chips">
                  <span v-for="t in (policy.resource_types || []).slice(0, 3)" :key="t" class="type-chip">{{ t }}</span>
                  <span v-if="(policy.resource_types || []).length > 3" class="type-chip type-more">
                    +{{ (policy.resource_types || []).length - 3 }}
                  </span>
                </div>
              </td>
              <td>
                <span class="check-count">{{ (policy.misconfig_ids || []).length }}</span>
              </td>
              <td>
                <span class="flagged-count" :class="{ 'has-findings': (policy.resources_flagged || 0) > 0 }">
                  {{ policy.resources_flagged || 0 }}
                </span>
              </td>
              <td class="text-muted">{{ formatDateTime(policy.last_scanned_at) }}</td>
              <td>
                <button
                  class="status-toggle"
                  :class="policy.enabled ? 'enabled' : 'disabled'"
                  @click="handleToggle(policy)"
                >
                  {{ policy.enabled ? 'Enabled' : 'Disabled' }}
                </button>
              </td>
              <td>
                <div class="actions-cell">
                  <button class="btn-icon" title="Scan" :disabled="policyScanIds.has(policy.id)" @click="handleScanPolicy(policy.id)">
                    <i :class="policyScanIds.has(policy.id) ? 'pi pi-spin pi-spinner' : 'pi pi-sync'"></i>
                  </button>
                  <button class="btn-icon" title="Edit" @click="openEditForm(policy)">
                    <i class="pi pi-pencil"></i>
                  </button>
                  <button class="btn-icon btn-icon-danger" title="Delete" @click="confirmDelete(policy)">
                    <i class="pi pi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Findings Section -->
    <div class="section-card">
      <div class="section-header">
        <h2 class="section-title">Findings</h2>
        <div class="section-controls">
          <span class="section-count">{{ store.findingsTotal }} total</span>
        </div>
      </div>

      <!-- Findings Filters -->
      <div class="findings-filters">
        <label class="filter-label">
          Status
          <select v-model="findingStatus" @change="handleFindingFilterChange">
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="suppressed">Suppressed</option>
          </select>
        </label>
        <label class="filter-label">
          Risk
          <select v-model="findingRisk" @change="handleFindingFilterChange">
            <option value="">All</option>
            <option value="security">Security</option>
            <option value="cost">Cost</option>
            <option value="operations">Operations</option>
            <option value="performance">Performance</option>
            <option value="reliability">Reliability</option>
          </select>
        </label>
        <label class="filter-label">
          Tier
          <select v-model="findingTier" @change="handleFindingFilterChange">
            <option value="">All</option>
            <option value="confirmed">Confirmed</option>
            <option value="advisory">Advisory</option>
          </select>
        </label>
        <label class="filter-label">
          Service
          <select v-model="findingService" @change="handleFindingFilterChange">
            <option value="">All</option>
            <option v-for="svc in serviceOptions" :key="svc" :value="svc">{{ svc }}</option>
          </select>
        </label>
        <div v-if="findingMisconfigId" class="active-query-filter">
          <span>Catalog check <code>{{ findingMisconfigId }}</code></span>
          <button class="btn btn-outline btn-sm" @click="clearMisconfigFilter">
            <i class="pi pi-times"></i>
            Clear
          </button>
        </div>
      </div>

      <div class="finding-groups-panel">
        <div class="finding-groups-header">
          <div>
            <h3>Grouped by Control</h3>
            <span>{{ store.findingGroupsTotal }} controls match the current filters</span>
          </div>
        </div>
        <div v-if="store.loading && !store.findingGroups.length" class="section-empty compact">
          <i class="pi pi-spin pi-spinner"></i> Loading grouped findings...
        </div>
        <div v-else-if="!store.findingGroups.length" class="section-empty compact">
          No grouped findings match the current filters
        </div>
        <div v-else class="finding-group-list">
          <article v-for="group in store.findingGroups" :key="group.misconfig_id" class="finding-group-card">
            <div class="finding-group-main">
              <div class="finding-group-title-row">
                <span class="severity-badge" :class="'sev-' + (group.risk_value || 0)">
                  {{ group.risk_value || 0 }}/3
                </span>
                <strong>{{ group.scenario }}</strong>
              </div>
              <div class="finding-group-meta">
                <span class="service-badge">{{ group.service_name }}</span>
                <span class="risk-pill" :class="'risk-' + (group.risk_type || '')">{{ group.risk_type }}</span>
                <code>{{ group.misconfig_id }}</code>
              </div>
              <p v-if="group.recommendation">{{ group.recommendation }}</p>
            </div>
            <div class="finding-group-scope">
              <span>{{ group.total_findings }} resources</span>
              <span>{{ group.confirmed_count }} confirmed</span>
              <span>{{ group.advisory_count }} advisory</span>
              <span>{{ group.account_count }} accounts</span>
              <span>{{ group.region_count }} regions</span>
            </div>
            <div class="finding-group-actions">
              <button class="btn btn-outline btn-sm" @click="focusFindingGroup(group.misconfig_id)">
                <i class="pi pi-filter"></i>
                View resources
              </button>
              <button
                v-if="group.sample_finding_id"
                class="btn btn-outline btn-sm"
                @click="openSampleFinding(group)"
              >
                <i class="pi pi-search"></i>
                Sample
              </button>
            </div>
          </article>
        </div>
      </div>

      <div v-if="store.loading && !store.findings.length" class="section-empty">
        <i class="pi pi-spin pi-spinner"></i> Loading...
      </div>
      <div v-else-if="!store.findings.length" class="section-empty">
        No findings match the current filters
      </div>
      <div v-else class="table-wrap">
        <table class="data-table findings-table">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Tier</th>
              <th>Risk</th>
              <th>Service</th>
              <th>Scenario</th>
              <th>Resource</th>
              <th>Status</th>
              <th>Detected</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in store.findings" :key="f.id">
              <td>
                <span class="severity-badge" :class="'sev-' + (f.risk_value || 0)">{{ f.risk_value || 0 }}/3</span>
              </td>
              <td>
                <span
                  class="tier-badge"
                  :class="f.evaluation_tier === 'confirmed' ? 'tier-confirmed' : 'tier-advisory'"
                  :title="f.evaluation_details || ''"
                >{{ f.evaluation_tier || 'advisory' }}</span>
              </td>
              <td>
                <span class="risk-pill" :class="'risk-' + (f.risk_type || '')">{{ f.risk_type }}</span>
              </td>
              <td>
                <span class="service-badge">{{ f.service_name }}</span>
              </td>
              <td class="scenario-cell">
                <span :title="f.scenario">{{ f.scenario }}</span>
              </td>
              <td class="arn-cell">
                <span
                  class="resource-label"
                  :class="{ empty: !resourceTitle(f) }"
                  :title="resourceTitle(f) || 'Resource identifier unavailable'"
                >{{ resourceLabel(f) }}</span>
              </td>
              <td>
                <span class="finding-status" :class="'status-' + f.status">{{ f.status }}</span>
              </td>
              <td class="text-muted">{{ formatDate(f.detected_at) }}</td>
              <td>
                <div class="actions-cell">
                  <button
                    class="btn-action"
                    title="View details"
                    @click="openFindingDetails(f)"
                  >
                    <i class="pi pi-search"></i>
                  </button>
                  <button
                    v-if="f.status === 'open'"
                    class="btn-action"
                    title="Acknowledge"
                    @click="handleUpdateFinding(f.id, 'acknowledged')"
                  >
                    <i class="pi pi-eye"></i>
                  </button>
                  <button
                    v-if="f.status === 'open' || f.status === 'acknowledged'"
                    class="btn-action btn-action-green"
                    title="Resolve"
                    @click="handleUpdateFinding(f.id, 'resolved')"
                  >
                    <i class="pi pi-check"></i>
                  </button>
                  <button
                    v-if="f.status === 'open' || f.status === 'acknowledged'"
                    class="btn-action btn-action-muted"
                    title="Suppress"
                    @click="handleUpdateFinding(f.id, 'suppressed')"
                  >
                    <i class="pi pi-ban"></i>
                  </button>
                  <button
                    v-if="f.status !== 'open'"
                    class="btn-action"
                    title="Reopen"
                    @click="handleUpdateFinding(f.id, 'open')"
                  >
                    <i class="pi pi-replay"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="store.findingsTotal > findingsLimit" class="pagination-bar">
        <button
          class="btn btn-sm btn-outline"
          :disabled="findingsOffset === 0"
          @click="goToPreviousFindingsPage"
        >
          Previous
        </button>
        <span class="pagination-info">
          {{ findingsOffset + 1 }}-{{ Math.min(findingsOffset + findingsLimit, store.findingsTotal) }}
          of {{ store.findingsTotal }}
        </span>
        <button
          class="btn btn-sm btn-outline"
          :disabled="findingsOffset + findingsLimit >= store.findingsTotal"
          @click="goToNextFindingsPage"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Finding Details -->
    <div v-if="selectedFinding" class="detail-overlay" @click.self="closeFindingDetails">
      <section class="detail-panel" role="dialog" aria-modal="true" aria-labelledby="finding-detail-title">
        <header class="detail-header">
          <div>
            <h2 id="finding-detail-title">Finding Details</h2>
            <p>{{ selectedFinding.scenario || 'Misconfiguration finding' }}</p>
          </div>
          <button class="detail-close" title="Close" @click="closeFindingDetails">
            <i class="pi pi-times"></i>
          </button>
        </header>

        <div class="detail-status-row">
          <span class="severity-badge" :class="'sev-' + (selectedFinding.risk_value || 0)">
            {{ selectedFinding.risk_value || 0 }}/3
          </span>
          <span
            class="tier-badge"
            :class="selectedFinding.evaluation_tier === 'confirmed' ? 'tier-confirmed' : 'tier-advisory'"
          >
            {{ selectedFinding.evaluation_tier || 'advisory' }}
          </span>
          <span class="risk-pill" :class="'risk-' + (selectedFinding.risk_type || '')">
            {{ selectedFinding.risk_type || 'unknown' }}
          </span>
          <span class="finding-status" :class="'status-' + selectedFinding.status">
            {{ selectedFinding.status }}
          </span>
          <span class="text-muted">{{ formatDateTime(selectedFinding.detected_at) }}</span>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">
            <i class="pi pi-shield"></i>
            Policy
          </div>
          <div class="detail-grid">
            <div>
              <span class="detail-label">Name</span>
              <strong>{{ selectedPolicy?.name || selectedFinding.policy_id || 'Unknown policy' }}</strong>
            </div>
            <div>
              <span class="detail-label">Status</span>
              <span v-if="selectedPolicy" class="finding-status" :class="selectedPolicy.enabled ? 'status-resolved' : 'status-suppressed'">
                {{ selectedPolicy.enabled ? 'enabled' : 'disabled' }}
              </span>
              <span v-else class="text-muted">Unavailable</span>
            </div>
            <div>
              <span class="detail-label">Checks</span>
              <strong>{{ selectedPolicy?.misconfig_ids?.length ?? '--' }}</strong>
            </div>
            <div>
              <span class="detail-label">Flagged</span>
              <strong>{{ selectedPolicy?.resources_flagged ?? '--' }}</strong>
            </div>
            <div>
              <span class="detail-label">Resource Types</span>
              <div v-if="selectedPolicy?.resource_types?.length" class="type-chips detail-chips">
                <span v-for="type in selectedPolicy.resource_types" :key="type" class="type-chip">{{ type }}</span>
              </div>
              <span v-else class="text-muted">No resource type filter</span>
            </div>
            <div>
              <span class="detail-label">Last Scanned</span>
              <span>{{ formatDateTime(selectedPolicy?.last_scanned_at) }}</span>
            </div>
          </div>
          <p v-if="selectedPolicy?.description" class="detail-copy">{{ selectedPolicy.description }}</p>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">
            <i class="pi pi-server"></i>
            Matched Resource
          </div>
          <div class="detail-grid">
            <div>
              <span class="detail-label">Identifier</span>
              <code>{{ selectedFinding.resource_id || resourceDisplayValue(resourceTitle(selectedFinding)) || '--' }}</code>
            </div>
            <div>
              <span class="detail-label">Service</span>
              <span class="service-badge">{{ selectedFinding.service_name || '--' }}</span>
            </div>
            <div>
              <span class="detail-label">Resource Type</span>
              <code>{{ selectedFinding.resource_type || '--' }}</code>
            </div>
            <div>
              <span class="detail-label">ARN</span>
              <code class="detail-long-value">{{ selectedFinding.resource_arn || '--' }}</code>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">
            <i class="pi pi-list-check"></i>
            Matched Check
          </div>
          <div class="detail-grid">
            <div>
              <span class="detail-label">Catalog ID</span>
              <code>{{ selectedFinding.misconfig_id }}</code>
            </div>
            <div>
              <span class="detail-label">Scenario</span>
              <span>{{ selectedFinding.scenario || '--' }}</span>
            </div>
            <div class="detail-wide">
              <span class="detail-label">Evidence</span>
              <p class="detail-copy">{{ selectedFinding.evaluation_details || 'No evaluator details were recorded for this finding.' }}</p>
            </div>
            <div class="detail-wide">
              <span class="detail-label">Recommendation</span>
              <p class="detail-copy">{{ selectedFinding.recommendation || 'No recommendation text is available for this catalog check.' }}</p>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Dialogs -->
    <MisconfigPolicyFormDialog
      :visible="showPolicyForm"
      :edit-policy="editingPolicy"
      @close="closePolicyForm"
      @saved="handlePolicySaved"
    />
    <ConfirmDialog
      :visible="showDeleteConfirm"
      title="Delete Policy"
      :message="`Are you sure you want to delete policy '${deletingPolicy?.name}'? All associated findings will also be deleted.`"
      confirm-label="Delete"
      :danger="true"
      @confirm="handleDeletePolicy"
      @cancel="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMisconfigStore } from '@/stores/misconfig'
import type { MisconfigFinding, MisconfigFindingGroup, MisconfigPolicy } from '@/types/api'
import MisconfigPolicyFormDialog from '@/components/MisconfigPolicyFormDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const store = useMisconfigStore()
const route = useRoute()
const router = useRouter()

// Scan state
const scanInProgress = ref(false)
const scanBanner = ref<boolean | null>(null)
const policyScanIds = ref<Set<string>>(new Set())

// Policy form
const showPolicyForm = ref(false)
const editingPolicy = ref<MisconfigPolicy | null>(null)

// Delete confirm
const showDeleteConfirm = ref(false)
const deletingPolicy = ref<MisconfigPolicy | null>(null)
const selectedFinding = ref<MisconfigFinding | null>(null)

// Finding filters
const findingStatus = ref('open')
const findingRisk = ref('')
const findingTier = ref('')
const findingService = ref('')
const findingMisconfigId = ref('')
const findingsOffset = ref(0)
const findingsLimit = 25
const findingGroupsLimit = 12

// Derived
const totalFindings = computed(() => {
  if (!store.dashboard) return 0
  return store.dashboard.total_open + store.dashboard.total_acknowledged +
    store.dashboard.total_resolved + store.dashboard.total_suppressed
})

const hasRiskData = computed(() => {
  if (!store.dashboard?.by_severity) return false
  return store.dashboard.by_severity.length > 0
})

const maxRiskCount = computed(() => {
  if (!store.dashboard?.by_severity?.length) return 1
  return Math.max(1, ...store.dashboard.by_severity.map(s => s.count))
})

const serviceOptions = computed(() => {
  if (!store.dashboard?.by_service) return []
  return store.dashboard.by_service.map(s => s.service).sort()
})

const selectedPolicy = computed(() => {
  if (!selectedFinding.value?.policy_id) return null
  return store.policies.find((policy) => policy.id === selectedFinding.value?.policy_id) || null
})

function riskPercent(count: number): number {
  return (count / maxRiskCount.value) * 100
}

function severityLabel(val: number): string {
  return ({ 3: 'Critical', 2: 'High', 1: 'Medium', 0: 'Low' } as Record<number, string>)[val] || 'Unknown'
}

function severityColor(val: number): string {
  return ({ 3: '#f87171', 2: '#fb923c', 1: '#facc15', 0: '#5a9aff' } as Record<number, string>)[val] || '#a0a0a0'
}

function resourceTitle(finding: MisconfigFinding): string {
  return finding.resource_arn || finding.resource_id || ''
}

function resourceLabel(finding: MisconfigFinding): string {
  const value = resourceTitle(finding)
  if (!value) return '--'
  return truncateMiddle(resourceDisplayValue(value), 48)
}

function resourceDisplayValue(value: string): string {
  if (!value.startsWith('arn:')) return value
  const arnParts = value.split(':')
  const resourcePart = arnParts.slice(5).join(':')
  return resourcePart || value
}

function truncateMiddle(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value
  const suffixLength = 14
  const prefixLength = Math.max(1, maxLength - suffixLength - 3)
  return `${value.slice(0, prefixLength)}...${value.slice(-suffixLength)}`
}

function formatDateTime(val?: string | null): string {
  if (!val) return '--'
  try {
    return new Date(val).toLocaleString()
  } catch { return val }
}

function formatDate(val?: string | null): string {
  if (!val) return '--'
  try {
    return new Date(val).toLocaleDateString()
  } catch { return val }
}

// --- Actions ---

async function triggerScan() {
  if (scanInProgress.value) return
  scanInProgress.value = true
  try {
    await store.triggerScan()
    // Wait briefly for scan to complete, then refresh
    setTimeout(async () => {
      scanBanner.value = true
      setTimeout(() => { scanBanner.value = null }, 10000)
      await refreshFindingData()
      scanInProgress.value = false
    }, 5000)
  } catch {
    scanInProgress.value = false
  }
}

async function handleScanPolicy(policyId: string) {
  policyScanIds.value.add(policyId)
  try {
    await store.scanPolicy(policyId)
    setTimeout(async () => {
      await refreshFindingData()
      policyScanIds.value.delete(policyId)
    }, 5000)
  } catch {
    policyScanIds.value.delete(policyId)
  }
}

function openCreateForm() {
  editingPolicy.value = null
  showPolicyForm.value = true
}

function openEditForm(policy: MisconfigPolicy) {
  editingPolicy.value = policy
  showPolicyForm.value = true
}

function closePolicyForm() {
  showPolicyForm.value = false
  editingPolicy.value = null
}

function handlePolicySaved() {
  refreshFindingData()
}

async function handleToggle(policy: MisconfigPolicy) {
  await store.updatePolicy(policy.id, { enabled: !policy.enabled })
  await store.fetchPolicies()
}

function confirmDelete(policy: MisconfigPolicy) {
  deletingPolicy.value = policy
  showDeleteConfirm.value = true
}

function openFindingDetails(finding: MisconfigFinding) {
  selectedFinding.value = finding
}

function closeFindingDetails() {
  selectedFinding.value = null
}

async function handleDeletePolicy() {
  if (deletingPolicy.value) {
    await store.deletePolicy(deletingPolicy.value.id)
    await refreshFindingData()
  }
  showDeleteConfirm.value = false
  deletingPolicy.value = null
}

async function handleUpdateFinding(id: string, status: string) {
  await store.updateFinding(id, status)
  await refreshFindingData()
}

function handleFindingFilterChange() {
  findingsOffset.value = 0
  refreshFindingData()
}

function goToPreviousFindingsPage() {
  findingsOffset.value = Math.max(0, findingsOffset.value - findingsLimit)
  loadFindings()
}

function goToNextFindingsPage() {
  findingsOffset.value += findingsLimit
  loadFindings()
}

function findingFilterParams(): Record<string, string> {
  const filters: Record<string, string> = {}
  if (findingStatus.value) filters.status = findingStatus.value
  if (findingRisk.value) filters.risk_type = findingRisk.value
  if (findingTier.value) filters.tier = findingTier.value
  if (findingService.value) filters.service = findingService.value
  if (findingMisconfigId.value) filters.misconfig_id = findingMisconfigId.value
  return filters
}

async function loadFindings() {
  const filters = findingFilterParams()
  filters.page = String(Math.floor(findingsOffset.value / findingsLimit) + 1)
  filters.page_size = String(findingsLimit)
  const result = await store.fetchFindings(filters)
  if (result.total > 0 && findingsOffset.value >= result.total) {
    findingsOffset.value = Math.floor((result.total - 1) / findingsLimit) * findingsLimit
    return loadFindings()
  }
  return result
}

async function loadFindingGroups() {
  const filters = findingFilterParams()
  filters.limit = String(findingGroupsLimit)
  return store.fetchFindingGroups(filters)
}

async function refreshFindingData() {
  await Promise.all([
    store.fetchDashboard(),
    store.fetchPolicies(),
    loadFindings(),
    loadFindingGroups(),
  ])
}

function focusFindingGroup(misconfigId: string) {
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      misconfig_id: misconfigId,
      status: findingStatus.value || 'open',
    },
  })
}

function openSampleFinding(group: MisconfigFindingGroup) {
  const sample = store.findings.find((finding) => finding.id === group.sample_finding_id)
  if (sample) {
    openFindingDetails(sample)
    return
  }
  focusFindingGroup(group.misconfig_id)
}

function queryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : ''
  }
  return typeof value === 'string' ? value : ''
}

function applyQueryFilters() {
  findingStatus.value = queryValue(route.query.status) || 'open'
  findingRisk.value = queryValue(route.query.risk_type)
  findingTier.value = queryValue(route.query.tier)
  findingService.value = queryValue(route.query.service)
  findingMisconfigId.value = queryValue(route.query.misconfig_id)
  findingsOffset.value = 0
}

function clearMisconfigFilter() {
  const nextQuery = { ...route.query }
  delete nextQuery.misconfig_id
  router.replace({ path: route.path, query: nextQuery })
}

watch(() => route.query, () => {
  applyQueryFilters()
  refreshFindingData()
})

onMounted(() => {
  applyQueryFilters()
  refreshFindingData()
})
</script>

<style scoped>
.misconfig-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.actions-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
}

/* Scan banner */
.scan-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  color: #4ade80;
  font-size: 0.85rem;
}

.scan-banner strong { font-weight: 700; }

.banner-dismiss {
  margin-left: auto;
  background: none;
  border: none;
  color: #4ade80;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.banner-dismiss:hover { background: rgba(34, 197, 94, 0.2); }

/* Summary cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
}

.summary-card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  padding: 1rem;
  text-align: center;
}

.card-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-color);
}

.card-label {
  font-size: 0.75rem;
  color: var(--text-color-secondary);
  margin-top: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.card-open .card-value { color: #f87171; }
.card-acknowledged .card-value { color: #facc15; }
.card-resolved .card-value { color: #4ade80; }
.card-suppressed .card-value { color: var(--text-color-secondary); }
.card-confirmed .card-value { color: #4ade80; }
.card-advisory .card-value { color: #facc15; }

/* Risk breakdown */
.risk-breakdown {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.risk-bar-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.risk-label {
  font-size: 0.8rem;
  font-weight: 500;
  min-width: 90px;
  text-transform: capitalize;
}

.risk-bar-bg {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  overflow: hidden;
}

.risk-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.risk-count {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-color);
  min-width: 30px;
  text-align: right;
}

/* Risk colors */
.risk-security { color: #f87171; }
.risk-cost { color: #facc15; }
.risk-operations { color: #5a9aff; }
.risk-performance { color: #a855f7; }
.risk-reliability { color: #19d5d5; }

.risk-fill-security { background: #f87171; }
.risk-fill-cost { background: #facc15; }
.risk-fill-operations { background: #5a9aff; }
.risk-fill-performance { background: #a855f7; }
.risk-fill-reliability { background: #19d5d5; }

/* Section card - reusable */
.section-card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.section-title {
  font-size: 0.95rem;
  font-weight: 600;
  background: var(--gradient-brand-horizontal);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.section-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.section-count {
  font-size: 0.8rem;
  color: var(--text-color-secondary);
}

.section-empty {
  padding: 2.5rem;
  text-align: center;
  color: var(--text-color-secondary);
  font-size: 0.875rem;
}

.section-empty.compact {
  padding: 1.25rem;
}

/* Data table */
.table-wrap {
  width: 100%;
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.policies-table {
  min-width: 920px;
}

.findings-table {
  min-width: 1120px;
}

.data-table th {
  text-align: left;
  padding: 0.65rem 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-color-secondary);
  background: var(--surface-ground);
  border-bottom: 1px solid var(--surface-border);
}

.data-table td {
  padding: 0.65rem 1rem;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--surface-border);
}

.data-table tbody tr:hover {
  background: rgba(32, 108, 245, 0.05);
}

.data-table th:last-child,
.data-table td:last-child {
  position: sticky;
  right: 0;
  z-index: 1;
  width: 1%;
  background: var(--surface-card);
  box-shadow: -10px 0 18px rgba(0, 0, 0, 0.18);
}

.data-table th:last-child {
  z-index: 2;
  background: var(--surface-ground);
}

.data-table tbody tr:hover td:last-child {
  background: #111827;
}

/* Policy table cells */
.policy-name { font-weight: 500; }
.policy-desc {
  font-size: 0.78rem;
  color: var(--text-color-secondary);
  margin-top: 2px;
}

.type-chips {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.type-chip {
  background: rgba(255, 255, 255, 0.06);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.75rem;
  color: var(--text-color-secondary);
}

.type-more {
  background: rgba(255, 255, 255, 0.1);
  font-weight: 500;
}

.check-count {
  font-weight: 600;
  font-size: 0.82rem;
}

.flagged-count {
  font-weight: 600;
  font-size: 0.82rem;
}

.flagged-count.has-findings {
  color: #f87171;
}

.status-toggle {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}

.status-toggle.enabled {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.status-toggle.enabled:hover { background: rgba(34, 197, 94, 0.25); }

.status-toggle.disabled {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-color-secondary);
}

.status-toggle.disabled:hover { background: rgba(255, 255, 255, 0.1); }

.actions-cell {
  display: inline-flex;
  gap: 0.35rem;
  align-items: center;
  min-width: max-content;
  white-space: nowrap;
}

.btn-icon {
  background: none;
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  padding: 0.3rem 0.45rem;
  cursor: pointer;
  color: var(--text-color-secondary);
  font-size: 0.8rem;
  transition: all 0.15s;
}

.btn-icon:hover {
  background: var(--surface-ground);
  color: var(--primary-color);
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: default;
}

.btn-icon-danger:hover {
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.15);
}

/* Findings filters */
.findings-filters {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
  background: var(--surface-ground);
  flex-wrap: wrap;
}

.filter-label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-color-secondary);
}

.filter-label select {
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  font-size: 0.82rem;
  background: var(--surface-ground);
  color: var(--text-color);
}

.active-query-filter {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-height: 34px;
  padding: 0.2rem 0.3rem 0.2rem 0.6rem;
  border: 1px solid rgba(32, 108, 245, 0.35);
  border-radius: 6px;
  color: var(--text-color-secondary);
  font-size: 0.8rem;
  background: rgba(32, 108, 245, 0.08);
}

.active-query-filter code {
  color: #5a9aff;
  font-family: var(--font-mono), monospace;
  font-size: 0.76rem;
}

.finding-groups-panel {
  border-bottom: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.018);
}

.finding-groups-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.25rem 0;
}

.finding-groups-header h3 {
  margin: 0;
  color: var(--text-color);
  font-size: 0.88rem;
}

.finding-groups-header span {
  display: block;
  margin-top: 0.2rem;
  color: var(--text-color-secondary);
  font-size: 0.78rem;
}

.finding-group-list {
  display: grid;
  gap: 0.65rem;
  padding: 0.85rem 1.25rem 1rem;
}

.finding-group-card {
  display: grid;
  grid-template-columns: minmax(260px, 1.5fr) minmax(240px, 0.9fr) auto;
  align-items: center;
  gap: 0.8rem;
  padding: 0.85rem;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-ground);
}

.finding-group-main {
  min-width: 0;
}

.finding-group-title-row {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
}

.finding-group-title-row strong {
  min-width: 0;
  color: var(--text-color);
  font-size: 0.84rem;
  line-height: 1.35;
}

.finding-group-meta,
.finding-group-scope,
.finding-group-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}

.finding-group-meta {
  margin-top: 0.45rem;
}

.finding-group-meta code {
  color: #5a9aff;
  font-family: var(--font-mono), monospace;
  font-size: 0.72rem;
}

.finding-group-main p {
  margin: 0.5rem 0 0;
  color: var(--text-color-secondary);
  font-size: 0.76rem;
  line-height: 1.45;
}

.finding-group-scope span {
  padding: 0.2rem 0.45rem;
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  color: var(--text-color-secondary);
  font-size: 0.74rem;
}

.finding-group-actions {
  justify-content: flex-end;
  min-width: max-content;
}

/* Findings table */
.severity-badge {
  font-size: 0.72rem;
  padding: 0.15rem 0.35rem;
  border-radius: 3px;
  font-weight: 600;
  min-width: 28px;
  text-align: center;
  display: inline-block;
}

.sev-3 { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.sev-2 { background: rgba(234, 179, 8, 0.2); color: #facc15; }
.sev-1 { background: rgba(32, 108, 245, 0.2); color: #5a9aff; }
.sev-0 { background: rgba(255, 255, 255, 0.05); color: var(--text-color-secondary); }

.tier-badge {
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: capitalize;
}

.tier-confirmed {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
}

.tier-advisory {
  background: rgba(250, 204, 21, 0.15);
  color: #facc15;
}

.risk-pill {
  padding: 0.15rem 0.45rem;
  border-radius: 10px;
  font-size: 0.72rem;
  font-weight: 500;
  text-transform: capitalize;
}

.risk-pill.risk-security { background: rgba(248, 113, 113, 0.15); }
.risk-pill.risk-cost { background: rgba(250, 204, 21, 0.15); }
.risk-pill.risk-operations { background: rgba(90, 154, 255, 0.15); }
.risk-pill.risk-performance { background: rgba(168, 85, 247, 0.15); }
.risk-pill.risk-reliability { background: rgba(25, 213, 213, 0.15); }

.service-badge {
  background: rgba(32, 108, 245, 0.15);
  color: #5a9aff;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 500;
}

.scenario-cell {
  max-width: 250px;
}

.scenario-cell span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arn-cell {
  font-family: var(--font-mono), monospace;
  font-size: 0.78rem;
  color: var(--text-color-secondary);
  max-width: 200px;
}

.arn-cell .resource-label {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-label {
  color: #5a9aff;
}

.resource-label.empty {
  color: var(--text-color-secondary);
}

.finding-status {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 500;
  text-transform: capitalize;
}

.status-open { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.status-acknowledged { background: rgba(250, 204, 21, 0.15); color: #facc15; }
.status-resolved { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.status-suppressed { background: rgba(255, 255, 255, 0.06); color: var(--text-color-secondary); }

.btn-action {
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  padding: 0.2rem 0.45rem;
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--primary-color);
  transition: all 0.15s;
}

.btn-action:hover { background: rgba(32, 108, 245, 0.12); }

.btn-action-green { color: #4ade80; }
.btn-action-green:hover { background: rgba(34, 197, 94, 0.15); }

.btn-action-muted { color: var(--text-color-secondary); }
.btn-action-muted:hover { background: rgba(255, 255, 255, 0.08); }

.text-muted {
  color: var(--text-color-secondary);
  font-size: 0.78rem;
}

/* Pagination */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem;
  border-top: 1px solid var(--surface-border);
}

.pagination-info {
  font-size: 0.82rem;
  color: var(--text-color-secondary);
}

/* Buttons */
.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.btn-primary {
  background: var(--gradient-brand-horizontal);
  color: white;
}

.btn-primary:hover:not(:disabled) { box-shadow: 0 0 14px rgba(32, 108, 245, 0.35); }
.btn-primary:disabled { opacity: 0.7; cursor: not-allowed; }

.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
}

.btn-outline {
  background: transparent;
  border: 1px solid var(--surface-border);
  color: var(--primary-color);
}

.btn-outline:hover:not(:disabled) {
  background: rgba(32, 108, 245, 0.12);
  border-color: var(--primary-color);
}

.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }

/* Finding detail modal */
.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  background: rgba(0, 0, 0, 0.55);
}

.detail-panel {
  width: min(760px, 100vw);
  height: 100%;
  overflow-y: auto;
  background: var(--surface-card);
  border-left: 1px solid var(--surface-border);
  box-shadow: -18px 0 36px rgba(0, 0, 0, 0.32);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.detail-header h2 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-color);
}

.detail-header p {
  margin: 0.3rem 0 0;
  color: var(--text-color-secondary);
  font-size: 0.85rem;
}

.detail-close {
  background: transparent;
  border: 1px solid var(--surface-border);
  color: var(--text-color-secondary);
  border-radius: 6px;
  width: 34px;
  height: 34px;
  cursor: pointer;
}

.detail-close:hover {
  color: var(--text-color);
  background: var(--surface-ground);
}

.detail-status-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
  background: var(--surface-ground);
}

.detail-section {
  padding: 1.2rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.detail-section-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.85rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--primary-color);
  text-transform: uppercase;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem 1rem;
}

.detail-grid > div {
  min-width: 0;
}

.detail-label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-color-secondary);
  text-transform: uppercase;
}

.detail-copy {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 0.84rem;
  line-height: 1.45;
}

.detail-wide {
  grid-column: 1 / -1;
}

.detail-chips {
  margin-top: 0.15rem;
}

.detail-long-value {
  display: block;
  max-width: 100%;
  overflow-wrap: anywhere;
  white-space: normal;
}

.detail-panel code {
  color: #5a9aff;
  font-family: var(--font-mono), monospace;
  font-size: 0.78rem;
}

@media (max-width: 720px) {
  .finding-group-card {
    align-items: stretch;
    grid-template-columns: 1fr;
  }

  .finding-group-actions {
    justify-content: flex-start;
    min-width: 0;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

/* Spinner */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.pi-spin { animation: spin 1s linear infinite; }
</style>
