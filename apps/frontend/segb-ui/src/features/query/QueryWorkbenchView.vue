<template>
  <div class="stack">
    <BaseCard title="SPARQL Workbench" subtitle="Read-only query execution.">
      <label class="field">
        <textarea
          v-model="query"
          rows="12"
          class="text-area"
          placeholder="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20"
        />
      </label>

      <div class="actions">
        <button class="btn ghost" :disabled="loading || validating || query.trim().length === 0" @click="validateOnly">
          {{ validating ? 'Validating…' : 'Validate query' }}
        </button>
        <button class="btn" :disabled="loading || validating || query.trim().length === 0" @click="run">
          {{ loading ? 'Running…' : 'Run query' }}
        </button>
      </div>

      <StatusBanner v-if="error" tone="error" :message="error" />
      <StatusBanner v-if="message" tone="info" :message="message" />
    </BaseCard>

    <BaseCard v-if="tableRows.length > 0" title="SELECT Result Table">
      <DataTable :columns="dynamicColumns" :rows="tableRows" />
    </BaseCard>

    <BaseCard v-if="rawTurtle" title="Raw Turtle Result">
      <pre class="raw">{{ rawTurtle }}</pre>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import DataTable, { type TableColumn } from '@/shared/ui/DataTable.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import { normalizeApiError } from '@/core/api/error'
import { runQueryTurtle, runSelectQuery, validateQuery } from '@/core/api/segbApi'

const query = ref(`SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20`)
const loading = ref(false)
const validating = ref(false)
const error = ref('')
const message = ref('')
const tableRows = ref<Array<Record<string, string>>>([])
const rawTurtle = ref('')

const dynamicColumns = computed<TableColumn[]>(() => {
  const first = tableRows.value[0]
  if (!first) {
    return []
  }
  return Object.keys(first).map((key) => ({ key, label: key }))
})

async function validateOnly(): Promise<void> {
  if (query.value.trim().length === 0) {
    return
  }

  validating.value = true
  error.value = ''
  message.value = ''
  try {
    const validation = await validateQuery(query.value)
    if (!validation.valid) {
      throw new Error(validation.message)
    }
    message.value = `Valid query (${validation.query_kind}).`
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    validating.value = false
  }
}

async function run(): Promise<void> {
  loading.value = true
  error.value = ''
  message.value = ''
  tableRows.value = []
  rawTurtle.value = ''

  try {
    const validation = await validateQuery(query.value)
    if (!validation.valid) {
      throw new Error(validation.message)
    }

    const kind = validation.query_kind.toLowerCase()
    if (kind === 'select') {
      tableRows.value = await runSelectQuery(query.value)
      message.value = `Returned ${tableRows.value.length} rows.`
      return
    }

    const output = await runQueryTurtle(query.value)
    if (kind === 'update') {
      message.value = output || 'SPARQL update executed successfully.'
      rawTurtle.value = ''
      return
    }

    rawTurtle.value = output
    message.value = `Returned ${rawTurtle.value.length} characters of turtle data.`
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
  resize: vertical;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.raw {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  background: linear-gradient(155deg, var(--panel-dark), var(--panel-dark-2));
  color: var(--panel-ink);
  overflow: auto;
  max-height: 420px;
  font-size: 0.82rem;
}
</style>
