<template>
  <div class="stack">
    <BaseCard title="Insert Semantic Log (TTL)">
      <div class="form-grid">
        <label class="field">
          <span>TTL Content</span>
          <textarea
            v-model="ttlContent"
            rows="14"
            class="text-area"
            placeholder="@prefix ..."
          />
        </label>
      </div>

      <div class="actions">
        <button class="btn ghost" :disabled="loading || validating || ttlContent.trim().length === 0" @click="validateOnly">
          {{ validating ? 'Validating…' : 'Validate TTL' }}
        </button>
        <button class="btn" :disabled="loading || validating || ttlContent.trim().length === 0" @click="submit">
          {{ loading ? 'Inserting…' : 'Insert TTL' }}
        </button>
      </div>

      <StatusBanner v-if="validationSummary" :tone="validationTone" :message="validationSummary" />
      <StatusBanner v-if="statusMessage" tone="success" :message="statusMessage" />
      <StatusBanner v-if="error" tone="error" :message="error" />

      <div v-if="validationIssues.length > 0" class="validation-panel">
        <h3 class="validation-title">Validation Findings</h3>
        <ul class="validation-list">
          <li
            v-for="(issue, index) in validationIssues"
            :key="`${issue.code}-${index}`"
            :class="['validation-item', issue.severity === 'error' ? 'is-error' : 'is-warning']"
          >
            <span class="issue-badge">{{ issue.severity }}</span>
            <div class="issue-content">
              <p class="issue-message">{{ issue.message }}</p>
              <p class="issue-meta">
                <span><strong>Code:</strong> <code>{{ issue.code }}</code></span>
                <span v-if="issue.focus_node"><strong>Node:</strong> <code>{{ issue.focus_node }}</code></span>
                <span v-if="issue.predicate"><strong>Predicate:</strong> <code>{{ issue.predicate }}</code></span>
                <span v-if="issue.value"><strong>Value:</strong> <code>{{ issue.value }}</code></span>
              </p>
            </div>
          </li>
        </ul>
      </div>
    </BaseCard>

    <BaseCard title="Current KG Snapshot">
      <template #actions>
        <button class="btn load-current" :disabled="loadingEvents || loading || validating" @click="loadEvents">
          {{ loadingEvents ? 'Loading…' : 'Load Current KG (TTL)' }}
        </button>
        <button class="btn download" :disabled="!eventsTtl.trim() || loadingEvents" @click="downloadEventsTtl">
          Download TTL
        </button>
      </template>
      <pre class="raw highlighted" v-html="highlightedEventsTtl" />
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import {
  type TtlValidationIssue,
  getEventsTurtle,
  insertTtl,
  validateTtl,
} from '@/core/api/segbApi'
import { normalizeApiError } from '@/core/api/error'
import { highlightTurtle } from '@/shared/rdf/highlightTurtle'

const ttlContent = ref('')
const loading = ref(false)
const loadingEvents = ref(false)
const validating = ref(false)
const statusMessage = ref('')
const error = ref('')
const eventsTtl = ref('')
const validationSummary = ref('')
const validationIssues = ref<TtlValidationIssue[]>([])

const validationTone = computed<'success' | 'warning' | 'error'>(() => {
  const hasErrors = validationIssues.value.some((issue) => issue.severity === 'error')
  if (hasErrors) {
    return 'error'
  }
  if (validationIssues.value.length > 0) {
    return 'warning'
  }
  return 'success'
})

const highlightedEventsTtl = computed(() => highlightTurtle(eventsTtl.value || 'No TTL loaded.'))

function clearValidationFeedback(): void {
  validationSummary.value = ''
  validationIssues.value = []
}

function summarizeValidationIssues(issues: TtlValidationIssue[]): string {
  const errorCount = issues.filter((issue) => issue.severity === 'error').length
  const warningCount = issues.filter((issue) => issue.severity === 'warning').length
  const errorLabel = errorCount === 1 ? 'error' : 'errors'
  const warningLabel = warningCount === 1 ? 'warning' : 'warnings'
  return `${errorCount} ${errorLabel}, ${warningCount} ${warningLabel}`
}

