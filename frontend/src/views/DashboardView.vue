<template>
  <div class="dashboard-view">
    <div v-if="scanRunning" class="scan-banner">
      <div class="scan-banner-main">
        <i class="pi pi-spin pi-spinner"></i>
        <span>{{ scanMessage }}</span>
      </div>
      <span class="scan-banner-progress">{{ scanProgress }}%</span>
      <div class="scan-track">
        <div class="scan-fill" :style="{ width: scanProgress + '%' }"></div>
      </div>
    </div>

    <div v-if="dashboard.loading && !dashboard.stats && !dashboard.resourceSummary && !dashboard.misconfig" class="empty-state">
      <i class="pi pi-spin pi-spinner"></i>
      Loading dashboard...
    </div>
    <div v-else-if="dashboard.error" class="error-state">{{ dashboard.error }}</div>

    <template v-else>
      <section class="metric-grid">
        <button class="metric-card" @click="router.push('/scans')">
          <span class="metric-icon icon-blue"><i class="pi pi-server"></i></span>
          <span class="metric-value">{{ dashboard.stats?.resources ?? dashboard.resourceSummary?.total ?? 0 }}</span>
          <span class="metric-label">Resources</span>
        </button>
        <button class="metric-card" @click="router.push('/misconfig')">
          <span class="metric-icon icon-red"><i class="pi pi-shield"></i></span>
          <span class="metric-value">{{ dashboard.misconfig?.total_open ?? 0 }}</span>
          <span class="metric-label">Open Findings</span>
        </button>
        <button class="metric-card" @click="router.push('/misconfig')">
          <span class="metric-icon icon-yellow"><i class="pi pi-list-check"></i></span>
          <span class="metric-value">{{ dashboard.stats?.recommendations ?? 0 }}</span>
          <span class="metric-label">Catalog Checks</span>
        </button>
        <button class="metric-card" @click="router.push('/setup/multi-account')">
          <span class="metric-icon icon-green"><i class="pi pi-users"></i></span>
          <span class="metric-value">{{ dashboard.stats?.accounts ?? dashboard.resourceSummary?.by_account?.length ?? 0 }}</span>
          <span class="metric-label">Accounts</span>
        </button>
      </section>

      <section class="dashboard-actions">
        <div>
          <h2>Inventory Scan</h2>
          <p>{{ lastScanSummary }}</p>
        </div>
        <div class="action-buttons">
          <button class="btn btn-secondary" @click="router.push('/scans')">
            <i class="pi pi-history"></i>
            Scan History
          </button>
          <button class="btn btn-primary" :disabled="scanRunning" @click="startDefaultScan">
            <i :class="scanRunning ? 'pi pi-spin pi-spinner' : 'pi pi-sync'"></i>
            {{ scanRunning ? 'Scanning' : 'Scan US Regions' }}
          </button>
        </div>
      </section>

      <section class="chart-grid">
        <article class="chart-card">
          <div class="card-header">
            <h2>Resources by Service</h2>
            <span>{{ dashboard.resourceSummary?.total ?? 0 }} total</span>
          </div>
          <VChart v-if="serviceChartOption" class="chart" :option="serviceChartOption" autoresize />
          <div v-else class="chart-empty">No resource data yet</div>
        </article>

        <article class="chart-card">
          <div class="card-header">
            <h2>Resources by Region</h2>
          </div>
          <VChart v-if="regionChartOption" class="chart" :option="regionChartOption" autoresize />
          <div v-else class="chart-empty">No region data yet</div>
        </article>
      </section>

      <section class="chart-grid">
        <article class="chart-card">
          <div class="card-header">
            <h2>Finding Risk</h2>
            <span>{{ totalFindings }} findings</span>
          </div>
          <div v-if="riskRows.length" class="risk-list">
            <div v-for="row in riskRows" :key="row.label" class="risk-row">
              <span class="risk-name" :style="{ color: row.color }">{{ row.label }}</span>
              <div class="risk-bar">
                <span :style="{ width: row.percent + '%', background: row.color }"></span>
              </div>
              <strong>{{ row.count }}</strong>
            </div>
          </div>
          <div v-else class="chart-empty">No open findings</div>
        </article>

        <article class="chart-card">
          <div class="card-header">
            <h2>Top Finding Services</h2>
          </div>
          <div v-if="dashboard.misconfig?.by_service?.length" class="service-list">
            <button
              v-for="item in dashboard.misconfig.by_service.slice(0, 8)"
              :key="item.service"
              class="service-row"
              @click="router.push({ path: '/misconfig', query: { service: item.service } })"
            >
              <span>{{ item.service }}</span>
              <strong>{{ item.count }}</strong>
            </button>
          </div>
          <div v-else class="chart-empty">No service findings</div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api } from '@/api/client'
