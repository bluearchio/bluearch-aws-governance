import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type {
  MisconfigFinding,
  MisconfigFindingGroup,
  MisconfigPolicy,
  MisconfigCatalogItem,
  MisconfigCatalogResponse,
  MisconfigDashboard,
} from '@/types/api'

export const useMisconfigStore = defineStore('misconfig', () => {
  const findings = ref<MisconfigFinding[]>([])
  const findingGroups = ref<MisconfigFindingGroup[]>([])
  const findingsTotal = ref(0)
  const findingGroupsTotal = ref(0)
  const findingsPage = ref(1)
  const findingsPageSize = ref(25)
  const policies = ref<MisconfigPolicy[]>([])
  const catalog = ref<MisconfigCatalogItem[]>([])
  const catalogMeta = ref<MisconfigCatalogResponse | null>(null)
  const dashboard = ref<MisconfigDashboard | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchFindings(filters?: Record<string, string>) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = { ...filters }
      if (params.page) {
        findingsPage.value = Number(params.page) || findingsPage.value
      } else {
        params.page = String(findingsPage.value)
      }
      if (params.page_size) {
        findingsPageSize.value = Number(params.page_size) || findingsPageSize.value
      } else {
        params.page_size = String(findingsPageSize.value)
      }
      const data = await api.misconfigFindings(params)
      findings.value = data.items
      findingsTotal.value = data.total
      findingsPage.value = data.page
      findingsPageSize.value = data.page_size
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load findings'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchFindingGroups(filters?: Record<string, string>) {
    loading.value = true
    error.value = null
    try {
      const data = await api.misconfigFindingGroups(filters)
      findingGroups.value = data.items
      findingGroupsTotal.value = data.total
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load finding groups'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchPolicies() {
    loading.value = true
    error.value = null
    try {
      policies.value = await api.misconfigPolicies()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load policies'
    } finally {
      loading.value = false
    }
  }

  async function fetchCatalog(params?: { service?: string; risk?: string; search?: string }) {
    loading.value = true
    error.value = null
    try {
      const p: Record<string, string> = {}
      if (params?.service) p.service = params.service
      if (params?.risk) p.risk_type = params.risk
      if (params?.search) p.search = params.search
      const data = await api.misconfigCatalog(p)
      catalog.value = data.items
      catalogMeta.value = data
    } catch (e) {
      catalogMeta.value = null
      error.value = e instanceof Error ? e.message : 'Failed to load catalog'
    } finally {
      loading.value = false
    }
  }

  async function fetchDashboard() {
    loading.value = true
    error.value = null
    try {
      dashboard.value = await api.misconfigDashboard()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load misconfig dashboard'
    } finally {
      loading.value = false
    }
  }

  async function createPolicy(data: { name: string; description?: string; resource_types: string[]; misconfig_ids: string[]; risk_types?: string[]; min_risk_value?: number }) {
    error.value = null
    try {
      const created = await api.createMisconfigPolicy(data)
      policies.value.push(created)
      return created
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create policy'
      throw e
    }
  }

  async function updatePolicy(id: string, data: Partial<{ name: string; description: string; enabled: boolean; resource_types: string[]; misconfig_ids: string[]; risk_types: string[]; min_risk_value: number }>) {
    error.value = null
    try {
      const updated = await api.updateMisconfigPolicy(id, data)
      const idx = policies.value.findIndex((p) => p.id === id)
      if (idx !== -1) policies.value[idx] = updated
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update policy'
      throw e
    }
  }

  async function deletePolicy(id: string) {
    error.value = null
    try {
      await api.deleteMisconfigPolicy(id)
      policies.value = policies.value.filter((p) => p.id !== id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete policy'
      throw e
    }
  }

  async function triggerScan() {
    error.value = null
    try {
      return await api.triggerMisconfigScan()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to trigger scan'
      throw e
    }
  }

  async function scanPolicy(id: string) {
    error.value = null
    try {
      return await api.scanMisconfigPolicy(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to scan policy'
      throw e
    }
  }

  async function updateFinding(id: string, status: string) {
    error.value = null
    try {
      const updated = await api.updateMisconfigFinding(id, { status })
      const idx = findings.value.findIndex((f) => f.id === id)
      if (idx !== -1) findings.value[idx] = updated
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update finding'
      throw e
    }
  }

  return {
    findings,
    findingGroups,
    findingsTotal,
    findingGroupsTotal,
    findingsPage,
    findingsPageSize,
    policies,
    catalog,
    catalogMeta,
    dashboard,
    loading,
    error,
    fetchFindings,
    fetchFindingGroups,
    fetchPolicies,
    fetchCatalog,
    fetchDashboard,
    createPolicy,
    updatePolicy,
    deletePolicy,
    triggerScan,
    scanPolicy,
    updateFinding,
  }
})
