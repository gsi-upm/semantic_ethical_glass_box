<template>
  <div class="stack">
    <BaseCard
      title="Shared Context Review"
      subtitle="Only cases that cannot be merged automatically are shown here; high-confidence matches are merged automatically."
    >
      <div class="toolbar">
        <button class="btn" :disabled="loadingQueue || loadingDecision" @click="refreshAll">
          {{ loadingQueue ? 'Refreshing…' : 'Refresh queue' }}
        </button>
        <button class="btn ghost" :disabled="loadingStats || loadingDecision" @click="loadStats">
          {{ loadingStats ? 'Loading…' : 'Refresh summary' }}
        </button>
      </div>

      <div class="kpi-grid">
        <article class="kpi-card">
          <p class="kpi-title">Pending reviews</p>
          <p class="kpi-value">{{ formatCount(queue?.pending_count ?? 0) }}</p>
          <p class="kpi-help">Require manual decision</p>
        </article>
        <article class="kpi-card">
          <p class="kpi-title">Unresolved contexts</p>
          <p class="kpi-value">{{ formatCount(queue?.unresolved_count ?? 0) }}</p>
          <p class="kpi-help">Currently ambiguous</p>
        </article>
        <article class="kpi-card">
          <p class="kpi-title">Active contexts</p>
          <p class="kpi-value">{{ formatCount(stats?.active_contexts ?? 0) }}</p>
          <p class="kpi-help">Available as reference</p>
        </article>
        <article class="kpi-card">
          <p class="kpi-title">Merged contexts</p>
          <p class="kpi-value">{{ formatCount(stats?.merged_contexts ?? 0) }}</p>
          <p class="kpi-help">Already integrated into canonical context</p>
        </article>
        <article class="kpi-card">
          <p class="kpi-title">Alias mappings</p>
          <p class="kpi-value">{{ formatCount(stats?.aliases ?? 0) }}</p>
          <p class="kpi-help">Source -> canonical redirects</p>
        </article>
      </div>

      <StatusBanner v-if="statusMessage" tone="success" :message="statusMessage" />
      <StatusBanner v-if="error" tone="error" :message="error" />
    </BaseCard>

    <div class="grid two">
      <BaseCard title="Pending Queue">
        <p v-if="pendingCases.length === 0" class="empty">
          There are no pending cases right now.
        </p>

        <button
          v-for="(reviewCase, index) in pendingCases"
          :key="reviewCase.case_id"
          class="case-item"
          :class="{ active: reviewCase.case_id === selectedCaseId }"
          @click="selectCase(reviewCase.case_id)"
        >
          <p class="case-title">Case {{ index + 1 }}</p>
          <p class="case-line"><strong>Event:</strong> {{ caseEventLabel(reviewCase) }}</p>
          <p class="case-line"><strong>Source:</strong> {{ caseSourceLabel(reviewCase) }}</p>
          <p class="case-line"><strong>Suggested candidates:</strong> {{ reviewCase.candidates.length }}</p>
          <p class="case-meta">Internal ID: {{ reviewCase.case_id }}</p>
        </button>
      </BaseCard>

      <BaseCard title="Decision Area">
        <p v-if="!selectedCase" class="empty">
          Select a pending case to inspect evidence and decide.
        </p>

        <div v-else class="detail-stack">
          <div class="header-row">
            <div class="header-info">
              <p class="title-line">Case {{ selectedCasePosition }} selected</p>
              <p class="meta">Comparing source context with {{ selectedCase.candidates.length }} candidate(s).</p>
            </div>
            <button class="btn danger" :disabled="loadingDecision" @click="rejectCase">
              {{ loadingDecision ? 'Applying…' : 'Keep contexts separate' }}
            </button>
          </div>

          <div class="panel">
            <p class="label">Source context (requires decision)</p>
            <p class="line"><strong>Event:</strong> {{ eventKindLabel(sourceRecord?.event_kind) }}</p>
            <p class="line"><strong>Subject:</strong> {{ humanizeUri(sourceRecord?.subject_uri, 'Not available') }}</p>
            <p class="line"><strong>Modality:</strong> {{ humanizeText(sourceRecord?.modality, 'Not available') }}</p>
            <p class="line"><strong>Linked observations:</strong> {{ formatCount(sourceRecord?.observation_count ?? 0) }}</p>
            <p class="line"><strong>Latest detection:</strong> {{ formatWhen(sourceRecord?.observed_at) }}</p>
            <p class="line message"><strong>Main description:</strong> {{ humanizeText(sourceRecord?.canonical_text, 'No text') }}</p>
          </div>

          <div class="panel">
            <p class="label">Merge options</p>
            <p v-if="selectedCase.candidates.length === 0" class="empty">No candidates available for this case.</p>

            <article v-for="(candidate, index) in selectedCase.candidates" :key="candidate.context_uri" class="candidate-row">
              <div class="candidate-card" :class="{ active: candidate.context_uri === selectedCandidateUri }">
                <div class="candidate-top">
                  <p class="candidate-title">Candidate {{ index + 1 }}</p>
                  <span class="score-pill">{{ formatScore(candidate.score) }} similarity</span>
                </div>

                <p class="candidate-summary">{{ describeCandidate(candidate.context_uri) }}</p>
                <p class="breakdown">
                  Time: {{ formatBreakdown(candidate.score_breakdown.time) }} · Text: {{ formatBreakdown(candidate.score_breakdown.text) }} ·
                  Subject: {{ formatBreakdown(candidate.score_breakdown.subject) }} · Modality: {{ formatBreakdown(candidate.score_breakdown.modality) }}
                </p>
              </div>

              <div class="candidate-actions">
                <button
                  class="btn ghost small"
                  :disabled="loadingDecision"
                  @click="selectedCandidateUri = candidate.context_uri"
                >
                  {{ candidate.context_uri === selectedCandidateUri ? 'Evidence visible' : 'View evidence' }}
                </button>
                <button class="btn small" :disabled="loadingDecision" @click="acceptCandidate(candidate.context_uri)">
                  {{ loadingDecision ? 'Applying…' : 'Accept this merge' }}
                </button>
              </div>
            </article>
          </div>

          <div class="comparison">
            <div class="panel">
              <p class="label">Source context evidence</p>
              <p class="panel-note">
                Observations recorded in TTL and linked to the shared context.
              </p>
              <p v-if="(sourceRecord?.observations.length ?? 0) === 0" class="empty">No observations recorded.</p>

              <article v-for="(observation, index) in sourceRecord?.observations ?? []" :key="`source-${index}`" class="obs-card">
                <p class="obs-time">{{ formatWhen(observation.observed_at) }}</p>
                <p class="obs-line"><strong>Robot:</strong> {{ humanizeUri(observation.robot_uri, 'Not available') }}</p>
                <p class="obs-line"><strong>Subject:</strong> {{ humanizeUri(observation.subject_uri, 'Not available') }}</p>
                <p class="obs-line"><strong>Modality:</strong> {{ humanizeText(observation.modality, 'Not available') }}</p>
                <p class="obs-line"><strong>Observation:</strong> {{ humanizeUri(observation.observation_uri, 'No identifier') }}</p>
                <p class="obs-line"><strong>Message:</strong> {{ humanizeText(observation.text, 'No text') }}</p>
              </article>
            </div>

            <div class="panel">
              <p class="label">Selected candidate evidence</p>
              <p v-if="!selectedCandidate" class="empty">Select a candidate to view evidence.</p>
              <p v-else class="panel-note">{{ describeCandidate(selectedCandidate.context_uri) }}</p>

              <p v-if="selectedCandidate && (candidateRecord?.observations.length ?? 0) === 0" class="empty">
                No observations recorded.
              </p>

              <article v-for="(observation, index) in candidateRecord?.observations ?? []" :key="`candidate-${index}`" class="obs-card">
                <p class="obs-time">{{ formatWhen(observation.observed_at) }}</p>
                <p class="obs-line"><strong>Robot:</strong> {{ humanizeUri(observation.robot_uri, 'Not available') }}</p>
                <p class="obs-line"><strong>Subject:</strong> {{ humanizeUri(observation.subject_uri, 'Not available') }}</p>
                <p class="obs-line"><strong>Modality:</strong> {{ humanizeText(observation.modality, 'Not available') }}</p>
                <p class="obs-line"><strong>Observation:</strong> {{ humanizeUri(observation.observation_uri, 'No identifier') }}</p>
                <p class="obs-line"><strong>Message:</strong> {{ humanizeText(observation.text, 'No text') }}</p>
              </article>
            </div>
          </div>
        </div>
      </BaseCard>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import { normalizeApiError } from '@/core/api/error'
