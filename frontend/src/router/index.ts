import { createRouter, createWebHistory } from 'vue-router'

const DashboardView = () => import('@/views/DashboardView.vue')
const SetupView = () => import('@/views/SetupView.vue')
const AssumeRoleView = () => import('@/views/AssumeRoleView.vue')
const MultiAccountView = () => import('@/views/MultiAccountView.vue')
const MisconfigView = () => import('@/views/MisconfigView.vue')
const FrameworksView = () => import('@/views/FrameworksView.vue')
const ScansView = () => import('@/views/ScansView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/setup/assume-role', name: 'assume-role', component: AssumeRoleView },
    { path: '/setup/multi-account', name: 'multi-account', component: MultiAccountView },
    { path: '/setup/infrastructure', redirect: '/setup' },
    { path: '/setup', name: 'setup', component: SetupView },
    { path: '/scans', name: 'scans', component: ScansView },
    { path: '/misconfig', name: 'misconfig', component: MisconfigView },
    { path: '/frameworks', name: 'frameworks', component: FrameworksView },
  ],
})

export default router
