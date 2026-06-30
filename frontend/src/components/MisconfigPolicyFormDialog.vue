<template>
  <div v-if="visible" class="dialog-overlay" @click.self="cancel">
    <div class="dialog-box">
      <h3 class="dialog-title">{{ editPolicy ? 'Edit Misconfig Policy' : 'New Misconfig Policy' }}</h3>

      <form @submit.prevent="submit">
        <!-- Section 1: Basic Info -->
        <div class="form-section">
          <div class="section-header" @click="collapsedBasic = !collapsedBasic">
            <i class="pi pi-info-circle section-icon"></i>
            <span class="section-label">Basic Info</span>
            <i :class="collapsedBasic ? 'pi pi-chevron-down' : 'pi pi-chevron-up'" class="section-chevron"></i>
          </div>
          <div v-show="!collapsedBasic" class="section-body">
            <div class="form-group">
              <label>Name <span class="required">*</span></label>
              <input v-model="form.name" type="text" required placeholder="e.g. ec2-security-checks" />
            </div>
            <div class="form-group">
              <label>Description</label>
              <input v-model="form.description" type="text" placeholder="Optional description" />
            </div>
          </div>
        </div>

        <!-- Section 2: Resource Types -->
        <div class="form-section">
          <div class="section-header" @click="collapsedTypes = !collapsedTypes">
            <i class="pi pi-server section-icon"></i>
            <span class="section-label">Resource Types</span>
            <span v-if="form.resource_types.length" class="section-badge">{{ form.resource_types.length }}</span>
            <i :class="collapsedTypes ? 'pi pi-chevron-down' : 'pi pi-chevron-up'" class="section-chevron"></i>
          </div>
          <div v-show="!collapsedTypes" class="section-body">
            <div class="select-all-row">
              <button
                type="button"
                class="btn btn-sm"
                @click="allResourceTypesSelected ? deselectAllResourceTypes() : selectAllResourceTypes()"
              >
                {{ allResourceTypesSelected ? 'Deselect All' : 'Select All' }}
              </button>
            </div>
            <div class="resource-types-grid">
              <label
                v-for="rt in resourceTypeOptions"
                :key="rt.value"
                class="checkbox-item"
                :class="{ checked: form.resource_types.includes(rt.value) }"
              >
                <input
                  type="checkbox"
                  :value="rt.value"
                  :checked="form.resource_types.includes(rt.value)"
                  @change="toggleResourceType(rt.value)"
                />
                <i :class="rt.icon"></i>
                <span>{{ rt.label }}</span>
              </label>
            </div>
          </div>
        </div>

        <!-- Section 3: Misconfigurations -->
        <div class="form-section">
          <div class="section-header" @click="collapsedMisconfigs = !collapsedMisconfigs">
            <i class="pi pi-shield section-icon"></i>
            <span class="section-label">Misconfigurations</span>
            <span v-if="form.misconfig_ids.length" class="section-badge">{{ form.misconfig_ids.length }}</span>
            <i :class="collapsedMisconfigs ? 'pi pi-chevron-down' : 'pi pi-chevron-up'" class="section-chevron"></i>
          </div>
          <div v-show="!collapsedMisconfigs" class="section-body">
            <div v-if="!form.resource_types.length" class="empty-hint">
              Select resource types above to see available misconfigurations.
            </div>
            <template v-else>
              <div v-if="catalogLoading" class="loading-hint">
                <i class="pi pi-spin pi-spinner"></i> Loading catalog...
              </div>
              <template v-else>
                <!-- Bulk actions -->
                <div class="bulk-actions">
                  <button
                    type="button"
                    class="btn btn-sm"
                    :disabled="selectableEntries.length === 0"
                    @click="selectAllMisconfigs"
                  >
                    Select All Executable ({{ selectableEntries.length }})
                  </button>
                  <button type="button" class="btn btn-sm" @click="form.misconfig_ids = []">Clear</button>
                  <template v-for="rt in availableRiskTypes" :key="rt">
                    <button
                      type="button"
                      class="btn btn-sm"
                      :class="'risk-' + rt"
                      :disabled="selectableCountForRisk(rt) === 0"
                      @click="selectByRisk(rt)"
                    >
                      All {{ rt }}
                    </button>
                  </template>
                </div>

                <div v-if="catalogEntries.length" class="support-summary">
                  <span>{{ selectableEntries.length }} executable</span>
                  <span v-if="unselectableEntries.length">{{ unselectableEntries.length }} unavailable until evaluator support lands</span>
                </div>

                <!-- Min risk filter -->
                <div class="risk-filter">
                  <label>Min severity:</label>
                  <select v-model.number="form.min_risk_value">
                    <option :value="0">0 - All</option>
                    <option :value="1">1 - Low+</option>
                    <option :value="2">2 - Medium+</option>
                    <option :value="3">3 - High only</option>
                  </select>
                </div>

                <!-- Misconfig list grouped by risk -->
                <div class="misconfig-list">
                  <div v-for="(entries, riskType) in groupedEntries" :key="riskType" class="risk-group">
                    <div class="risk-group-header" :class="'risk-' + riskType">
                      {{ riskType }} ({{ selectableCount(entries) }} executable / {{ entries.length }} total)
                    </div>
                    <label
                      v-for="entry in entries"
                      :key="entry.id"
                      class="misconfig-item"
                      :class="{ checked: form.misconfig_ids.includes(entry.id), unsupported: !isEntrySelectable(entry) }"
                      :title="entry.support_reason || undefined"
                    >
                      <input
                        type="checkbox"
                        :checked="form.misconfig_ids.includes(entry.id)"
                        :disabled="!isEntrySelectable(entry)"
                        @change="toggleMisconfig(entry)"
                      />
                      <span class="misconfig-severity" :class="'sev-' + (entry.risk_value ?? 0)">{{ entry.risk_value ?? 0 }}/3</span>
                      <span class="misconfig-svc">{{ entry.service_name }}</span>
                      <span class="misconfig-scenario">{{ entry.scenario }}</span>
                      <span v-if="!isEntrySelectable(entry)" class="support-badge">
                        {{ supportLabel(entry) }}
                      </span>
                    </label>
                  </div>
                </div>
              </template>
            </template>
          </div>
        </div>

        <!-- Section 4: Live Preview of Affected Resources -->
        <div class="form-section" v-if="form.misconfig_ids.length > 0">
          <div class="section-header" @click="collapsedPreview = !collapsedPreview">
            <i class="pi pi-eye section-icon"></i>
            <span class="section-label">Affected Resources Preview</span>
            <span v-if="previewTotal > 0" class="section-badge" style="background: rgba(239,68,68,0.15); color: #f87171">{{ previewTotal }}</span>
            <i :class="collapsedPreview ? 'pi pi-chevron-down' : 'pi pi-chevron-up'" class="section-chevron"></i>
          </div>
          <div v-show="!collapsedPreview" class="section-body">
            <div v-if="previewLoading" class="loading-hint">
              <i class="pi pi-spin pi-spinner"></i> Evaluating resources...
            </div>
            <div v-else-if="previewResources.length === 0" class="empty-hint">
              No resources in the database match the selected rules.
            </div>
            <template v-else>
              <div class="preview-summary">
                <span class="preview-count">{{ previewTotal }} resources affected</span>
                <span class="preview-detail" v-if="previewConfirmed > 0">
                  (<span style="color: #4ade80">{{ previewConfirmed }} confirmed</span>,
                  <span style="color: #facc15">{{ previewTotal - previewConfirmed }} advisory</span>)
                </span>
              </div>
              <div class="preview-list">
                <div v-for="r in previewResources" :key="r.resource_arn" class="preview-item">
                  <div class="preview-item-header">
                    <span class="preview-svc">{{ r.service_name }}</span>
                    <span class="preview-arn">{{ r.resource_arn.split(':').pop() }}</span>
                    <span class="preview-findings">
                      <span v-if="r.confirmed" class="preview-tier confirmed">{{ r.confirmed }} confirmed</span>
                      <span v-if="r.advisory" class="preview-tier advisory">{{ r.advisory }} advisory</span>
                    </span>
                  </div>
                  <div v-if="r.scenarios.length" class="preview-scenarios">
                    <span v-for="(s, i) in r.scenarios" :key="i" class="preview-scenario">{{ s }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Actions -->
        <div class="dialog-actions">
          <button type="button" class="btn" @click="cancel">Cancel</button>
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="!isValid || submitting"
          >
            <i v-if="submitting" class="pi pi-spin pi-spinner"></i>
            {{ editPolicy ? 'Update' : 'Create' }} Policy
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'
import type { MisconfigPolicy, MisconfigCatalogItem } from '@/types/api'

const props = defineProps<{
  visible: boolean
  editPolicy?: MisconfigPolicy | null
}>()

const emit = defineEmits<{
  close: []
  saved: [MisconfigPolicy]
}>()

const collapsedBasic = ref(false)
const collapsedTypes = ref(false)
const collapsedMisconfigs = ref(false)
const submitting = ref(false)
const catalogLoading = ref(false)
const catalogEntries = ref<MisconfigCatalogItem[]>([])
const collapsedPreview = ref(false)
const previewLoading = ref(false)
const previewResources = ref<{ resource_arn: string; resource_type: string; service_name: string; findings_count: number; confirmed: number; advisory: number; scenarios: string[] }[]>([])
const previewTotal = ref(0)
const previewConfirmed = computed(() => previewResources.value.reduce((sum, r) => sum + r.confirmed, 0))

const form = ref({
  name: '',
  description: '',
  resource_types: [] as string[],
  misconfig_ids: [] as string[],
  min_risk_value: 0,
  enabled: true,
})

const resourceTypeOptions = [
  { value: 'ec2_instance', label: 'EC2 Instance', icon: 'pi pi-desktop' },
  { value: 'ec2_volume', label: 'EBS Volume', icon: 'pi pi-database' },
  { value: 'ec2_snapshot', label: 'EC2 Snapshot', icon: 'pi pi-camera' },
  { value: 'ec2_ami', label: 'EC2 AMI', icon: 'pi pi-image' },
  { value: 'ec2_eip', label: 'Elastic IP', icon: 'pi pi-globe' },
  { value: 's3_bucket', label: 'S3 Bucket', icon: 'pi pi-inbox' },
  { value: 'lambda_function', label: 'Lambda Function', icon: 'pi pi-bolt' },
  { value: 'lambda_layer', label: 'Lambda Layer', icon: 'pi pi-clone' },
  { value: 'rds_instance', label: 'RDS Instance', icon: 'pi pi-database' },
  { value: 'rds_cluster', label: 'RDS Cluster', icon: 'pi pi-sitemap' },
  { value: 'rds_snapshot', label: 'RDS Snapshot', icon: 'pi pi-camera' },
  { value: 'dynamodb_table', label: 'DynamoDB Table', icon: 'pi pi-table' },
  { value: 'elasticache_cluster', label: 'ElastiCache', icon: 'pi pi-bolt' },
  { value: 'ecs_cluster', label: 'ECS Cluster', icon: 'pi pi-th-large' },
  { value: 'ecs_service', label: 'ECS Service', icon: 'pi pi-cog' },
  { value: 'ecs_task_definition', label: 'ECS Task Def', icon: 'pi pi-file' },
  { value: 'eks_cluster', label: 'EKS Cluster', icon: 'pi pi-th-large' },
  { value: 'elb_load_balancer', label: 'Load Balancer', icon: 'pi pi-arrows-h' },
  { value: 'sns_topic', label: 'SNS Topic', icon: 'pi pi-bell' },
  { value: 'sqs_queue', label: 'SQS Queue', icon: 'pi pi-list' },
  { value: 'cloudwatch_alarm', label: 'CW Alarm', icon: 'pi pi-exclamation-triangle' },
  { value: 'cloudwatch_log_group', label: 'CW Log Group', icon: 'pi pi-file' },
]

const allResourceTypesSelected = computed(() => {
  return form.value.resource_types.length === resourceTypeOptions.length
})

function selectAllResourceTypes() {
  form.value.resource_types = resourceTypeOptions.map(rt => rt.value)
}

function deselectAllResourceTypes() {
  form.value.resource_types = []
}

/** Parse the risk_detail string (e.g. "security, operations") into an array of risk types */
function parseRiskTypes(item: MisconfigCatalogItem): string[] {
  if (!item.risk_detail) return ['other']
  return item.risk_detail.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
}

// Reset form when dialog opens
watch(() => props.visible, (v) => {
  if (v) {
    if (props.editPolicy) {
      form.value = {
        name: props.editPolicy.name,
        description: props.editPolicy.description || '',
        resource_types: [...(props.editPolicy.resource_types || [])],
        misconfig_ids: [...(props.editPolicy.misconfig_ids || [])],
        min_risk_value: props.editPolicy.min_risk_value || 0,
        enabled: props.editPolicy.enabled,
      }
    } else {
      form.value = {
        name: '',
        description: '',
        resource_types: [],
        misconfig_ids: [],
        min_risk_value: 0,
        enabled: true,
      }
    }
  }
})

const filteredEntries = computed(() => catalogEntries.value)
const selectableEntries = computed(() => filteredEntries.value.filter(isEntrySelectable))
const unselectableEntries = computed(() => filteredEntries.value.filter((entry) => !isEntrySelectable(entry)))

const availableRiskTypes = computed(() => {
  const types = new Set<string>()
  for (const e of filteredEntries.value) {
    for (const rt of parseRiskTypes(e)) types.add(rt)
  }
  return Array.from(types).sort()
})

const groupedEntries = computed(() => {
  const groups: Record<string, MisconfigCatalogItem[]> = {}
  for (const entry of filteredEntries.value) {
    const primary = parseRiskTypes(entry)[0] || 'other'
    if (!groups[primary]) groups[primary] = []
    groups[primary].push(entry)
  }
  return groups
})

const isValid = computed(() => {
  return form.value.name.trim() &&
    form.value.resource_types.length > 0 &&
    form.value.misconfig_ids.length > 0
})

function isEntrySelectable(entry: MisconfigCatalogItem): boolean {
  return entry.selectable === true || entry.supported === true || entry.support_level === 'executable'
}

function supportLabel(entry: MisconfigCatalogItem): string {
  if (entry.support_level === 'mapped') return 'needs evaluator'
  if (entry.support_level === 'unsupported') return 'not collected'
  return 'not executable'
}

function selectableCount(entries: MisconfigCatalogItem[] = filteredEntries.value): number {
  return entries.filter(isEntrySelectable).length
}

function selectableCountForRisk(riskType: string): number {
  return filteredEntries.value.filter((entry) => (
    isEntrySelectable(entry) && parseRiskTypes(entry).includes(riskType)
  )).length
}

function pruneUnavailableSelections() {
  const selectableIds = new Set(selectableEntries.value.map((entry) => entry.id))
  form.value.misconfig_ids = form.value.misconfig_ids.filter((id) => selectableIds.has(id))
}

function toggleResourceType(value: string) {
  const idx = form.value.resource_types.indexOf(value)
  if (idx >= 0) {
    form.value.resource_types.splice(idx, 1)
  } else {
    form.value.resource_types.push(value)
  }
}

function toggleMisconfig(entry: MisconfigCatalogItem) {
  if (!isEntrySelectable(entry)) return
  const id = entry.id
  const idx = form.value.misconfig_ids.indexOf(id)
  if (idx >= 0) {
    form.value.misconfig_ids.splice(idx, 1)
  } else {
    form.value.misconfig_ids.push(id)
  }
}

function selectAllMisconfigs() {
  form.value.misconfig_ids = selectableEntries.value.map(e => e.id)
}

function selectByRisk(riskType: string) {
  const ids = filteredEntries.value
    .filter(e => isEntrySelectable(e) && parseRiskTypes(e).includes(riskType))
    .map(e => e.id)
  const current = new Set(form.value.misconfig_ids)
  for (const id of ids) current.add(id)
  form.value.misconfig_ids = Array.from(current)
}

async function loadCatalogForResourceTypes(types: string[]) {
  if (types.length === 0) {
    catalogEntries.value = []
    form.value.misconfig_ids = []
    return
  }

  catalogLoading.value = true
  try {
    const data = await api.misconfigCatalog({ resource_types: types.join(','), limit: '500' })
    catalogEntries.value = data.items
    pruneUnavailableSelections()
  } catch {
    catalogEntries.value = []
    form.value.misconfig_ids = []
  } finally {
    catalogLoading.value = false
  }
}

// Watch resource types to load catalog
watch(() => form.value.resource_types, async (types) => {
  await loadCatalogForResourceTypes(types)
}, { deep: true })

// Watch misconfig_ids to auto-preview affected resources
watch(() => form.value.misconfig_ids, async (ids) => {
  if (ids.length === 0 || form.value.resource_types.length === 0) {
    previewResources.value = []
    previewTotal.value = 0
    return
  }
  previewLoading.value = true
  try {
    const data = await api.previewMisconfig({
      resource_types: form.value.resource_types,
      misconfig_ids: ids,
      min_risk_value: form.value.min_risk_value,
    })
    previewResources.value = data.resources
    previewTotal.value = data.total
  } catch {
    previewResources.value = []
    previewTotal.value = 0
  } finally {
    previewLoading.value = false
  }
}, { deep: true })

function cancel() {
  emit('close')
}

async function submit() {
  if (!isValid.value || submitting.value) return
  submitting.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
      resource_types: form.value.resource_types,
      misconfig_ids: form.value.misconfig_ids,
      risk_types: availableRiskTypes.value,
      min_risk_value: form.value.min_risk_value,
      enabled: form.value.enabled,
    }

    let result: MisconfigPolicy
    if (props.editPolicy) {
      result = await api.updateMisconfigPolicy(props.editPolicy.id, payload)
    } else {
      result = await api.createMisconfigPolicy(payload)
    }
    emit('saved', result)
    emit('close')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 5vh;
  z-index: 200;
  overflow-y: auto;
}

