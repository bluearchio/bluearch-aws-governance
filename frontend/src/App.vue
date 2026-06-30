<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <svg width="28" height="28" viewBox="0 0 103 103" fill="none" aria-hidden="true">
            <circle cx="51" cy="51" r="47.5" stroke="#206CF5" stroke-width="5"/>
            <circle cx="51" cy="51" r="36" stroke="#206CF5" stroke-width="5"/>
            <path d="M32.4 68.1L51.7 29.6L71 68.1" stroke="#206CF5" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <div class="logo-copy">
            <span class="logo-text">BlueArch</span>
            <span class="logo-subtitle">Governance Hub</span>
          </div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/" class="nav-item" :class="{ active: route.path === '/' }">
          <i class="pi pi-th-large"></i>
          <span>Dashboard</span>
        </router-link>

        <div class="nav-group">
          <router-link
            to="/setup"
            class="nav-item"
            :class="{ active: isExactActive('/setup') }"
          >
            <i class="pi pi-cog"></i>
            <span>Setup</span>
          <i class="pi sub-chevron" :class="isGroupOpen('/setup') ? 'pi-chevron-down' : 'pi-chevron-right'"></i>
          </router-link>

          <div v-if="isGroupOpen('/setup')" class="sub-nav">
            <router-link to="/setup/assume-role" class="nav-item sub-item" :class="{ active: isActive('/setup/assume-role') }">
              <i class="pi pi-key"></i>
              <span>Assume Role</span>
            </router-link>
            <router-link to="/setup/multi-account" class="nav-item sub-item" :class="{ active: isActive('/setup/multi-account') }">
              <i class="pi pi-sitemap"></i>
              <span>Multi-Account</span>
            </router-link>
          </div>
        </div>

        <router-link to="/scans" class="nav-item" :class="{ active: isActive('/scans') }">
          <i class="pi pi-sync"></i>
          <span>Scans</span>
        </router-link>

        <router-link to="/misconfig" class="nav-item" :class="{ active: isActive('/misconfig') }">
          <i class="pi pi-shield"></i>
          <span>Misconfig</span>
        </router-link>

        <router-link to="/frameworks" class="nav-item" :class="{ active: isActive('/frameworks') }">
          <i class="pi pi-sitemap"></i>
          <span>Frameworks</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <a href="/docs" target="_blank" class="nav-item">
          <i class="pi pi-book"></i>
          <span>API Docs</span>
        </a>
      </div>
    </aside>

    <div class="app-main">
      <header class="topbar">
        <div class="topbar-left">
          <h1 class="page-title">{{ pageTitle }}</h1>
        </div>
        <div class="topbar-right">
          <ContextSwitcher class="topbar-context" />
          <div class="health-indicator" :class="healthClass" :title="`Status: ${healthStatus}`">
            <i class="pi pi-circle-fill"></i>
            <span>{{ healthStatus }}</span>
          </div>
        </div>
      </header>

      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import ContextSwitcher from '@/components/ContextSwitcher.vue'

const route = useRoute()
const healthStatus = ref('checking...')
const isHealthy = ref(false)

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    dashboard: 'Dashboard',
    setup: 'Setup',
    'assume-role': 'Assume Role',
    'multi-account': 'Multi-Account',
    scans: 'Scans',
    misconfig: 'Misconfiguration',
    frameworks: 'Frameworks',
  }
  return titles[route.name as string] || 'Governance Hub'
})

const healthClass = computed(() => ({
  healthy: isHealthy.value,
  unhealthy: !isHealthy.value && healthStatus.value !== 'checking...',
}))

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function isExactActive(path: string): boolean {
  return route.path === path
}

function isGroupOpen(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}

async function checkHealth() {
  try {
    const response = await api.health()
    healthStatus.value = response.status
    isHealthy.value = response.status === 'healthy'
  } catch {
    healthStatus.value = 'unreachable'
    isHealthy.value = false
  }
}

onMounted(() => {
  checkHealth()
})
</script>
