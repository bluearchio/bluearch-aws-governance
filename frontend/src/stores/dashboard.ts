import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { HealthResponse, MisconfigDashboard, ResourceSummary, SystemStats } from '@/types/api'

export const useDashboardStore = defineStore('dashboard', () => {
  const stats = ref<SystemStats | null>(null)
  const health = ref<HealthResponse | null>(null)
  const resourceSummary = ref<ResourceSummary | null>(null)
  const misconfig = ref<MisconfigDashboard | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAll() {
    loading.value = true
    error.value = null
    const failures: string[] = []
    await Promise.allSettled([
      api.stats()
        .then((data) => { stats.value = data })
        .catch((e) => { failures.push(e instanceof Error ? e.message : 'Failed to load stats') }),
      api.health()
        .then((data) => { health.value = data })
        .catch((e) => { failures.push(e instanceof Error ? e.message : 'Failed to load health') }),
      api.resourceSummary()
        .then((data) => {
          resourceSummary.value = data
          stats.value = {
            resources: data.total,
            recommendations: stats.value?.recommendations ?? 0,
            accounts: stats.value?.accounts ?? data.by_account.length,
          }
        })
        .catch((e) => { failures.push(e instanceof Error ? e.message : 'Failed to load resource summary') }),
      api.misconfigDashboard()
        .then((data) => { misconfig.value = data })
        .catch((e) => { failures.push(e instanceof Error ? e.message : 'Failed to load misconfig dashboard') }),
    ])
    if (failures.length && !stats.value && !resourceSummary.value && !misconfig.value) {
      error.value = failures[0]
    }
    loading.value = false
  }

  return {
    stats,
    health,
    resourceSummary,
    misconfig,
    loading,
    error,
    fetchAll,
  }
})
