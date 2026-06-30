<template>
  <div class="setup-subview">
    <div class="subview-header">
      <div class="subview-title-row">
        <button class="btn-icon" title="Back to Setup" @click="router.push('/setup')">
          <i class="pi pi-arrow-left"></i>
        </button>
        <h2>Multi-Account Management</h2>
      </div>
      <button class="btn btn-secondary" :disabled="loading" @click="refresh">
        <i class="pi pi-refresh" :class="{ spin: loading }"></i>
        Refresh
      </button>
    </div>

    <div v-if="validation && !validation.can_deploy && !validation.error" class="callout callout-warning">
      <i class="pi pi-exclamation-triangle"></i>
      <div>
        <strong>Cannot deploy from this account</strong>
        <p>{{ validation.guidance || 'Run from the management account or a delegated CloudFormation StackSets admin.' }}</p>
      </div>
    </div>
    <div v-if="validation?.error" class="callout callout-danger">
      <i class="pi pi-times-circle"></i>
      <div>
        <strong>{{ validation.error }}</strong>
        <p v-if="validation.guidance">{{ validation.guidance }}</p>
      </div>
    </div>

    <div v-if="activeJob" class="job-banner">
      <div>
        <strong>{{ jobLabel }}</strong>
        <span>{{ activeJob.progress_message || activeJob.status }}</span>
      </div>
      <div class="job-progress">
        <div :style="{ width: `${activeJob.progress || 0}%` }"></div>
      </div>
    </div>

    <div v-if="result" class="result-banner" :class="result.success ? 'result-ok' : 'result-error'">
      <i :class="result.success ? 'pi pi-check-circle' : 'pi pi-times-circle'"></i>
      <span>{{ result.message }}</span>
      <button class="btn-icon btn-icon-flat" @click="result = null"><i class="pi pi-times"></i></button>
    </div>

    <div v-if="error" class="result-banner result-error">
      <i class="pi pi-exclamation-triangle"></i>
      <span>{{ error }}</span>
    </div>

    <div v-if="status" class="section-card" :class="statusCardClass">
      <div class="card-title-row">
        <span class="status-badge" :class="statusBadgeClass">
          <i :class="statusBadgeIcon"></i>
          {{ statusBadgeLabel }}
        </span>
        <span v-if="status.template_version" class="muted">Template: {{ status.template_version }}</span>
      </div>
      <div class="metric-grid">
        <div>
          <strong>{{ status.instance_count }}</strong>
          <span>Stack Instances</span>
        </div>
        <div>
          <strong>{{ currentInstances }}</strong>
          <span>Current</span>
        </div>
        <div>
          <strong>{{ failedInstances }}</strong>
          <span>Failed / Outdated</span>
        </div>
      </div>
    </div>

    <div class="action-row">
      <button v-if="!status?.exists" class="btn btn-primary" :disabled="isBusy || !canDeploy" @click="deploy(false)">
        <i class="pi pi-cloud-upload"></i>
        Deploy StackSet
      </button>
      <button v-else class="btn btn-primary" :disabled="isBusy || !canDeploy" @click="update">
        <i class="pi pi-sync"></i>
        Update Template
      </button>
      <button class="btn btn-warning" :disabled="isBusy || !canDeploy" @click="showCleanConfirm = true">
        <i class="pi pi-refresh"></i>
        Clean &amp; Redeploy
      </button>
      <button v-if="status?.exists" class="btn btn-danger" :disabled="isBusy || !canDeploy" @click="showRemoveConfirm = true">
        <i class="pi pi-trash"></i>
        Remove All
      </button>
    </div>

    <div v-if="status?.exists && status.instances.length" class="section-card">
      <div class="card-title-row">
        <h3>Stack Instances</h3>
        <span class="muted">{{ status.instances.length }} instance{{ status.instances.length === 1 ? '' : 's' }}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Region</th>
              <th>Status</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in status.instances" :key="`${item.account_id}:${item.region}`">
              <td class="mono">{{ item.account_id }}</td>
              <td>{{ item.region }}</td>
              <td><span class="instance-status">{{ item.status }}</span></td>
              <td>{{ item.status_reason || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="accounts.length" class="section-card">
      <div class="card-title-row">
        <h3>Tracked Accounts</h3>
        <span class="muted">{{ accounts.length }} account{{ accounts.length === 1 ? '' : 's' }}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Name</th>
              <th>Discovery</th>
              <th>Access</th>
              <th>Resources</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="account in accounts" :key="account.account_id">
              <td class="mono">{{ account.account_id }}</td>
              <td>{{ account.account_name || '-' }}</td>
              <td>{{ account.enabled_for_discovery ? 'Enabled' : 'Disabled' }}</td>
              <td>{{ account.access_check_status || '-' }}</td>
              <td>{{ account.total_resources_discovered ?? 0 }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section-card">
      <div class="card-title-row">
        <h3>CloudFormation Templates</h3>
        <span class="muted">Served by bluearch-core</span>
      </div>
      <div class="template-list">
        <div v-for="name in templateNames" :key="name" class="template-item">
          <div class="card-title-row">
            <div>
              <strong>{{ name }}</strong>
              <p v-if="templateMeta[name]">{{ templateMeta[name].description }}</p>
            </div>
            <div class="template-actions">
              <a v-if="templateMeta[name]?.public_url" :href="templateMeta[name].public_url" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
                <i class="pi pi-download"></i>
                Download
              </a>
              <button class="btn btn-secondary btn-sm" @click="toggleTemplate(name)">
                <i class="pi" :class="showTemplates[name] ? 'pi-eye-slash' : 'pi-eye'"></i>
                {{ showTemplates[name] ? 'Hide' : 'View' }}
              </button>
            </div>
          </div>
          <div v-if="templateLoading[name]" class="empty-state"><i class="pi pi-spin pi-spinner"></i> Loading template...</div>
          <pre v-else-if="showTemplates[name] && templateContents[name]" class="template-content">{{ templateContents[name] }}</pre>
        </div>
        <div v-if="templateNames.length === 0" class="empty-state">Template metadata is unavailable from core.</div>
      </div>
    </div>

    <div v-if="showRemoveConfirm" class="dialog-overlay" @click.self="showRemoveConfirm = false">
      <div class="dialog">
        <h3>Remove All Infrastructure</h3>
        <p>Core will remove the StackSet, all stack instances, and tracked account records created by the shared setup workflow.</p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showRemoveConfirm = false">Cancel</button>
          <button class="btn btn-danger" @click="remove">Remove</button>
        </div>
      </div>
    </div>

    <div v-if="showCleanConfirm" class="dialog-overlay" @click.self="showCleanConfirm = false">
      <div class="dialog">
        <h3>Clean &amp; Redeploy</h3>
        <p>Core will recreate cross-account infrastructure using its current template registry.</p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showCleanConfirm = false">Cancel</button>
          <button class="btn btn-warning" @click="deploy(true)">Clean &amp; Redeploy</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { api } from '@/api/client'
import { useMultiAccountStore } from '@/stores/multiAccount'
import type { JobResponse } from '@/types/api'

const router = useRouter()
const multiAccountStore = useMultiAccountStore()
const {
  accounts,
  componentTemplateMap,
  error,
  loading,
  status,
  validation,
} = storeToRefs(multiAccountStore)
const templateMeta = multiAccountStore.templateMeta
const activeJob = ref<JobResponse | null>(null)
const result = ref<{ success: boolean; message: string } | null>(null)
const showRemoveConfirm = ref(false)
const showCleanConfirm = ref(false)
const cleanDeploy = ref(false)
const templateContents = reactive<Record<string, string>>({})
const templateLoading = reactive<Record<string, boolean>>({})
const showTemplates = reactive<Record<string, boolean>>({})
let pollTimer: ReturnType<typeof setInterval> | null = null

const templateNames = computed(() => [
  componentTemplateMap.value['cross-account'],
  componentTemplateMap.value['management-resources'],
].filter(Boolean) as string[])
const currentInstances = computed(() => status.value?.instances.filter(item => item.status === 'CURRENT').length || 0)
const failedInstances = computed(() => status.value?.instances.filter(item => ['OUTDATED', 'INOPERABLE', 'FAILED'].includes(item.status)).length || 0)
const canDeploy = computed(() => validation.value?.can_deploy !== false)
const isBusy = computed(() => activeJob.value?.status === 'pending' || activeJob.value?.status === 'running')
const statusCardClass = computed(() => !status.value?.exists ? 'status-neutral' : failedInstances.value > 0 ? 'status-warning' : 'status-healthy')
const statusBadgeClass = computed(() => !status.value?.exists ? 'badge-neutral' : failedInstances.value > 0 ? 'badge-warning' : 'badge-success')
const statusBadgeIcon = computed(() => !status.value?.exists ? 'pi pi-minus-circle' : failedInstances.value > 0 ? 'pi pi-exclamation-triangle' : 'pi pi-check-circle')
const statusBadgeLabel = computed(() => !status.value?.exists ? 'Not Deployed' : failedInstances.value > 0 ? 'Degraded' : status.value.status || 'Active')
const jobLabel = computed(() => {
  if (!activeJob.value) return ''
  if (activeJob.value.job_type === 'multi_account_update') return 'Updating StackSet...'
  if (activeJob.value.job_type === 'multi_account_remove') return 'Removing infrastructure...'
  return cleanDeploy.value ? 'Cleaning and redeploying StackSet...' : 'Deploying StackSet...'
})

async function refresh() {
  await multiAccountStore.refresh()
}

async function loadTemplateMetadata() {
  await multiAccountStore.loadTemplateMetadata({ background: true })
}

async function toggleTemplate(name: string) {
  if (showTemplates[name]) {
    showTemplates[name] = false
    return
  }
  if (!templateContents[name]) {
    templateLoading[name] = true
    try {
      const detail = await api.getTemplate(name)
      templateContents[name] = detail.content
      templateMeta[name] = detail
    } catch {
      templateContents[name] = '# Failed to load template'
    } finally {
      templateLoading[name] = false
    }
  }
  showTemplates[name] = true
}

async function deploy(forceRecreate: boolean) {
  showCleanConfirm.value = false
  result.value = null
  cleanDeploy.value = forceRecreate
  try {
    const job = await api.deployMultiAccount(forceRecreate ? { force_recreate: true } : {})
    startPolling(job.job_id, job.job_type)
  } catch (e) {
    result.value = { success: false, message: e instanceof Error ? e.message : 'Failed to start deployment' }
  }
}

async function update() {
  result.value = null
  cleanDeploy.value = false
  try {
    const job = await api.updateMultiAccount()
    startPolling(job.job_id, job.job_type)
  } catch (e) {
    result.value = { success: false, message: e instanceof Error ? e.message : 'Failed to start update' }
  }
}

async function remove() {
  showRemoveConfirm.value = false
  result.value = null
  try {
    const job = await api.removeMultiAccount()
    startPolling(job.job_id, job.job_type)
  } catch (e) {
    result.value = { success: false, message: e instanceof Error ? e.message : 'Failed to start removal' }
  }
}

function startPolling(jobId: string, jobType: string) {
  stopPolling()
  activeJob.value = { id: jobId, job_type: jobType, status: 'pending', progress: 0 }
  pollTimer = setInterval(async () => {
    try {
      const job = await api.getJob(jobId)
      activeJob.value = job
      if (job.status === 'completed' || job.status === 'failed') {
        stopPolling()
        result.value = {
          success: job.status === 'completed',
          message: job.status === 'completed'
            ? (job.result?.message as string) || 'Operation completed successfully'
            : job.error || 'Operation failed',
        }
        activeJob.value = null
        await refresh()
      }
    } catch {
      stopPolling()
    }
  }, 1800)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  multiAccountStore.load({ background: true })
  loadTemplateMetadata()
})
onUnmounted(stopPolling)
</script>

<style scoped>
.setup-subview {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.subview-header,
.subview-title-row,
.card-title-row,
.action-row,
.template-actions,
.dialog-actions,
.result-banner,
.job-banner,
.callout {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.subview-header,
.card-title-row,
.job-banner {
  justify-content: space-between;
}

h2,
h3,
p {
  margin: 0;
}

h2 {
  font-size: 1.1rem;
  font-weight: 600;
}

h3 {
  font-size: 0.92rem;
  font-weight: 600;
}

p,
.muted,
.empty-state {
  color: var(--text-color-secondary);
  font-size: 0.84rem;
}

.subview-title-row {
  min-width: 0;
}

.section-card,
.job-banner,
.result-banner,
.callout {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
}

.callout,
.job-banner,
.result-banner {
  padding: 1rem 1.25rem;
}

.callout-warning {
  background: rgba(234, 179, 8, 0.08);
  border-color: rgba(234, 179, 8, 0.3);
  color: #facc15;
}

.callout-danger {
  background: rgba(239, 68, 68, 0.09);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.status-healthy {
  border-color: rgba(34, 197, 94, 0.28);
}

.status-warning {
  border-color: rgba(234, 179, 8, 0.3);
}

.status-neutral {
  border-color: var(--surface-border);
}

.section-card:first-of-type {
  overflow: hidden;
}

.section-card:first-of-type .card-title-row {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.metric-grid {
  display: flex;
  gap: 2rem;
  padding: 1.25rem;
}

.metric-grid div {
  display: flex;
  min-width: 140px;
  flex-direction: column;
  gap: 0.15rem;
}

.metric-grid strong {
  color: var(--text-color);
  font-size: 1.5rem;
  font-weight: 700;
}

.metric-grid span {
  color: var(--text-color-secondary);
  font-size: 0.78rem;
}

.mono {
  font-family: var(--font-mono);
  overflow-wrap: anywhere;
}

.btn,
.btn-icon {
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}

.btn {
  border: 0;
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.btn-sm {
  padding: 0.35rem 0.65rem;
  font-size: 0.78rem;
  text-decoration: none;
}

.btn-icon {
  width: 34px;
  height: 34px;
  border: 1px solid var(--surface-border);
  background: transparent;
  color: var(--text-color-secondary);
}

.btn-icon:hover:not(:disabled) {
  background: var(--surface-ground);
  color: var(--text-color);
}

.btn-icon-flat {
  margin-left: auto;
  background: transparent;
  border: 0;
}

.btn-primary {
  background: var(--primary-color);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  box-shadow: var(--glow-blue);
}

.btn-secondary {
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  color: var(--text-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--surface-card-hover);
  border-color: rgba(32, 108, 245, 0.35);
}

.btn-warning {
  background: #f59e0b;
  color: #111;
}

.btn-warning:hover:not(:disabled) {
  background: #d97706;
}

.btn-danger {
  background: var(--color-danger);
  color: #fff;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: 999px;
  padding: 0.32rem 0.75rem;
  font-size: 0.82rem;
  font-weight: 600;
}

.badge-success {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.badge-warning {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}

.badge-neutral {
  background: var(--surface-card-hover);
  color: var(--text-color-secondary);
}

.section-card {
  overflow: hidden;
}

.section-card > .card-title-row {
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid var(--surface-border);
}

.card-title-row > h3 + .muted {
  background: var(--surface-ground);
  border-radius: 999px;
  padding: 0.2rem 0.5rem;
  font-size: 0.78rem;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

th {
  background: var(--surface-ground);
  border-bottom: 1px solid var(--surface-border);
  color: var(--text-color-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  padding: 0.65rem 1rem;
  text-align: left;
  text-transform: uppercase;
}

td {
  border-bottom: 1px solid var(--surface-border);
  color: var(--text-color);
  padding: 0.6rem 1rem;
  text-align: left;
}

tbody tr:last-child td {
  border-bottom: 0;
}

tbody tr:hover {
  background: rgba(32, 108, 245, 0.05);
}

.instance-status {
  display: inline-block;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.16rem 0.5rem;
}

.template-list {
  display: flex;
  flex-direction: column;
}

.template-item {
  border-bottom: 1px solid var(--surface-border);
}

.template-item:last-child {
  border-bottom: 0;
}

.template-item > .card-title-row {
  padding: 0.85rem 1.25rem;
}

.template-item strong {
  color: var(--text-color);
  display: block;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  margin-bottom: 0.15rem;
}

.template-item p {
  font-size: 0.75rem;
  line-height: 1.4;
}

.template-content {
  margin: 0;
  max-height: 500px;
  overflow: auto;
  padding: 1rem;
  border-top: 1px solid var(--surface-border);
  background: var(--surface-card-hover);
  color: var(--text-color);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  line-height: 1.5;
  white-space: pre;
}

.empty-state {
  padding: 1.5rem;
  text-align: center;
}

.job-banner {
  background: rgba(32, 108, 245, 0.12);
  border-color: rgba(32, 108, 245, 0.25);
}

.job-banner div:first-child {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  color: #5a9aff;
}

.job-progress {
  width: 180px;
  height: 6px;
  border-radius: 999px;
  background: rgba(32, 108, 245, 0.15);
  overflow: hidden;
}

.job-progress div {
  height: 100%;
  background: var(--primary-color);
}

.result-ok {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.25);
}

.result-error {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.25);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  z-index: 1000;
}

.dialog {
  width: min(520px, calc(100vw - 2rem));
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.spin {
  animation: spin 1s linear infinite;
}

@media (max-width: 720px) {
  .subview-header,
  .card-title-row,
  .action-row,
  .job-banner,
  .template-item > .card-title-row {
    align-items: stretch;
    flex-direction: column;
  }

  .subview-title-row,
  .template-actions {
    width: 100%;
  }

  .action-row .btn,
  .subview-header .btn,
  .template-actions .btn {
    width: 100%;
  }

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 1rem;
  }

  .job-progress {
    width: 100%;
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
