<template>
  <div class="scans-view">
    <section class="scan-control">
      <div>
        <h2>Inventory Scan</h2>
        <p>Collect AWS inventory into bluearch-core for Governance Hub policy evaluation.</p>
      </div>
      <div class="scan-actions">
        <button class="chip-action" @click="useUsRegions">US regions</button>
        <button class="chip-action" @click="useAllRegions">All listed</button>
        <button class="btn btn-primary" :disabled="scanning || selectedRegions.length === 0" @click="startScan">
          <i :class="scanning ? 'pi pi-spin pi-spinner' : 'pi pi-play'"></i>
          {{ scanButtonText }}
        </button>
        <button v-if="scanning" class="btn btn-secondary" @click="cancelScan">
          <i class="pi pi-stop-circle"></i>
          Stop
        </button>
      </div>
    </section>

    <section class="region-panel">
      <button
        v-for="region in regionOptions"
        :key="region"
        class="region-chip"
        :class="{ active: selectedRegions.includes(region) }"
        @click="toggleRegion(region)"
      >
        {{ region }}
      </button>
    </section>

    <section v-if="activeJob" class="progress-card">
      <div class="progress-header">
        <div>
          <strong>{{ activeJob.progress_message || activeJob.message || 'Scan queued' }}</strong>
          <span>{{ activeJob.status }}</span>
        </div>
        <strong>{{ activeJob.progress || 0 }}%</strong>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: (activeJob.progress || 0) + '%' }"></div>
      </div>
      <div class="progress-grid">
        <div>
          <span>{{ progressResources }}</span>
          <small>Resources</small>
        </div>
        <div v-if="activeJob.progress_data?.current_service">
          <span>{{ activeJob.progress_data.current_service }}</span>
          <small>Service</small>
        </div>
        <div v-if="activeJob.progress_data?.current_region">
          <span>{{ activeJob.progress_data.current_region }}</span>
          <small>Region</small>
        </div>
        <div v-if="activeJob.progress_data?.errors_count">
          <span class="danger">{{ activeJob.progress_data.errors_count }}</span>
          <small>Errors</small>
        </div>
      </div>
    </section>

    <section class="table-card">
      <div class="table-header">
        <h2>Recent Scan Jobs</h2>
        <button class="btn btn-secondary" @click="refresh">
          <i class="pi pi-refresh"></i>
          Refresh
        </button>
      </div>
      <div v-if="jobs.loading && !jobs.jobs.length" class="empty-state">
        <i class="pi pi-spin pi-spinner"></i>
        Loading jobs...
      </div>
      <table v-else-if="jobs.jobs.length" class="data-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Message</th>
            <th>Progress</th>
            <th>Started</th>
            <th>Completed</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs.jobs" :key="job.id">
            <td><span class="status-badge" :class="'status-' + job.status">{{ job.status }}</span></td>
            <td>{{ job.message || job.error || '-' }}</td>
            <td>{{ job.progress ?? 0 }}%</td>
            <td>{{ formatDate(job.started_at || job.created_at) }}</td>
            <td>{{ formatDate(job.completed_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">No scan jobs yet.</div>
    </section>

    <section class="table-card">
      <div class="table-header">
        <h2>Scan History</h2>
        <span>{{ history.length }} completed</span>
      </div>
      <table v-if="history.length" class="data-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Resources</th>
            <th>Started</th>
            <th>Completed</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in history" :key="item.id">
            <td><span class="status-badge" :class="'status-' + item.status">{{ item.status }}</span></td>
            <td>{{ scanResources(item) }}</td>
            <td>{{ formatDate(item.started_at) }}</td>
            <td>{{ formatDate(item.completed_at) }}</td>
            <td>{{ item.error || item.error_message || item.message || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">Completed scans will appear here.</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { useJobsStore } from '@/stores/jobs'
import type { ScanHistoryItem } from '@/types/api'

const jobs = useJobsStore()
const history = ref<ScanHistoryItem[]>([])

const regionOptions = [
  'us-east-1',
  'us-east-2',
  'us-west-1',
  'us-west-2',
  'eu-west-1',
  'eu-west-2',
  'eu-central-1',
  'ap-southeast-1',
  'ap-southeast-2',
  'ap-northeast-1',
  'sa-east-1',
  'ca-central-1',
]
const defaultRegions = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']
const selectedRegions = ref<string[]>([...defaultRegions])

const activeJob = computed(() => jobs.currentScanJob)
const scanning = computed(() => ['pending', 'running', 'cancelling'].includes(activeJob.value?.status || ''))
const scanButtonText = computed(() => scanning.value ? 'Scanning...' : `Scan ${selectedRegions.value.length} regions`)
const progressResources = computed(() => {
  return activeJob.value?.progress_data?.total_resources
    ?? Number(activeJob.value?.result?.resources_found || 0)
})

function toggleRegion(region: string) {
  if (selectedRegions.value.includes(region)) {
    selectedRegions.value = selectedRegions.value.filter((item) => item !== region)
  } else {
    selectedRegions.value = [...selectedRegions.value, region]
  }
}

function useUsRegions() {
  selectedRegions.value = [...defaultRegions]
}

function useAllRegions() {
  selectedRegions.value = [...regionOptions]
}

async function startScan() {
  await jobs.startScan(selectedRegions.value)
}

async function cancelScan() {
  await jobs.cancelScan()
}

async function refresh() {
  await Promise.all([
    jobs.fetchJobs(),
    api.scanHistory().then((items) => { history.value = items }).catch(() => {}),
  ])
}

function scanResources(item: ScanHistoryItem) {
  return item.total_resources ?? item.resources_found ?? Number(item.result?.resources_found || 0)
}

function formatDate(value?: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

onMounted(refresh)
</script>

<style scoped>
.scans-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.scan-control,
.region-panel,
.progress-card,
.table-card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 1rem;
}

.scan-control,
.table-header,
.progress-header,
.scan-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

h2 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}

p,
.table-header span,
.progress-header span {
  margin: 0;
  color: var(--text-color-secondary);
  font-size: 0.84rem;
}

.scan-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.btn,
.chip-action,
.region-chip {
  border-radius: 6px;
  border: 1px solid var(--surface-border);
  cursor: pointer;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 0.8rem;
  color: #fff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary { background: var(--primary-color); border-color: var(--primary-color); }
.btn-secondary { background: var(--surface-card-hover); }

.chip-action,
.region-chip {
  padding: 0.42rem 0.65rem;
  background: var(--surface-ground);
  color: var(--text-color-secondary);
}

.chip-action:hover,
.region-chip:hover,
.region-chip.active {
  color: var(--text-color);
  border-color: rgba(32, 108, 245, 0.55);
}

.region-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.region-chip.active {
  background: rgba(32, 108, 245, 0.18);
  color: var(--accent-cyan);
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  background: var(--surface-ground);
  overflow: hidden;
  margin: 0.85rem 0;
}

.progress-fill {
  height: 100%;
  background: var(--gradient-brand-horizontal);
}

.progress-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}

.progress-grid div {
  display: grid;
  gap: 0.15rem;
  padding: 0.7rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
}

.progress-grid span {
  font-weight: 700;
}

.progress-grid small {
  color: var(--text-color-secondary);
}

.danger {
  color: #f87171;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 0.75rem;
  border-top: 1px solid var(--surface-border);
  text-align: left;
  font-size: 0.85rem;
}

.data-table th {
  color: var(--text-color-secondary);
  font-size: 0.72rem;
  text-transform: uppercase;
}

.status-badge {
  display: inline-flex;
  border-radius: 999px;
  padding: 0.24rem 0.55rem;
  background: var(--surface-ground);
  color: var(--text-color-secondary);
  font-size: 0.75rem;
}

.status-running,
.status-pending {
  background: rgba(32, 108, 245, 0.18);
  color: #5a9aff;
}

.status-completed {
  background: rgba(34, 197, 94, 0.16);
  color: #4ade80;
}

.status-failed,
.status-cancelled {
  background: rgba(239, 68, 68, 0.16);
  color: #f87171;
}

.empty-state {
  min-height: 120px;
  display: grid;
  place-items: center;
  color: var(--text-color-secondary);
}

@media (max-width: 760px) {
  .scan-control,
  .table-header,
  .progress-header {
    align-items: stretch;
    flex-direction: column;
  }

  .progress-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
