<template>
  <div class="stack">
    <BaseCard title="Session token">
      <label class="field">
        <span>JWT token</span>
        <textarea
          v-model="tokenDraft"
          rows="6"
          class="text-area"
          placeholder="eyJhbGciOi..."
        />
      </label>

      <div class="actions">
        <button class="btn" @click="save">Save token</button>
        <button class="btn ghost" @click="clear">Clear token</button>
      </div>

      <StatusBanner v-if="message" tone="success" :message="message" />
    </BaseCard>

    <BaseCard title="Session summary">
      <div class="summary-card">
        <div class="row">
          <span class="label">Authentication</span>
          <span class="pill" :class="session.isAuthenticated ? 'ok' : 'off'">
            {{ session.isAuthenticated ? 'Authenticated' : 'No token' }}
          </span>
        </div>
        <div class="row">
          <span class="label">Token status</span>
          <span class="pill" :class="tokenStateClass">{{ tokenStateLabel }}</span>
        </div>
        <div class="row">
          <span class="label">Username</span>
          <span class="value">{{ decodedToken?.username ?? '-' }}</span>
        </div>
        <div class="row">
          <span class="label">Name</span>
          <span class="value">{{ decodedToken?.name ?? '-' }}</span>
        </div>
        <div class="row">
          <span class="label">Expires at</span>
          <span class="value">{{ expiresAt }}</span>
        </div>
        <div class="row top">
          <span class="label">Roles</span>
          <div class="roles">
            <span v-for="role in decodedRoles" :key="role" class="role-chip">{{ role }}</span>
            <span v-if="decodedRoles.length === 0" class="value">-</span>
          </div>
        </div>
      </div>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import { useSessionStore } from '@/core/auth/sessionStore'

const session = useSessionStore()
const tokenDraft = ref(session.token)
const message = ref('')
const decodedToken = computed(() => session.decodedToken)

const decodedRoles = computed(() => decodedToken.value?.roles ?? [])

const expiresAt = computed(() => {
  const exp = decodedToken.value?.exp
  if (!exp) {
    return '-'
  }
  return new Date(exp * 1000).toLocaleString()
})

const tokenStateLabel = computed(() => {
  if (!session.isAuthenticated) {
    return 'No token'
  }
  return session.isExpired ? 'Expired' : 'Active'
})

const tokenStateClass = computed(() => {
  if (!session.isAuthenticated) {
    return 'off'
  }
  return session.isExpired ? 'warn' : 'ok'
})

function save(): void {
  session.setToken(tokenDraft.value)
  message.value = 'Token saved in session storage.'
}

function clear(): void {
  session.clearToken()
  tokenDraft.value = ''
  message.value = 'Token removed from session storage.'
}
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
  color: var(--ink-700);
}

.text-area {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.65rem 0.7rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 0.84rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.summary-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  background: linear-gradient(180deg, #ffffff, #f8fcff);
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.row.top {
  align-items: flex-start;
}

.label {
  color: var(--ink-700);
  font-size: 0.88rem;
}

.value {
  color: var(--ink-900);
  font-size: 0.88rem;
  font-weight: 600;
}

.roles {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.role-chip {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.12rem 0.5rem;
  background: #ffffff;
  color: var(--ink-800);
  font-size: 0.76rem;
  font-weight: 700;
}

.pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  font-size: 0.76rem;
  font-weight: 700;
  border: 1px solid transparent;
  letter-spacing: 0.02em;
}

.pill.ok {
  color: #166534;
  background: #dcfce7;
  border-color: #86efac;
}

.pill.warn {
  color: #a16207;
  background: #fef9c3;
  border-color: #fde047;
}

.pill.off {
  color: var(--ink-600);
  background: #f8fafc;
  border-color: var(--border-muted);
}
</style>
