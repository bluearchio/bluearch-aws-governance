import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ScanJob, ScanJobResponse } from '@/types/api'

const ACTIVE_STATUSES = new Set(['pending', 'running', 'cancelling'])
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled'])

function responseId(response: ScanJobResponse): string {
  return response.id || response.job_id || ''
}

function asScanJob(response: ScanJobResponse): ScanJob {
  return {
    id: responseId(response),
    product: response.product || 'governance-hub',
    source: response.source || response.product || 'governance-hub',
    job_type: response.job_type || 'scan',
    status: response.status as ScanJob['status'],
    message: response.message || response.progress_message || 'Scan queued',
    progress: response.progress ?? 0,
    progress_message: response.progress_message,
    requested_services: response.requested_services,
    services: response.services,
    account_id: response.account_id,
    region: response.region,
    regions: response.regions,
    total_resources: response.total_resources,
    resources_written: response.resources_written,
    progress_data: response.progress_data,
    result: response.result,
    errors: response.errors,
    error: response.error,
    created_at: response.created_at || new Date().toISOString(),
    started_at: response.started_at,
    completed_at: response.completed_at,
  }
}

export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref<ScanJob[]>([])
  const activeJob = ref<ScanJob | null>(null)
  const currentScanJobId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let pollInterval: ReturnType<typeof setInterval> | null = null
  let cleanupTimeout: ReturnType<typeof setTimeout> | null = null

  const currentScanJob = computed(() => {
    if (!currentScanJobId.value) return null
    return jobs.value.find((job) => job.id === currentScanJobId.value) || activeJob.value
  })

  async function fetchJobs() {
    loading.value = true
    error.value = null
    try {
      jobs.value = await api.listScanJobs()
      const running = jobs.value.find((job) => ACTIVE_STATUSES.has(job.status))
      if (running && !currentScanJobId.value) {
        currentScanJobId.value = running.id
        activeJob.value = running
        startPolling(running.id)
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load scan jobs'
    } finally {
      loading.value = false
    }
  }

  async function startScan(regions: string[]) {
    error.value = null
    try {
      const response = await api.startScan({ regions })
      const job = asScanJob(response)
      activeJob.value = job
      currentScanJobId.value = job.id
      jobs.value = [job, ...jobs.value.filter((item) => item.id !== job.id)]
      startPolling(job.id)
      return job
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to start scan'
      throw e
    }
  }

  async function pollJob(jobId: string) {
    const job = await api.getScanJob(jobId)
    activeJob.value = job
    const index = jobs.value.findIndex((item) => item.id === jobId)
    if (index >= 0) {
      jobs.value[index] = job
    } else {
      jobs.value.unshift(job)
    }
    return job
  }

  async function cancelScan(jobId = currentScanJobId.value) {
    if (!jobId) return null
    error.value = null
    try {
      const job = await api.cancelScan(jobId)
      activeJob.value = job
      const index = jobs.value.findIndex((item) => item.id === job.id)
      if (index >= 0) jobs.value[index] = job
      return job
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to cancel scan'
      throw e
    }
  }

  function startPolling(jobId: string) {
    stopPolling()
    pollJob(jobId).catch(() => {})
    pollInterval = setInterval(async () => {
      try {
        const job = await pollJob(jobId)
        if (TERMINAL_STATUSES.has(job.status)) {
          stopPolling()
          scheduleCleanup()
        }
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  function clearCurrentJob() {
    currentScanJobId.value = null
    activeJob.value = null
  }

  function scheduleCleanup() {
    if (cleanupTimeout) clearTimeout(cleanupTimeout)
    cleanupTimeout = setTimeout(clearCurrentJob, 60000)
  }

  watch(currentScanJob, (job) => {
    if (job && TERMINAL_STATUSES.has(job.status)) {
      stopPolling()
      scheduleCleanup()
    }
  })

  return {
    jobs,
    activeJob,
    currentScanJob,
    currentScanJobId,
    loading,
    error,
    fetchJobs,
    startScan,
    pollJob,
    cancelScan,
    stopPolling,
    clearCurrentJob,
  }
})