async function runValidation(): Promise<boolean> {
  error.value = ''
  statusMessage.value = ''

  try {
    const result = await validateTtl({
      ttl_content: ttlContent.value,
    })
    validationIssues.value = result.issues

    if (!result.valid) {
      validationSummary.value = `Validation failed (${summarizeValidationIssues(result.issues)}).`
      return false
    }

    if (result.issues.length > 0) {
      validationSummary.value = `Validation passed with warnings (${summarizeValidationIssues(result.issues)}).`
    } else {
      validationSummary.value = `Validation passed (${result.triple_count} triples checked).`
    }
    return true
  } catch (unknownError) {
    clearValidationFeedback()
    error.value = normalizeApiError(unknownError).message
    return false
  }
}

async function validateOnly(): Promise<void> {
  if (ttlContent.value.trim().length === 0) {
    return
  }

  validating.value = true
  try {
    await runValidation()
  } finally {
    validating.value = false
  }
}

async function submit(): Promise<void> {
  if (ttlContent.value.trim().length === 0) {
    return
  }

  loading.value = true
  statusMessage.value = ''
  error.value = ''
  clearValidationFeedback()

  try {
    const isValid = await runValidation()
    if (!isValid) {
      return
    }

    const response = await insertTtl({
      ttl_content: ttlContent.value,
    })
    statusMessage.value = `Inserted successfully. log_id=${response.log_id}`
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loading.value = false
  }
}

async function loadEvents(): Promise<void> {
  loadingEvents.value = true
  error.value = ''

  try {
    eventsTtl.value = await getEventsTurtle()
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loadingEvents.value = false
  }
}

function downloadEventsTtl(): void {
  const content = eventsTtl.value.trim()
  if (!content) {
    return
  }

  const timestamp = new Date().toISOString().replace(/:/g, '-').replace(/\./g, '-')
  const filename = `kg-snapshot-${timestamp}.ttl`
  const blob = new Blob([eventsTtl.value], { type: 'text/turtle;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.form-grid {
  display: grid;
  gap: 0.8rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
  color: var(--ink-700);
}

.text-area,
.text-input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.65rem 0.7rem;
  font: inherit;
  background: #ffffff;
}

.text-area {
  min-height: 240px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.actions {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.validation-panel {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #f8fbff;
  padding: 0.7rem;
}

.validation-title {
  margin: 0 0 0.45rem;
  font-size: 0.92rem;
  color: var(--ink-800);
}

.validation-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.validation-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.6rem;
  border: 1px solid var(--border-muted);
  border-radius: 9px;
  padding: 0.55rem 0.65rem;
  background: #ffffff;
}

.validation-item.is-error {
  border-color: #fecaca;
  background: #fff8f8;
}

.validation-item.is-warning {
  border-color: #fde68a;
  background: #fffcf0;
}

.issue-badge {
  align-self: start;
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 0.05rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
}

.validation-item.is-error .issue-badge {
  border-color: #fca5a5;
  color: #991b1b;
}

.validation-item.is-warning .issue-badge {
  border-color: #fcd34d;
  color: #92400e;
}

.issue-content {
  min-width: 0;
}

.issue-message {
  margin: 0;
  color: var(--ink-900);
  font-size: 0.86rem;
}

.issue-meta {
  margin: 0.22rem 0 0;
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  color: var(--ink-600);
  font-size: 0.78rem;
}

.raw {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  background: #0f172a;
  color: #dbeafe;
  overflow: auto;
  max-height: 380px;
  font-size: 0.82rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.btn.download {
  background: linear-gradient(130deg, #f97316, #ea580c);
  color: #ffffff;
}

.btn.load-current {
  background: linear-gradient(130deg, var(--accent), var(--accent-2));
  color: #ffffff;
}

.raw.highlighted :deep(.ttl-token-comment) {
  color: #94a3b8;
  font-style: italic;
}

.raw.highlighted :deep(.ttl-token-directive) {
  color: #67e8f9;
  font-weight: 700;
}

.raw.highlighted :deep(.ttl-token-uri) {
  color: #fda4af;
}

.raw.highlighted :deep(.ttl-token-prefixed) {
  color: #93c5fd;
}

.raw.highlighted :deep(.ttl-token-string) {
  color: #86efac;
}

.raw.highlighted :deep(.ttl-token-number) {
  color: #facc15;
}
</style>