import { useDashboardStore } from '@/stores/dashboard'
import { useJobsStore } from '@/stores/jobs'
import type { ScanHistoryItem } from '@/types/api'

use([CanvasRenderer, PieChart, BarChart, GridComponent, LegendComponent, TooltipComponent])

const router = useRouter()
const dashboard = useDashboardStore()
const jobs = useJobsStore()
const history = ref<ScanHistoryItem[]>([])

const defaultScanRegions = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']
const colors = ['#5a9aff', '#19d4d4', '#a855f7', '#f87171', '#4ade80', '#facc15', '#fb923c', '#ec4899']

const activeScan = computed(() => jobs.currentScanJob)
const scanRunning = computed(() => ['pending', 'running', 'cancelling'].includes(activeScan.value?.status || ''))
const scanProgress = computed(() => Math.round(activeScan.value?.progress ?? 0))
const scanMessage = computed(() => activeScan.value?.progress_message || activeScan.value?.message || 'Inventory scan running')

const totalFindings = computed(() => {
  const data = dashboard.misconfig
  if (!data) return 0
  return data.total_open + data.total_acknowledged + data.total_resolved + data.total_suppressed
})

const lastScanSummary = computed(() => {
  const item = history.value[0]
  if (!item) return 'No inventory scans have completed yet.'
  const resources = item.total_resources ?? item.resources_found ?? Number(item.result?.resources_found || 0)
  return `${resources} resources found on ${formatDate(item.started_at || item.created_at)}`
})

const serviceChartOption = computed(() => {
  const rows = dashboard.resourceSummary?.by_service?.slice(0, 10) || []
  if (!rows.length) return null
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#a0a0a0' } },
    series: [{
      type: 'pie',
      radius: ['44%', '70%'],
      center: ['50%', '45%'],
      label: { color: '#a0a0a0', fontSize: 11 },
      data: rows.map((row, index) => ({
        name: row.service_name,
        value: row.count,
        itemStyle: { color: colors[index % colors.length] },
      })),
    }],
  }
})

const regionChartOption = computed(() => {
  const rows = dashboard.resourceSummary?.by_region?.slice(0, 12) || []
  if (!rows.length) return null
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 18, top: 18, bottom: 52 },
    xAxis: {
      type: 'category',
      data: rows.map((row) => row.region),
      axisLabel: { color: '#a0a0a0', rotate: 35 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#a0a0a0' },
      splitLine: { lineStyle: { color: '#262626' } },
    },
    series: [{
      type: 'bar',
      data: rows.map((row, index) => ({
        value: row.count,
        itemStyle: { color: colors[index % colors.length], borderRadius: [4, 4, 0, 0] },
      })),
    }],
  }
})

const riskRows = computed(() => {
  const rows = dashboard.misconfig?.by_severity || []
  const max = Math.max(1, ...rows.map((row) => row.count))
  return rows.map((row) => {
    const risk = Number(row.risk_value)
    return {
      label: ({ 3: 'Critical', 2: 'High', 1: 'Medium', 0: 'Low' } as Record<number, string>)[risk] || 'Unknown',
      color: ({ 3: '#f87171', 2: '#fb923c', 1: '#facc15', 0: '#5a9aff' } as Record<number, string>)[risk] || '#a0a0a0',
      count: row.count,
      percent: (row.count / max) * 100,
    }
  })
})

