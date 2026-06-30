<template>
  <div class="context-switcher" ref="switcherRef">
    <button class="context-trigger" @click="open = !open" :disabled="contextStore.loading">
      <i class="pi pi-building"></i>
      <span class="context-label">{{ contextStore.currentLabel }}</span>
      <i class="pi pi-chevron-down trigger-chevron"></i>
    </button>
    <div v-if="open" class="context-dropdown">
      <div class="dropdown-header">Account Context</div>
      <div class="dropdown-divider"></div>
      <button
        v-for="ctx in contextStore.all"
        :key="ctx.account_id || ctx.id || 'context'"
        class="dropdown-item"
        :class="{ current: ctx.is_current }"
        :disabled="ctx.is_current || !ctx.account_id"
        @click="ctx.account_id && handleSwitch(ctx.account_id)"
      >
        <div class="ctx-info">
          <span class="ctx-alias">{{ ctx.account_alias || ctx.account_id || 'Unknown account' }}</span>
          <span v-if="ctx.account_alias" class="ctx-id">{{ ctx.account_id }}</span>
        </div>
        <i v-if="ctx.is_current" class="pi pi-check ctx-check"></i>
      </button>
      <div v-if="contextStore.all.length === 0" class="dropdown-empty">
        No accounts registered
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useContextStore } from '@/stores/context'

const contextStore = useContextStore()
const open = ref(false)
const switcherRef = ref<HTMLElement | null>(null)

function handleSwitch(accountId: string) {
  open.value = false
  contextStore.switchTo(accountId)
}

function onClickOutside(e: MouseEvent) {
  if (switcherRef.value && !switcherRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => {
  contextStore.loadCurrent({ background: true })
  contextStore.loadAll({ background: true })
  document.addEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.context-switcher {
  position: relative;
}

.context-trigger {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-card);
  color: var(--text-color);
  cursor: pointer;
  font-size: 0.82rem;
}

.context-trigger:hover:not(:disabled) {
  background: var(--surface-card-hover);
  border-color: rgba(32, 108, 245, 0.35);
}

.context-trigger:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.context-trigger .pi-building {
  color: var(--accent-cyan);
  font-size: 0.9rem;
}

.context-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  font-weight: 600;
}

.trigger-chevron {
  color: var(--text-color-secondary);
  font-size: 0.65rem;
}

.context-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 260px;
  max-width: min(320px, calc(100vw - 2rem));
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.38);
  z-index: 100;
  overflow: hidden;
}

.dropdown-header {
  padding: 0.65rem 0.85rem;
  color: var(--text-color-secondary);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.dropdown-divider {
  height: 1px;
  background: var(--surface-border);
}

.dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  border: 0;
  background: transparent;
  color: var(--text-color);
  cursor: pointer;
  text-align: left;
}

.dropdown-item:hover:not(:disabled) {
  background: rgba(32, 108, 245, 0.1);
}

.dropdown-item:disabled {
  cursor: default;
}

.dropdown-item.current {
  background: rgba(32, 108, 245, 0.14);
}

.ctx-info {
  display: grid;
  gap: 0.1rem;
  min-width: 0;
}

.ctx-alias,
.ctx-id {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ctx-alias {
  font-size: 0.84rem;
  font-weight: 600;
}

.ctx-id {
  color: var(--text-color-secondary);
  font-family: var(--font-mono);
  font-size: 0.72rem;
}

.ctx-check {
  color: var(--color-success);
}

.dropdown-empty {
  padding: 0.85rem;
  color: var(--text-color-secondary);
  font-size: 0.8rem;
  text-align: center;
}
</style>