.dialog-box {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 12px;
  width: 720px;
  max-width: 95vw;
  max-height: 85vh;
  overflow-y: auto;
  padding: 1.5rem;
}

.dialog-title {
  margin: 0 0 1.25rem;
  font-size: 1.1rem;
  color: var(--text-color);
}

.form-section {
  margin-bottom: 1rem;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  user-select: none;
}

.section-icon { color: var(--primary-color); font-size: 0.9rem; }
.section-label { font-weight: 500; font-size: 0.875rem; color: var(--text-color); }
.section-chevron { margin-left: auto; font-size: 0.7rem; opacity: 0.5; }
.section-badge {
  background: var(--primary-color);
  color: #fff;
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 10px;
}

.section-body { padding: 0.85rem; }

.form-group {
  margin-bottom: 0.75rem;
}

.form-group label {
  display: block;
  font-size: 0.8rem;
  color: var(--text-color-secondary);
  margin-bottom: 0.3rem;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 0.5rem 0.65rem;
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  color: var(--text-color);
  font-size: 0.85rem;
}

.required { color: var(--color-danger); }

.select-all-row {
  margin-bottom: 0.5rem;
}

.resource-types-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 4px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  color: var(--text-color-secondary);
  transition: background 0.15s;
}

.checkbox-item:hover { background: rgba(255, 255, 255, 0.04); }
.checkbox-item.checked { background: rgba(32, 108, 245, 0.1); color: var(--text-color); }
.checkbox-item input { display: none; }
.checkbox-item i { font-size: 0.85rem; width: 16px; text-align: center; }

