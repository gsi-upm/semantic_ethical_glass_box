<template>
  <aside class="sidebar">
    <template v-for="section in visibleSections" :key="section.title">
      <p class="section">{{ section.title }}</p>
      <RouterLink v-for="item in section.items" :key="item.to" class="nav-link" :to="item.to">{{ item.label }}</RouterLink>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { useAuthModeStore } from '@/core/auth/authModeStore'
import { useSessionStore } from '@/core/auth/sessionStore'
import type { Role } from '@/core/auth/roles'

type NavigationItem = {
  to: string
  label: string
  allowedRoles?: Role[]
}

type NavigationSection = {
  title: string
  items: NavigationItem[]
}

const sections: NavigationSection[] = [
  {
    title: 'Analytics',
    items: [
      { to: '/reports', label: 'Reports Dashboard', allowedRoles: ['auditor', 'admin'] },
      { to: '/kg-graph', label: 'KG Visual Explorer', allowedRoles: ['auditor', 'admin'] },
    ],
  },
  {
    title: 'Operations',
    items: [
      { to: '/logs/insert', label: 'Insert TTL', allowedRoles: ['admin'] },
      { to: '/logs/delete', label: 'Delete TTLs', allowedRoles: ['admin'] },
      { to: '/query', label: 'SPARQL Workbench', allowedRoles: ['auditor', 'admin'] },
    ],
  },
  {
    title: 'Shared Context',
    items: [{ to: '/shared-context', label: 'Resolver Console', allowedRoles: ['admin'] }],
  },
  {
    title: 'System',
    items: [
      { to: '/health', label: 'Health' },
      { to: '/system/logs', label: 'Server Logs', allowedRoles: ['admin'] },
      { to: '/session', label: 'Session' },
    ],
  },
]

const authMode = useAuthModeStore()
const session = useSessionStore()

onMounted(() => {
  void authMode.ensureLoaded()
})

function canView(allowedRoles?: Role[]): boolean {
  if (!allowedRoles || allowedRoles.length === 0) {
    return true
  }
  if (authMode.isAuthDisabled) {
    return true
  }
  return session.hasAnyRole(allowedRoles)
}

const visibleSections = computed<NavigationSection[]>(() => {
  return sections
    .map((section) => ({
      title: section.title,
      items: section.items.filter((item) => canView(item.allowedRoles)),
    }))
    .filter((section) => section.items.length > 0)
})
</script>

<style scoped>
.sidebar {
  position: sticky;
  top: 0;
  align-self: start;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.section {
  margin: 0.75rem 0 0.2rem;
  color: var(--ink-500);
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.nav-link {
  text-decoration: none;
  color: var(--ink-800);
  font-weight: 540;
  font-size: 0.92rem;
  border-radius: 10px;
  padding: 0.48rem 0.56rem;
}

.nav-link:hover {
  background: var(--surface-alt);
}

.nav-link.router-link-active {
  color: #005d91;
  background: #dff3fc;
}
</style>
