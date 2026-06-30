import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import { createCachedLoader, type CachedLoadOptions } from '@/stores/cache'

interface FeatureStatus {
  available: boolean
  partial?: boolean
  reason?: string
}

interface PermissionStatusResponse {
  tier: string
  features: Record<string, FeatureStatus>
  account_id?: string
  checked_at?: string
  upgrade_path?: {
    next_tier: string
    action: string
    unlocks: string[]
  }
}

export const usePermissionStore = defineStore('permissions', () => {
  const status = ref<PermissionStatusResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const tier = computed(() => String(status.value?.tier || 'unknown').toLowerCase())

  function canUse(feature: string): boolean {
    if (!status.value) return true // optimistic until loaded
    const f = status.value.features[feature]
    return f ? f.available : true
  }

  function featureStatus(feature: string): FeatureStatus | null {
    if (!status.value) return null
    return status.value.features[feature] || null
  }

  function isPartial(feature: string): boolean {
    if (!status.value) return false
    const f = status.value.features[feature]
    return f ? (f.partial || false) : false
  }

  // Map nav route names to feature keys for badge display
  const navFeatureMap: Record<string, string> = {
    resources: 'scan',
    recommendations: 'recommendations',
    misconfig: 'misconfig',
    scans: 'scan',
    setup: 'setup',
  }

  function navHasWarning(routeName: string): boolean {
    const feature = navFeatureMap[routeName]
    if (!feature || !status.value) return false
    const f = status.value.features[feature]
    if (!f) return false
    return !f.available || (f.partial || false)
  }

  const loader = createCachedLoader<PermissionStatusResponse>({
    fetcher: api.permissions,
    assign: (value) => { status.value = value },
    hasData: () => status.value !== null,
    setLoading: (value) => { loading.value = value },
    setError: (message) => { error.value = message },
    getErrorMessage: (e) => e instanceof Error ? e.message : 'Failed to load permissions',
  })

  async function load(options?: CachedLoadOptions) {
    await loader.load(options).catch(setUnavailable)
  }

  async function refresh() {
    loading.value = true
    error.value = null
    try {
      status.value = await api.refreshPermissions()
    } catch (e) {
      setUnavailable(e)
    } finally {
      loading.value = false
    }
  }

  function setUnavailable(e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load permissions'
    if (!status.value) {
      status.value = { tier: 'unknown', features: {} }
    }
  }

  return { status, loading, error, tier, canUse, featureStatus, isPartial, navHasWarning, load, refresh }
})