import {
  acceptSharedContextReviewCase,
  getSharedContextReviewQueue,
  getSharedContextStats,
  rejectSharedContextReviewCase,
  type SharedContextReviewCandidate,
  type SharedContextReviewCase,
  type SharedContextReviewQueueResponse,
  type SharedContextReviewRecord,
  type SharedContextStatsResponse,
} from '@/core/api/segbApi'
import { compactUri, titleCase } from '@/shared/utils/format'

const DATE_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  timeZone: 'UTC',
})
const NUMBER_FORMATTER = new Intl.NumberFormat('en-GB')

const loadingQueue = ref(false)
const loadingDecision = ref(false)
const loadingStats = ref(false)
const error = ref('')
const statusMessage = ref('')
const queue = ref<SharedContextReviewQueueResponse | null>(null)
const stats = ref<SharedContextStatsResponse | null>(null)
const selectedCaseId = ref('')
const selectedCandidateUri = ref('')

const pendingCases = computed<SharedContextReviewCase[]>(() => queue.value?.pending_cases ?? [])

const contextsByUri = computed<Record<string, SharedContextReviewRecord>>(() => {
  const lookup: Record<string, SharedContextReviewRecord> = {}
  for (const context of queue.value?.contexts ?? []) {
    lookup[context.uri] = context
  }
  return lookup
})

