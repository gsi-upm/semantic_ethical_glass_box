import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import AppLayout from '@/app/layout/AppLayout.vue'
import ReportsView from '@/features/reports/ReportsView.vue'
import KgGraphView from '@/features/kg/KgGraphView.vue'
import InsertLogView from '@/features/logs/InsertLogView.vue'
import DeleteTtlsView from '@/features/logs/DeleteTtlsView.vue'
import QueryWorkbenchView from '@/features/query/QueryWorkbenchView.vue'
import SharedContextView from '@/features/shared-context/SharedContextView.vue'
import HealthView from '@/features/health/HealthView.vue'
import SessionView from '@/features/session/SessionView.vue'
import SystemLogsView from '@/features/system/SystemLogsView.vue'
import { useAuthModeStore } from '@/core/auth/authModeStore'
import { useSessionStore } from '@/core/auth/sessionStore'
import type { Role } from '@/core/auth/roles'

type RouteMetaWithRoles = {
  allowedRoles?: Role[]
}

const appChildrenRoutes: RouteRecordRaw[] = [
  { path: '', redirect: '/reports' },
  { path: 'reports', component: ReportsView, meta: { allowedRoles: ['auditor', 'admin'] } },
  { path: 'kg-graph', component: KgGraphView, meta: { allowedRoles: ['auditor', 'admin'] } },
  { path: 'logs/insert', component: InsertLogView, meta: { allowedRoles: ['admin'] } },
  { path: 'logs/delete', component: DeleteTtlsView, meta: { allowedRoles: ['admin'] } },
  { path: 'query', component: QueryWorkbenchView, meta: { allowedRoles: ['auditor', 'admin'] } },
  { path: 'shared-context', component: SharedContextView, meta: { allowedRoles: ['admin'] } },
  { path: 'health', component: HealthView },
  { path: 'system/logs', component: SystemLogsView, meta: { allowedRoles: ['admin'] } },
  { path: 'session', component: SessionView },
]

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', redirect: '/session' },
    {
      path: '/',
      component: AppLayout,
      children: appChildrenRoutes,
    },
    { path: '/:pathMatch(.*)*', redirect: '/reports' },
  ],
})

function routeRequiresRole(toMeta: unknown): Role[] {
  if (!toMeta || typeof toMeta !== 'object') {
    return []
  }
  const meta = toMeta as RouteMetaWithRoles
  return meta.allowedRoles ?? []
}

router.beforeEach(async (to) => {
  const authMode = useAuthModeStore()
  await authMode.ensureLoaded()

  const allowedRoles = routeRequiresRole(to.meta)
  if (allowedRoles.length === 0 || authMode.isAuthDisabled) {
    return true
  }

  const session = useSessionStore()
  if (session.hasAnyRole(allowedRoles)) {
    return true
  }

  return '/session'
})

export default router
