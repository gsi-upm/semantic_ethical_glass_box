<template>
  <div class="stack">
    <BaseCard
      title="Backend Server Logs"
      subtitle="Admin-only view of backend operational logs exposed by /logs/server."
    >
      <div class="filters">
        <label class="field compact">
          <span>Rows</span>
          <input
            v-model.number="limit"
            type="number"
            class="text-input"
            min="1"
            max="2000"
          />
        </label>

        <label class="field compact">
          <span>Level</span>
          <select v-model="level" class="text-input">
            <option value="">All</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </label>

        <label class="field grow">
          <span>Contains</span>
          <input
            v-model="contains"
            class="text-input"
            placeholder="search text"
            @keyup.enter="load"
          />
        </label>
      </div>

      <div class="actions">
        <button class="btn" :disabled="loading" @click="load">
          {{ loading ? 'Loading…' : 'Refresh logs' }}
        </button>
        <button class="btn ghost" :disabled="loading" @click="clearFilters">Clear filters</button>
      </div>

      <StatusBanner v-if="statusMessage" tone="success" :message="statusMessage" />
      <StatusBanner v-if="error" tone="error" :message="error" />
    </BaseCard>

    <BaseCard title="Log Entries">
      <pre v-if="entries.length === 0" class="raw">No log entries for current filters.</pre>

      <div v-else class="table-wrap">
        <table class="entries-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Level</th>
              <th>Actor</th>
              <th>IP</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entry, index) in entries" :key="`${entry.raw}-${index}`">
              <td>{{ entry.timestamp ?? '-' }}</td>
              <td>
                <span class="badge" :data-level="entry.level ?? 'NONE'">{{ entry.level ?? '-' }}</span>
              </td>
              <td>{{ entry.actor ?? '-' }}</td>
              <td>{{ entry.origin_ip ?? '-' }}</td>
              <td class="message">{{ entry.message }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import { normalizeApiError } from '@/core/api/error'
import { getServerLogs, type ServerLogEntry } from '@/core/api/segbApi'

const loading = ref(false)
const error = ref('')
const statusMessage = ref('')
const limit = ref(200)
const level = ref('')
const contains = ref('')
const entries = ref<ServerLogEntry[]>([])

function normalizeLimit(): number {
  const value = Number.isFinite(limit.value) ? Math.trunc(limit.value) : 200
  const clamped = Math.min(2000, Math.max(1, value))
  limit.value = clamped
  return clamped
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  statusMessage.value = ''

  try {
    const response = await getServerLogs({
      limit: normalizeLimit(),
      level: level.value || undefined,
      contains: contains.value.trim() || undefined,
    })
    entries.value = response.entries
    statusMessage.value = `Loaded ${response.count} entries.`
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loading.value = false
  }
}

function clearFilters(): void {
  level.value = ''
  contains.value = ''
  void load()
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.filters {
  display: grid;
  gap: 0.7rem;
  grid-template-columns: minmax(90px, 140px) minmax(120px, 180px) minmax(220px, 1fr);
  align-items: end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
  color: var(--ink-700);
}

.text-input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: #ffffff;
}

.actions {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.table-wrap {
  overflow: auto;
  max-height: 540px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #ffffff;
}

.entries-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
  font-size: 0.85rem;
}

.entries-table th,
.entries-table td {
  border-bottom: 1px solid var(--border-muted);
  padding: 0.55rem 0.6rem;
  text-align: left;
  vertical-align: top;
}

.entries-table th {
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-600);
  background: var(--surface-alt);
  position: sticky;
  top: 0;
}

.entries-table tr:last-child td {
  border-bottom: none;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 74px;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-weight: 700;
  letter-spacing: 0.02em;
  font-size: 0.74rem;
}

.badge[data-level='DEBUG'] {
  color: #166534;
  background: #dcfce7;
  border-color: #86efac;
}

.badge[data-level='INFO'] {
  color: #075985;
  background: #e0f2fe;
  border-color: #7dd3fc;
}

.badge[data-level='WARNING'] {
  color: #a16207;
  background: #fef9c3;
  border-color: #fde047;
}

.badge[data-level='ERROR'] {
  color: #b91c1c;
  background: #fee2e2;
  border-color: #fca5a5;
}

.badge[data-level='CRITICAL'] {
  color: #ffffff;
  background: linear-gradient(130deg, #dc2626, #991b1b);
  border-color: #ef4444;
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.3);
}

.badge[data-level='NONE'] {
  color: var(--ink-600);
  background: #f8fafc;
  border-color: var(--border-muted);
}

.message {
  white-space: pre-wrap;
  word-break: break-word;
}

.raw {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  background: linear-gradient(155deg, var(--panel-dark), var(--panel-dark-2));
  color: var(--panel-ink);
  overflow: auto;
  max-height: 320px;
  font-size: 0.84rem;
}

@media (max-width: 900px) {
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
