<template>
  <div class="stack">
    <BaseCard title="Backend health" subtitle="/healthz/live and /healthz/ready endpoints.">
      <div class="actions">
        <button class="btn" :disabled="loading" @click="load">
          {{ loading ? 'Checking…' : 'Check health' }}
        </button>
        <span v-if="lastCheckedAt" class="last-checked">Last checked: {{ lastCheckedAt }}</span>
      </div>
      <StatusBanner v-if="error" tone="error" :message="error" />
    </BaseCard>

    <div class="grid two">
      <BaseCard title="Live probe">
        <div v-if="!liveHealth" class="empty-state">Not checked yet.</div>
        <div v-else class="probe-card">
          <div class="probe-row">
            <span class="label">Status</span>
            <span class="pill" :class="liveHealth.live ? 'ok' : 'down'">
              {{ liveHealth.live ? 'Healthy' : 'Down' }}
            </span>
          </div>
          <div class="probe-row">
            <span class="label">Backend API</span>
            <span class="value">{{ liveHealth.live ? 'Responding' : 'Unavailable' }}</span>
          </div>
        </div>
      </BaseCard>
      <BaseCard title="Ready probe">
        <div v-if="!readyHealth" class="empty-state">Not checked yet.</div>
        <div v-else class="probe-card">
          <div class="probe-row">
            <span class="label">Overall readiness</span>
            <span class="pill" :class="readyHealth.ready ? 'ok' : 'down'">
              {{ readyHealth.ready ? 'Ready' : 'Not ready' }}
            </span>
          </div>
          <div class="probe-row">
            <span class="label">Virtuoso</span>
            <span class="pill" :class="readyHealth.virtuoso ? 'ok' : 'down'">
              {{ readyHealth.virtuoso ? 'Connected' : 'Disconnected' }}
            </span>
          </div>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import { getLiveHealth, getReadyHealth, type ReadyResponse } from '@/core/api/segbApi'
import { normalizeApiError } from '@/core/api/error'

const loading = ref(false)
const error = ref('')
const liveHealth = ref<{ live: boolean } | null>(null)
const readyHealth = ref<ReadyResponse | null>(null)
const lastCheckedAt = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    const [live, ready] = await Promise.all([getLiveHealth(), getReadyHealth()])
    liveHealth.value = live
    readyHealth.value = ready
    lastCheckedAt.value = new Date().toLocaleString()
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.grid.two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.last-checked {
  color: var(--ink-600);
  font-size: 0.85rem;
}

.empty-state {
  border: 1px dashed var(--border);
  border-radius: 10px;
  padding: 0.8rem;
  color: var(--ink-600);
  background: #f9fdff;
}

.probe-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  background: linear-gradient(180deg, #ffffff, #f8fcff);
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.probe-row {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
}

.label {
  color: var(--ink-700);
  font-size: 0.88rem;
}

.value {
  color: var(--ink-900);
  font-weight: 600;
  font-size: 0.88rem;
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

.pill.down {
  color: #991b1b;
  background: #fee2e2;
  border-color: #fca5a5;
}

@media (max-width: 980px) {
  .grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
