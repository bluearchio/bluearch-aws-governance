import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { createCachedLoader, type CachedLoadOptions } from '@/stores/cache'
import type {
  AccountResponse,
  AccountValidationResponse,
  StackSetStatusResponse,
  TemplateMetadata,
} from '@/types/api'

interface MultiAccountOverview {
  accounts: AccountResponse[]
  status: StackSetStatusResponse
  validation: AccountValidationResponse
}

interface TemplateMetadataState {
  componentTemplateMap: Record<string, string>
  templateMeta: Record<string, TemplateMetadata>
}

export const useMultiAccountStore = defineStore('multiAccount', () => {
  const status = ref<StackSetStatusResponse | null>(null)
  const accounts = ref<AccountResponse[]>([])
  const validation = ref<AccountValidationResponse | null>(null)
  const loading = ref(false)
  const templateLoading = ref(false)
  const error = ref<string | null>(null)
  const componentTemplateMap = ref<Record<string, string>>({})
  const templateMeta = reactive<Record<string, TemplateMetadata>>({})

  const overviewLoader = createCachedLoader<MultiAccountOverview>({
    fetcher: async () => {
      const [validationResponse, statusResponse, accountResponse] = await Promise.all([
        api.validateAccount(),
        api.multiAccountStatus(),
        api.listAccounts(),
      ])
      return {
        validation: validationResponse,
        status: statusResponse,
        accounts: Array.isArray(accountResponse) ? accountResponse : [],
      }
    },
    assign: (value) => {
      validation.value = value.validation
      status.value = value.status
      accounts.value = value.accounts
    },
    hasData: () => status.value !== null || accounts.value.length > 0 || validation.value !== null,
    setLoading: (value) => { loading.value = value },
    setError: (message) => { error.value = message },
    getErrorMessage: (e) => e instanceof Error ? e.message : 'Failed to load multi-account status',
  })

  const templateLoader = createCachedLoader<TemplateMetadataState>({
    fetcher: async () => {
      const map = await api.componentTemplateMap()
      const templates = await api.listTemplates()
      const meta: Record<string, TemplateMetadata> = {}
      const templateNames = [map['cross-account'], map['management-resources']].filter(Boolean)
      for (const item of templates) {
        if (templateNames.includes(item.name)) meta[item.name] = item
      }
      return { componentTemplateMap: map, templateMeta: meta }
    },
    assign: (value) => {
      componentTemplateMap.value = value.componentTemplateMap
      Object.assign(templateMeta, value.templateMeta)
    },
    hasData: () => Object.keys(componentTemplateMap.value).length > 0,
    setLoading: (value) => { templateLoading.value = value },
    setError: () => {},
    staleMs: 5 * 60_000,
  })

  function load(options?: CachedLoadOptions) {
    return overviewLoader.load(options).catch(() => null)
  }

  function refresh() {
    return overviewLoader.refresh().catch(() => null)
  }

  function loadTemplateMetadata(options?: CachedLoadOptions) {
    return templateLoader.load(options).catch(() => null)
  }

  function refreshTemplateMetadata() {
    return templateLoader.refresh().catch(() => null)
  }

  return {
    accounts,
    componentTemplateMap,
    error,
    loading,
    status,
    templateLoading,
    templateMeta,
    validation,
    load,
    refresh,
    loadTemplateMetadata,
    refreshTemplateMetadata,
  }
})