.empty-hint, .loading-hint {
  text-align: center;
  padding: 1.5rem;
  color: var(--text-color-secondary);
  font-size: 0.85rem;
}

.bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 0.75rem;
}

.support-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-color-secondary);
}

.support-summary span:first-child {
  color: #4ade80;
}

.risk-filter {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-color-secondary);
}

.risk-filter select {
  padding: 0.3rem 0.5rem;
  background: var(--surface-ground);
  border: 1px solid var(--surface-border);
  border-radius: 4px;
  color: var(--text-color);
  font-size: 0.8rem;
}

.misconfig-list {
  max-height: 300px;
  overflow-y: auto;
}

.risk-group-header {
  position: sticky;
  top: 0;
  padding: 0.35rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--surface-card);
  z-index: 1;
}

.risk-security { color: var(--color-danger); }
.risk-cost { color: var(--color-warning); }
.risk-operations { color: var(--primary-color); }
.risk-performance { color: #a855f7; }
.risk-reliability { color: var(--accent-cyan); }

.misconfig-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.5rem;
  font-size: 0.8rem;
  cursor: pointer;
  border-radius: 4px;
  color: var(--text-color-secondary);
}

.misconfig-item:hover { background: rgba(255, 255, 255, 0.03); }
.misconfig-item.checked { background: rgba(32, 108, 245, 0.08); color: var(--text-color); }
.misconfig-item.unsupported {
  cursor: not-allowed;
  opacity: 0.42;
  filter: saturate(0.75);
}
.misconfig-item.unsupported:hover { background: transparent; }
.misconfig-item input { display: none; }