const selectedCase = computed<SharedContextReviewCase | null>(() => {
  if (!selectedCaseId.value) {
    return null
  }
  return pendingCases.value.find((reviewCase) => reviewCase.case_id === selectedCaseId.value) ?? null
})

const selectedCasePosition = computed<string>(() => {
  if (!selectedCase.value) {
    return '-'
  }
  const index = pendingCases.value.findIndex((reviewCase) => reviewCase.case_id === selectedCase.value?.case_id)
  return index >= 0 ? String(index + 1) : '-'
})

const selectedCandidate = computed<SharedContextReviewCandidate | null>(() => {
  if (!selectedCase.value || !selectedCandidateUri.value) {
    return null
  }
  return selectedCase.value.candidates.find((candidate) => candidate.context_uri === selectedCandidateUri.value) ?? null
})

const sourceRecord = computed<SharedContextReviewRecord | null>(() => {
  const sourceUri = selectedCase.value?.source_context_uri
  if (!sourceUri) {
    return null
  }
  return contextsByUri.value[sourceUri] ?? null
})

const candidateRecord = computed<SharedContextReviewRecord | null>(() => {
  if (!selectedCandidateUri.value) {
    return null
  }
  return contextsByUri.value[selectedCandidateUri.value] ?? null
})

function normalizeWords(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
}

function formatCount(value: number): string {
  return NUMBER_FORMATTER.format(value)
}

function eventKindLabel(eventKind: string | null | undefined): string {
  if (!eventKind) {
    return 'Not available'
  }
  return titleCase(normalizeWords(eventKind))
}

function humanizeUri(uri: string | null | undefined, fallback = '-'): string {
  if (!uri) {
    return fallback
  }
  const compact = compactUri(uri)
  if (!compact) {
    return fallback
  }
  return titleCase(normalizeWords(compact))
}

function humanizeText(value: string | null | undefined, fallback = '-'): string {
  const trimmed = value?.trim() ?? ''
  return trimmed || fallback
}

function formatWhen(raw: string | null | undefined): string {
  if (!raw) {
    return 'Not available'
  }
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) {
    return raw
  }
  return `${DATE_FORMATTER.format(date)} UTC`
}