async function startDefaultScan() {
  await jobs.startScan(defaultScanRegions)
}

function formatDate(value?: string) {
  if (!value) return 'unknown date'
  return new Date(value).toLocaleString()
}

onMounted(async () => {
  await Promise.all([
    dashboard.fetchAll(),
    jobs.fetchJobs(),
    api.scanHistory().then((items) => { history.value = items }).catch(() => {}),
  ])
})

watch(() => activeScan.value?.status, async (status, oldStatus) => {
  if ((status === 'completed' || status === 'failed') && oldStatus === 'running') {
    await dashboard.fetchAll()
    history.value = await api.scanHistory().catch(() => history.value)
  }
})
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.metric-grid,
.chart-grid {
  display: grid;
  gap: 1rem;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-card,
.chart-card,
.dashboard-actions,
.scan-banner {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
}

.metric-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.2rem 0.75rem;
  align-items: center;
  padding: 1rem;
  color: var(--text-color);
  text-align: left;
  cursor: pointer;
}

.metric-card:hover,
.service-row:hover {
  border-color: rgba(32, 108, 245, 0.45);
  background: var(--surface-card-hover);
}

.metric-icon {
  grid-row: span 2;
  display: grid;
  place-items: center;
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 8px;
}

.icon-blue { color: #5a9aff; background: rgba(32, 108, 245, 0.12); }
.icon-red { color: #f87171; background: rgba(239, 68, 68, 0.12); }
.icon-yellow { color: #facc15; background: rgba(234, 179, 8, 0.12); }
.icon-green { color: #4ade80; background: rgba(34, 197, 94, 0.12); }

.metric-value {
  font-size: 1.55rem;
  font-weight: 700;
}

.metric-label,
.card-header span,
.dashboard-actions p {
  color: var(--text-color-secondary);
  font-size: 0.82rem;
}

.dashboard-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
}

h2 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}

.action-buttons {
  display: flex;
  gap: 0.6rem;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 0;
  border-radius: 6px;
  padding: 0.55rem 0.8rem;
  color: #fff;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary { background: var(--primary-color); }
.btn-secondary { background: var(--surface-card-hover); border: 1px solid var(--surface-border); }

.chart-card {
  min-height: 310px;
  padding: 1rem;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.chart {
  height: 250px;
}

.chart-empty,
.empty-state,
.error-state {
  min-height: 180px;
  display: grid;
  place-items: center;
  color: var(--text-color-secondary);
}

.error-state {
  color: #f87171;
}

.risk-list,
.service-list {
  display: grid;
  gap: 0.55rem;
}

.risk-row,
.service-row {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr) 44px;
  align-items: center;
  gap: 0.75rem;
}

.risk-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--surface-ground);
  overflow: hidden;
}

.risk-bar span {
  display: block;
  height: 100%;
}

.service-row {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 0.55rem 0.65rem;
  background: transparent;
  color: var(--text-color);
  cursor: pointer;
  text-align: left;
}

.scan-banner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.65rem;
  padding: 0.85rem 1rem;
}

.scan-banner-main {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.scan-banner-main i,
.scan-banner-progress {
  color: var(--accent-cyan);
}

.scan-track {
  grid-column: 1 / -1;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-ground);
  overflow: hidden;
}

.scan-fill {
  height: 100%;
  background: var(--gradient-brand-horizontal);
}

@media (max-width: 980px) {
  .metric-grid,
  .chart-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 680px) {
  .metric-grid,
  .chart-grid,
  .dashboard-actions {
    grid-template-columns: 1fr;
  }

  .dashboard-actions {
    display: grid;
  }
}
</style>