.misconfig-severity {
  font-size: 0.7rem;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  min-width: 28px;
  text-align: center;
  font-weight: 600;
}

.sev-3 { background: rgba(239, 68, 68, 0.2); color: var(--color-danger); }
.sev-2 { background: rgba(234, 179, 8, 0.2); color: var(--color-warning); }
.sev-1 { background: rgba(32, 108, 245, 0.2); color: var(--primary-color); }
.sev-0 { background: rgba(255, 255, 255, 0.05); color: var(--text-color-secondary); }

.misconfig-svc {
  font-size: 0.7rem;
  color: var(--accent-cyan);
  min-width: 50px;
}

.misconfig-scenario {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.support-badge {
  flex-shrink: 0;
  border: 1px solid var(--surface-border);
  border-radius: 999px;
  padding: 0.08rem 0.35rem;
  color: var(--text-color-secondary);
  font-size: 0.65rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--surface-border);
}

.btn {
  padding: 0.5rem 1rem;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-color-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.btn:hover { background: rgba(255, 255, 255, 0.05); color: var(--text-color); }
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.btn:disabled:hover {
  background: transparent;
  color: var(--text-color-secondary);
}

.btn-primary {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
}

.btn-primary:hover { background: #1a5cd4; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

/* Preview section */
.preview-summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.82rem;
}
.preview-count { font-weight: 600; color: var(--color-danger); }
.preview-detail { color: var(--text-color-secondary); font-size: 0.78rem; }

.preview-list {
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid var(--surface-border);
  border-radius: 6px;
}

.preview-item {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--surface-border);
}
.preview-item:last-child { border-bottom: none; }
.preview-item:hover { background: rgba(32, 108, 245, 0.05); }

.preview-item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.78rem;
}
.preview-svc {
  background: rgba(32, 108, 245, 0.15);
  color: #5a9aff;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 500;
}
.preview-arn {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-color-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
.preview-findings { display: flex; gap: 0.35rem; flex-shrink: 0; }
.preview-tier {
  font-size: 0.65rem;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-weight: 600;
}
.preview-tier.confirmed { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.preview-tier.advisory { background: rgba(234, 179, 8, 0.15); color: #facc15; }

.preview-scenarios {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.35rem;
  padding-left: 2rem;
}
.preview-scenario {
  font-size: 0.68rem;
  color: var(--text-color-secondary);
  padding: 0.1rem 0.3rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 3px;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