function formatScore(score: number): string {
  return `${(score * 100).toFixed(1)}%`
}

function formatBreakdown(value: number | undefined): string {
  if (value === undefined) {
    return 'N/A'
  }
  return `${Math.round(value * 100)}%`
}

function describeRecord(record: SharedContextReviewRecord | null): string {
  if (!record) {
    return 'No details available.'
  }
  return `${eventKindLabel(record.event_kind)} · ${humanizeText(record.modality, 'No modality')} · ${formatCount(record.observation_count)} observation(s) · Latest detection: ${formatWhen(record.observed_at)}`
}

function describeCandidate(contextUri: string): string {
  const record = contextsByUri.value[contextUri] ?? null
  return describeRecord(record)
}

function caseEventLabel(reviewCase: SharedContextReviewCase): string {
  const record = contextsByUri.value[reviewCase.source_context_uri] ?? null
  return eventKindLabel(record?.event_kind)
}

function caseSourceLabel(reviewCase: SharedContextReviewCase): string {
  const record = contextsByUri.value[reviewCase.source_context_uri] ?? null
  if (!record) {
    return 'No data'
  }
  return `${humanizeUri(record.subject_uri, 'Subject unavailable')} · ${formatWhen(record.observed_at)}`
}

function ensureSelection(): void {
  if (pendingCases.value.length === 0) {
    selectedCaseId.value = ''
    selectedCandidateUri.value = ''
    return
  }

  const selectedStillExists = pendingCases.value.some((reviewCase) => reviewCase.case_id === selectedCaseId.value)
  if (!selectedStillExists) {
    const firstCase = pendingCases.value[0]
    selectedCaseId.value = firstCase ? firstCase.case_id : ''
  }

  const activeCase = pendingCases.value.find((reviewCase) => reviewCase.case_id === selectedCaseId.value)
  if (!activeCase) {
    selectedCandidateUri.value = ''
    return
  }

  const candidateExists = activeCase.candidates.some((candidate) => candidate.context_uri === selectedCandidateUri.value)
  if (!candidateExists) {
    selectedCandidateUri.value = activeCase.candidates[0]?.context_uri ?? ''
  }
}

async function loadQueue(): Promise<void> {
  loadingQueue.value = true
  error.value = ''

  try {
    queue.value = await getSharedContextReviewQueue()
    ensureSelection()
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loadingQueue.value = false
  }
}

async function loadStats(): Promise<void> {
  loadingStats.value = true
  error.value = ''

  try {
    stats.value = await getSharedContextStats()
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loadingStats.value = false
  }
}

async function refreshAll(): Promise<void> {
  statusMessage.value = ''
  await Promise.all([loadQueue(), loadStats()])
}

function selectCase(caseId: string): void {
  selectedCaseId.value = caseId
  const activeCase = pendingCases.value.find((reviewCase) => reviewCase.case_id === caseId)
  selectedCandidateUri.value = activeCase?.candidates[0]?.context_uri ?? ''
}

async function acceptCandidate(targetContextUri: string): Promise<void> {
  if (!selectedCase.value) {
    return
  }

  loadingDecision.value = true
  error.value = ''
  statusMessage.value = ''

  try {
    await acceptSharedContextReviewCase(selectedCase.value.case_id, targetContextUri)
    statusMessage.value = 'Merge accepted: source context has been integrated into the selected candidate.'
    await refreshAll()
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loadingDecision.value = false
  }
}

async function rejectCase(): Promise<void> {
  if (!selectedCase.value) {
    return
  }

  loadingDecision.value = true
  error.value = ''
  statusMessage.value = ''

  try {
    await rejectSharedContextReviewCase(selectedCase.value.case_id)
    statusMessage.value = 'Merge rejected: both contexts remain independent.'
    await refreshAll()
  } catch (unknownError) {
    error.value = normalizeApiError(unknownError).message
  } finally {
    loadingDecision.value = false
  }
}

