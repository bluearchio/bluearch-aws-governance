<template>
  <div class="setup-subview">
    <div class="subview-header">
      <div class="subview-title-row">
        <button class="btn-icon" title="Back to Setup" @click="router.push('/setup')">
          <i class="pi pi-arrow-left"></i>
        </button>
        <h2>Assume Role Configuration</h2>
      </div>
      <button class="btn btn-secondary" :disabled="loading" @click="refresh">
        <i class="pi pi-refresh" :class="{ spin: loading }"></i>
        Refresh
      </button>
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
        <span v-if="status.stack_status" class="muted">Stack: {{ status.stack_status }}</span>
      </div>
      <div class="detail-grid">
        <div>
          <span>Role ARN</span>
          <strong class="mono">{{ status.role_arn || '-' }}</strong>
        </div>
        <div>
          <span>Role Name</span>
          <strong>{{ status.role_name || '-' }}</strong>
        </div>
        <div>
          <span>Account ID</span>
          <strong class="mono">{{ status.account_id || '-' }}</strong>
        </div>
        <div>
          <span>External ID</span>
          <strong>{{ status.external_id_configured ? 'Configured' : 'Not set' }}</strong>
        </div>
      </div>
    </div>

    <div class="action-row">
      <button class="btn btn-primary" :disabled="isBusy" @click="showDeployDialog = true">
        <i class="pi pi-cloud-upload"></i>
        {{ status?.configured ? 'Re-deploy Role' : 'Deploy Role' }}
      </button>
      <button
        v-if="status?.configured && status.enabled"
        class="btn btn-warning"
        :disabled="isBusy"
        @click="disable(false)"
      >
        <i class="pi pi-power-off"></i>
        Disable
      </button>
      <button
        v-if="status?.configured || status?.stack_exists"
        class="btn btn-danger"
        :disabled="isBusy"
        @click="showDeleteConfirm = true"
      >
        <i class="pi pi-trash"></i>
        Disable &amp; Delete Stack
      </button>
    </div>

    <div v-if="configs.length" class="section-card">
      <div class="card-title-row">
        <h3>Configurations</h3>
        <span class="muted">{{ configs.length }} record{{ configs.length === 1 ? '' : 's' }}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Role</th>
              <th>Enabled</th>
              <th>Active</th>
              <th>Last Used</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="cfg in configs" :key="cfg.id">
              <td class="mono">{{ cfg.account_id }}</td>
              <td class="mono">{{ cfg.role_arn }}</td>
              <td>{{ cfg.enabled ? 'Yes' : 'No' }}</td>
              <td>{{ cfg.is_active ? 'Yes' : 'No' }}</td>
              <td>{{ formatDate(cfg.last_used_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section-card">
      <div class="card-title-row">
        <h3>CloudFormation Template</h3>
        <div class="template-actions">
          <a v-if="templateMeta?.public_url" :href="templateMeta.public_url" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
            <i class="pi pi-download"></i>
            Download
          </a>
          <button class="btn btn-secondary btn-sm" :disabled="!assumeRoleTemplate" @click="toggleTemplate">
            <i class="pi" :class="showTemplate ? 'pi-eye-slash' : 'pi-eye'"></i>
            {{ showTemplate ? 'Hide' : 'View' }}
          </button>
        </div>
      </div>
      <div v-if="templateLoading" class="empty-state"><i class="pi pi-spin pi-spinner"></i> Loading template...</div>
      <pre v-else-if="showTemplate && templateContent" class="template-content">{{ templateContent }}</pre>
      <div v-else-if="!assumeRoleTemplate" class="empty-state">Template metadata is unavailable from core.</div>
    </div>

    <div v-if="showDeployDialog" class="dialog-overlay" @click.self="showDeployDialog = false">
      <div class="dialog">
        <h3>Deploy Assume Role</h3>
        <p>Core will deploy the CloudFormation stack and persist the assume-role configuration.</p>
        <label>
          Trust Mode
          <select v-model="deployForm.trust_mode">
            <option value="CurrentUser">Current User Only</option>
            <option value="SpecificArn">Specific IAM ARN</option>
            <option value="AnyPrincipal">Any Principal in Account</option>
          </select>
        </label>
        <label v-if="deployForm.trust_mode === 'SpecificArn'">
          IAM ARN
          <input v-model="deployForm.specific_arn" placeholder="arn:aws:iam::123456789012:user/name" />
        </label>
        <label>
          External ID
          <input v-model="deployForm.external_id" placeholder="Optional" />
        </label>
        <label>
          Role Name
          <input v-model="deployForm.role_name" />
        </label>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showDeployDialog = false">Cancel</button>
          <button class="btn btn-primary" @click="deploy">Deploy</button>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="dialog-overlay" @click.self="showDeleteConfirm = false">
      <div class="dialog">
        <h3>Delete Stack &amp; Disable</h3>
        <p>This disables the core assume-role configuration and asks core to delete the CloudFormation stack.</p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" @click="showDeleteConfirm = false">Cancel</button>
          <button class="btn btn-danger" @click="disable(true)">Delete Stack</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { AssumeRoleConfigRecord, AssumeRoleStatusResponse, JobResponse, TemplateMetadata } from '@/types/api'

const router = useRouter()

const status = ref<AssumeRoleStatusResponse | null>(null)
const configs = ref<AssumeRoleConfigRecord[]>([])
const loading = ref(false)
const error = ref('')
const activeJob = ref<JobResponse | null>(null)
const result = ref<{ success: boolean; message: string } | null>(null)
const showDeployDialog = ref(false)
const showDeleteConfirm = ref(false)
const componentTemplateMap = ref<Record<string, string>>({})
const templateMeta = ref<TemplateMetadata | null>(null)
const templateContent = ref('')
const templateLoading = ref(false)
const showTemplate = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const deployForm = reactive({
  trust_mode: 'CurrentUser',
  specific_arn: '',
  external_id: '',
  role_name: 'BlueArchCLIRole',
})

const assumeRoleTemplate = computed(() => componentTemplateMap.value['assume-role'])
const isBusy = computed(() => activeJob.value?.status === 'pending' || activeJob.value?.status === 'running')
const statusCardClass = computed(() => status.value?.enabled ? 'status-healthy' : status.value?.configured ? 'status-warning' : 'status-neutral')
const statusBadgeClass = computed(() => status.value?.enabled ? 'badge-success' : status.value?.configured ? 'badge-warning' : 'badge-neutral')
const statusBadgeIcon = computed(() => status.value?.enabled ? 'pi pi-check-circle' : status.value?.configured ? 'pi pi-exclamation-triangle' : 'pi pi-minus-circle')
const statusBadgeLabel = computed(() => status.value?.enabled ? 'Active' : status.value?.configured ? 'Disabled' : 'Not Configured')
const jobLabel = computed(() => activeJob.value?.job_type === 'assume_role_disable' ? 'Disabling assume role...' : 'Deploying assume role...')

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [statusResponse, configResponse] = await Promise.all([
      api.assumeRoleStatus(),
      api.assumeRoleConfigs(),
    ])
    status.value = statusResponse
    configs.value = configResponse
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load assume-role status'
  } finally {
    loading.value = false
  }
}

async function loadTemplateMap() {
  try {
    componentTemplateMap.value = await api.componentTemplateMap()
    const list = await api.listTemplates()
    templateMeta.value = list.find(item => item.name === assumeRoleTemplate.value) || null
  } catch {
    componentTemplateMap.value = {}
  }
}

async function toggleTemplate() {
  if (showTemplate.value) {
    showTemplate.value = false
    return
  }
  const name = assumeRoleTemplate.value
  if (!name) return
  if (!templateContent.value) {
    templateLoading.value = true
    try {
      const detail = await api.getTemplate(name)
      templateContent.value = detail.content
      templateMeta.value = detail
    } catch {
      templateContent.value = '# Failed to load template'
    } finally {
      templateLoading.value = false
    }
  }
  showTemplate.value = true
}

async function deploy() {
  showDeployDialog.value = false
  result.value = null
  const payload: Record<string, string | undefined> = {
    trust_mode: deployForm.trust_mode,
    role_name: deployForm.role_name,
  }
  if (deployForm.specific_arn) payload.specific_arn = deployForm.specific_arn
  if (deployForm.external_id) payload.external_id = deployForm.external_id
  try {
    const job = await api.deployAssumeRole(payload)
    startPolling(job.job_id, job.job_type)
  } catch (e) {
    result.value = { success: false, message: e instanceof Error ? e.message : 'Failed to start deployment' }
  }
}

async function disable(deleteStack: boolean) {
  showDeleteConfirm.value = false
  result.value = null
  try {
    const response = await api.disableAssumeRole({ delete_stack: deleteStack })
    if (response.job_id) {
      startPolling(response.job_id, response.job_type || 'assume_role_disable')
    } else {
      result.value = { success: response.success ?? true, message: response.message || 'Assume role disabled' }
      await refresh()
    }
  } catch (e) {
    result.value = { success: false, message: e instanceof Error ? e.message : 'Failed to disable assume role' }
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
  }, 1500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function formatDate(iso?: string | null): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(() => {
  refresh()
  loadTemplateMap()
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
.job-banner {
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
  font-size: 0.95rem;
}

.section-card,
.job-banner,
.result-banner {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 1rem;
}

.status-healthy {
  border-color: rgba(34, 197, 94, 0.35);
}

.status-warning {
  border-color: rgba(234, 179, 8, 0.35);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.detail-grid div {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.detail-grid span,
.muted,
.empty-state {
  color: var(--text-color-secondary);
  font-size: 0.83rem;
}

.mono {
  font-family: var(--font-mono);
  overflow-wrap: anywhere;
}

.btn,
.btn-icon {
  border-radius: 6px;
  border: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
}

.btn {
  padding: 0.5rem 0.9rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.btn-sm {
  padding: 0.38rem 0.65rem;
  font-size: 0.8rem;
}

.btn-icon {
  width: 34px;
  height: 34px;
  border: 1px solid var(--surface-border);
  background: var(--surface-ground);
  color: var(--text-color-secondary);
}

.btn-icon-flat {
  margin-left: auto;
  background: transparent;
  border: 0;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-secondary {
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  color: var(--text-color);
}

.btn-warning {
  background: var(--color-warning);
  color: #111;
}

.btn-danger {
  background: var(--color-danger);
  color: white;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.badge-success {
  background: rgba(34, 197, 94, 0.16);
  color: var(--color-success);
}

.badge-warning {
  background: rgba(234, 179, 8, 0.18);
  color: var(--color-warning);
}

.badge-neutral {
  background: var(--surface-ground);
  color: var(--text-color-secondary);
}

.table-wrap {
  overflow-x: auto;
  margin-top: 0.8rem;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

th,
td {
  border-bottom: 1px solid var(--surface-border);
  padding: 0.65rem;
  text-align: left;
}

th {
  color: var(--text-color-secondary);
  font-weight: 600;
}

.template-content {
  margin: 0.85rem 0 0;
  max-height: 420px;
  overflow: auto;
  padding: 1rem;
  border-radius: 6px;
  background: var(--surface-ground);
  color: var(--text-color);
  font-size: 0.78rem;
}

.job-banner {
  background: rgba(32, 108, 245, 0.12);
}

.job-banner div:first-child {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.job-progress {
  width: 180px;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-ground);
  overflow: hidden;
}

.job-progress div {
  height: 100%;
  background: var(--accent-cyan);
}

.result-ok {
  color: var(--color-success);
  border-color: rgba(34, 197, 94, 0.3);
}

.result-error {
  color: var(--color-danger);
  border-color: rgba(239, 68, 68, 0.3);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
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
  padding: 1.25rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: var(--text-color-secondary);
  font-size: 0.82rem;
}

input,
select {
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  color: var(--text-color);
  padding: 0.55rem 0.65rem;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