onMounted(() => {
  void refreshAll()
})
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.grid.two {
  display: grid;
  grid-template-columns: minmax(290px, 0.9fr) minmax(0, 1.5fr);
  gap: 1rem;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.65rem;
}

.kpi-card {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: linear-gradient(165deg, #ffffff, #f4fbff);
  padding: 0.65rem 0.72rem;
  box-shadow: 0 1px 6px rgba(0, 98, 155, 0.08);
}

.kpi-title {
  margin: 0;
  font-size: 0.8rem;
  color: var(--ink-600);
}

.kpi-value {
  margin: 0.22rem 0 0.18rem;
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--ink-900);
  letter-spacing: 0.01em;
}

.kpi-help {
  margin: 0;
  font-size: 0.78rem;
  color: var(--ink-500);
}

.hint {
  margin: 0;
  font-size: 0.86rem;
  color: var(--ink-600);
  line-height: 1.45;
}

.empty {
  margin: 0;
  color: var(--ink-600);
}

.case-item {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #ffffff;
  padding: 0.7rem;
  margin-bottom: 0.5rem;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.case-item.active {
  border-color: #61b4d9;
  background: #eef8fd;
}

.case-title {
  margin: 0;
  font-weight: 750;
  color: var(--ink-900);
  font-size: 0.95rem;
}

.case-line {
  margin: 0;
  font-size: 0.82rem;
  color: var(--ink-700);
  line-height: 1.35;
}

.case-meta {
  margin: 0.18rem 0 0;
  font-size: 0.76rem;
  color: var(--ink-500);
}

.detail-stack {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.title-line {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 750;
  color: var(--ink-900);
}

.meta {
  margin: 0;
  font-size: 0.82rem;
  color: var(--ink-600);
}

.panel {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.72rem;
  background: #ffffff;
}

.label {
  margin: 0 0 0.38rem;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-600);
  font-weight: 700;
}

.line {
  margin: 0.12rem 0;
  color: var(--ink-700);
  font-size: 0.86rem;
  line-height: 1.4;
}

.line.message {
  margin-top: 0.22rem;
  color: var(--ink-800);
}

.candidate-row {
  border: 1px solid var(--border-muted);
  border-radius: 11px;
  padding: 0.56rem;
  margin-bottom: 0.52rem;
  background: #fbfdff;
}

.candidate-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.55rem 0.62rem;
  background: #ffffff;
}

.candidate-card.active {
  border-color: #61b4d9;
  background: #eef8fd;
}

.candidate-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.candidate-title {
  margin: 0;
  font-weight: 700;
  color: var(--ink-900);
}

.candidate-summary {
  margin: 0.35rem 0 0.32rem;
  font-size: 0.82rem;
  color: var(--ink-700);
  line-height: 1.35;
}

.score-pill {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.14rem 0.48rem;
  font-size: 0.76rem;
  color: var(--ink-700);
  background: #ffffff;
  font-weight: 700;
}

.breakdown {
  margin: 0;
  font-size: 0.8rem;
  color: var(--ink-600);
  line-height: 1.4;
}

.candidate-actions {
  display: flex;
  gap: 0.46rem;
  justify-content: flex-end;
  margin-top: 0.48rem;
}

.comparison {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
}

.panel-note {
  margin: 0 0 0.52rem;
  color: var(--ink-600);
  font-size: 0.82rem;
  line-height: 1.35;
}

.obs-card {
  border: 1px solid var(--border-muted);
  border-radius: 10px;
  padding: 0.52rem 0.6rem;
  background: #fafdff;
  margin-bottom: 0.48rem;
}

.obs-time {
  margin: 0 0 0.34rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--ink-800);
}

.obs-line {
  margin: 0.15rem 0;
  font-size: 0.82rem;
  color: var(--ink-700);
  line-height: 1.36;
}

.btn.small {
  padding: 0.45rem 0.64rem;
  font-size: 0.82rem;
}

.btn.danger {
  border-color: #b91c1c;
  background: linear-gradient(130deg, #dc2626, #b91c1c);
  color: #ffffff;
}

@media (max-width: 1250px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .grid.two,
  .comparison {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .header-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .candidate-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
