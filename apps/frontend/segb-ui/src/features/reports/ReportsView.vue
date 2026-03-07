<template>
  <div class="stack">
    <BaseCard
      title="Notebook Reports Dashboard"
      subtitle=""
    >
      <div class="actions">
        <button class="btn" :disabled="loading" @click="loadAllReports">
          {{ loading ? 'Loading reports…' : 'Refresh reports' }}
        </button>
      </div>
      <StatusBanner
        v-if="error"
        tone="error"
        :message="error"
      />
      <StatusBanner
        v-for="(warningMessage, warningIndex) in reportWarnings"
        :key="`report-warning-${warningIndex}`"
        tone="warning"
        :message="warningMessage"
      />
    </BaseCard>

    <div class="grid top-reports">
      <BaseCard title="Report 1: Participants">
        <div class="participants-sections">
          <section class="participants-section">
            <h4 class="section-title">Humans</h4>
            <DataTable :columns="participantColumns" :rows="humanParticipantsRows" :max-height="compactTableMaxHeight" />
          </section>

          <section class="participants-section">
            <h4 class="section-title">Robots</h4>
            <DataTable :columns="participantColumns" :rows="robotParticipantsRows" :max-height="compactTableMaxHeight" />
          </section>
        </div>
      </BaseCard>

      <BaseCard title="Report 2: ML Usage">
        <DataTable :columns="mlColumns" :rows="mlRows" :max-height="largeTableMaxHeight" />
      </BaseCard>
    </div>

    <BaseCard title="Report 3: Temporal Emotions">
      <div class="emotion-legend" aria-label="Emotion legend">
        <div v-for="item in emotionLegendItems" :key="item.key" class="emotion-legend-item">
          <span class="emotion-legend-swatch" :style="{ backgroundColor: item.color }" />
          <span>{{ item.label }}</span>
        </div>
      </div>
      <p class="note">Humans and Robots charts are grouped by target entity. Report 4 uses intensity threshold only.</p>
      <div v-if="humanEmotionCharts.length === 0 && robotEmotionCharts.length === 0" class="empty">No emotion timeline data available.</div>
      <div v-else class="emotion-spaces">
        <section class="emotion-space">
          <h4 class="section-title">Humans</h4>
          <div class="emotion-controls">
            <label class="select-label" for="human-emotion-select">Select a human</label>
            <select id="human-emotion-select" v-model="selectedHumanChartTitle" class="select-input">
              <option v-for="option in humanChartOptions" :key="option" :value="option">
                {{ option }}
              </option>
            </select>
          </div>
          <SimpleLineChart
            v-if="selectedHumanChart"
            :points="selectedHumanChart.points"
            :y-max="100"
            :show-title="false"
            :show-legend="false"
          />
          <div v-else class="empty">No human emotion timeline available.</div>
        </section>

        <section class="emotion-space">
          <h4 class="section-title">Robot targets</h4>
          <div class="emotion-controls">
            <label class="select-label" for="robot-select">Select a robot</label>
            <select id="robot-select" v-model="selectedRobotChartTitle" class="select-input">
              <option v-for="option in robotChartOptions" :key="option" :value="option">
                {{ option }}
              </option>
            </select>
          </div>
          <SimpleLineChart
            v-if="selectedRobotChart"
            :points="selectedRobotChart.points"
            :y-max="100"
            :show-title="false"
            :show-legend="false"
          />
          <div v-else class="empty">No robot emotion timeline available.</div>
        </section>
      </div>
    </BaseCard>

    <div class="grid two">
      <BaseCard title="Report 4: Extreme Emotions (>= 75%)">
        <template v-if="extremeRows.length > 0">
          <DataTable :columns="extremeColumns" :rows="extremeRows" :max-height="regularTableMaxHeight" />
        </template>
        <StatusBanner
          v-else
          tone="warning"
          :message="extremeEmptyMessage"
        />
      </BaseCard>

      <BaseCard title="Report 5: Extreme Emotion Distribution">
        <template v-if="extremeBars.length > 0">
          <SimpleBarChart title="Extreme emotion counts" :bars="extremeBars" />
        </template>
        <StatusBanner
          v-else
          tone="warning"
          message="No extreme emotions available for distribution."
        />
      </BaseCard>
    </div>

    <div class="grid two">
      <BaseCard title="Report 6: Robot State Timeline">
        <DataTable :columns="stateColumns" :rows="stateRows" :max-height="regularTableMaxHeight" />
      </BaseCard>

      <BaseCard title="Report 7: Displacement Summary">
        <DataTable :columns="summaryColumns" :rows="summaryRows" :max-height="regularTableMaxHeight" />
      </BaseCard>
    </div>

    <BaseCard title="Report 8: Conversation History">
      <div v-if="conversationMasterRows.length === 0" class="empty">No conversation data available.</div>
      <div v-else class="conversation-layout">
        <aside class="conversation-master">
          <button
            v-for="conversation in conversationMasterRows"
            :key="conversation.id"
            type="button"
            :class="['conversation-row', { active: conversation.id === selectedConversationId }]"
            @click="selectedConversationId = conversation.id"
          >
            <p class="conversation-pair">{{ conversation.participants }}</p>
            <p class="conversation-meta">{{ conversation.summary }}</p>
            <p class="conversation-preview">{{ conversation.preview }}</p>
          </button>
        </aside>

        <section class="conversation-detail">
          <template v-if="selectedConversation">
            <header class="conversation-detail-header">
              <h4 class="section-title">
                {{ selectedConversation.humanLabel }} ↔ {{ selectedConversation.robotLabel }}
              </h4>
              <p class="conversation-meta">
                {{ formatUtcTimestamp(selectedConversation.startedAt) || 'Unknown start' }}
                -
                {{ formatUtcTimestamp(selectedConversation.endedAt) || 'Unknown end' }}
              </p>
            </header>

            <div class="chat-thread">
              <article
                v-for="(message, index) in selectedConversation.messages"
                :key="`${selectedConversation.id}-${message.id}-${index}`"
                :class="['chat-row', message.senderRole]"
              >
                <div class="speaker-logo" :title="message.senderLabel">
                  <span>{{ speakerGlyph(message.senderRole) }}</span>
                </div>

                <div :class="['chat-bubble', message.senderRole]">
                  <p class="chat-meta">
                    <strong>{{ message.senderLabel }}</strong>
                    ·
                    {{ formatUtcTimestamp(message.t) || 'Unknown timestamp' }}
                  </p>
                  <p class="chat-text">{{ message.text }}</p>
                </div>
              </article>
            </div>
          </template>
          <div v-else class="empty">Select a conversation from the master list.</div>
        </section>
      </div>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import DataTable, { type TableColumn } from '@/shared/ui/DataTable.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import SimpleLineChart from '@/shared/charts/SimpleLineChart.vue'
import SimpleBarChart from '@/shared/charts/SimpleBarChart.vue'
import { formatRatioAsPercent } from '@/shared/utils/format'
import { useReports } from '@/features/reports/useReports'
import { REPORT_EXTREME_EMOTION_THRESHOLD } from '@/features/reports/queries'

const {
  loading,
  error,
  reportWarnings,
  humanParticipants,
  robotParticipants,
  mlUsage,
  emotionTimelineByHumanParticipant,
  emotionTimelineByRobotParticipant,
  maxEmotionIntensity,
  extremeEmotion,
  extremeEmotionBars,
  robotStates,
  displacementSummary,
  conversationSessions,
  loadAllReports,
  normalizeEmotionLabel,
  formatUtcTimestamp,
} = useReports()

const participantColumns: TableColumn[] = [
  { key: 'participant', label: 'Participant' },
  { key: 'interactedWith', label: 'Interacted with' },
]

const mlColumns: TableColumn[] = [
  { key: 'usedBy', label: 'Used by' },
  { key: 'usedAt', label: 'When (UTC)' },
  { key: 'activity', label: 'Activity' },
  { key: 'activityType', label: 'Activity Type' },
  { key: 'modelLabel', label: 'Model' },
  { key: 'version', label: 'Version' },
  { key: 'datasetLabel', label: 'Dataset' },
  { key: 'score', label: 'Evaluation Score (%)' },
]

const extremeColumns: TableColumn[] = [
  { key: 'timestamp', label: 'Timestamp' },
  { key: 'target', label: 'Subject' },
  { key: 'category', label: 'Emotion' },
  { key: 'intensity', label: 'Intensity (%)' },
  { key: 'confidence', label: 'Confidence (%)' },
]

const stateColumns: TableColumn[] = [
  { key: 'robot', label: 'Robot' },
  { key: 'timestamp', label: 'Timestamp' },
  { key: 'location', label: 'Location' },
]

const summaryColumns: TableColumn[] = [
  { key: 'robot', label: 'Robot' },
  { key: 'samples', label: 'State Samples' },
  { key: 'locationChanges', label: 'Location Changes' },
  { key: 'path', label: 'Observed Path' },
]

const humanParticipantsRows = computed(() => humanParticipants.value)
const robotParticipantsRows = computed(() => robotParticipants.value)
const mlRows = computed(() => mlUsage.value)
const compactTableMaxHeight = 190
const regularTableMaxHeight = 340
const largeTableMaxHeight = 560
const EXTREME_THRESHOLD = REPORT_EXTREME_EMOTION_THRESHOLD

const emotionLegendItems = [
  { key: 'joy', label: 'Joy', color: '#facc15' },
  { key: 'sadness', label: 'Sadness', color: '#2563eb' },
  { key: 'anger', label: 'Anger', color: '#dc2626' },
  { key: 'fear', label: 'Fear', color: '#9333ea' },
  { key: 'disgust', label: 'Disgust', color: '#16a34a' },
  { key: 'surprise', label: 'Surprise', color: '#60a5fa' },
]

const humanEmotionCharts = computed(() => {
  return Array.from(emotionTimelineByHumanParticipant.value.entries()).map(([participant, points]) => ({
    title: participant,
    points,
  }))
})

const robotEmotionCharts = computed(() => {
  return Array.from(emotionTimelineByRobotParticipant.value.entries()).map(([participant, points]) => ({
    title: participant,
    points,
  }))
})

const humanChartOptions = computed(() => {
  return humanEmotionCharts.value.map((chart) => chart.title)
})

const robotChartOptions = computed(() => {
  return robotEmotionCharts.value.map((chart) => chart.title)
})

const selectedHumanChartTitle = ref('')
const selectedRobotChartTitle = ref('')

const selectedHumanChart = computed(() => {
  return humanEmotionCharts.value.find((chart) => chart.title === selectedHumanChartTitle.value)
})

const selectedRobotChart = computed(() => {
  return robotEmotionCharts.value.find((chart) => chart.title === selectedRobotChartTitle.value)
})

const extremeRows = computed(() => {
  return extremeEmotion.value.map((row) => ({
    timestamp: formatUtcTimestamp(row.t),
    target: row.targetLabel ? `🧑 ${row.targetLabel}` : '',
    category: normalizeEmotionLabel(row.category),
    intensity: formatRatioAsPercent(row.intensity, 0),
    confidence: formatRatioAsPercent(row.confidence, 0),
  }))
})

const extremeEmptyMessage = computed(() => {
  if (maxEmotionIntensity.value === null) {
    return 'No emotion timeline data available yet.'
  }
  return `No extreme emotions found with threshold >= ${formatRatioAsPercent(EXTREME_THRESHOLD, 0)}. Current max intensity: ${formatRatioAsPercent(maxEmotionIntensity.value, 0)}.`
})

const extremeBars = computed(() => extremeEmotionBars.value)

const stateRows = computed(() => {
  return robotStates.value.map((row) => ({
    robot: row.robotName,
    timestamp: formatUtcTimestamp(row.t),
    location: row.location,
  }))
})

const summaryRows = computed(() => displacementSummary.value)
const selectedConversationId = ref('')

const conversationMasterRows = computed(() => {
  return conversationSessions.value.map((session) => ({
    id: session.id,
    participants: `🧑 ${session.humanLabel} ↔ 🤖 ${session.robotLabel}`,
    summary: `${session.messageCount} messages · ${formatUtcTimestamp(session.startedAt) || 'Unknown start'} - ${formatUtcTimestamp(session.endedAt) || 'Unknown end'}`,
    preview: session.preview || '(No preview)',
  }))
})

const selectedConversation = computed(() => {
  if (!selectedConversationId.value) {
    return conversationSessions.value[0]
  }
  return conversationSessions.value.find((session) => session.id === selectedConversationId.value) ?? conversationSessions.value[0]
})

function speakerGlyph(role: 'human' | 'robot' | 'unknown'): string {
  if (role === 'human') {
    return '🧑'
  }
  if (role === 'robot') {
    return '🤖'
  }
  return '🗨️'
}

watch(
  humanChartOptions,
  (options) => {
    if (options.length === 0) {
      selectedHumanChartTitle.value = ''
      return
    }
    if (!options.includes(selectedHumanChartTitle.value)) {
      selectedHumanChartTitle.value = options[0] ?? ''
    }
  },
  { immediate: true },
)

watch(
  robotChartOptions,
  (options) => {
    if (options.length === 0) {
      selectedRobotChartTitle.value = ''
      return
    }
    if (!options.includes(selectedRobotChartTitle.value)) {
      selectedRobotChartTitle.value = options[0] ?? ''
    }
  },
  { immediate: true },
)

watch(
  conversationSessions,
  (sessions) => {
    if (sessions.length === 0) {
      selectedConversationId.value = ''
      return
    }
    if (!sessions.some((session) => session.id === selectedConversationId.value)) {
      selectedConversationId.value = sessions[0]?.id ?? ''
    }
  },
  { immediate: true },
)

onMounted(() => {
  void loadAllReports()
})
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.grid {
  display: grid;
  gap: 0.9rem;
}

.grid.top-reports {
  grid-template-columns: minmax(320px, 0.65fr) minmax(0, 1.35fr);
  align-items: start;
}

.grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.participants-sections {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.participants-section {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.section-title {
  margin: 0;
  font-size: 1.08rem;
  font-weight: 700;
  color: var(--ink-700);
}

.actions {
  display: flex;
  gap: 0.6rem;
}

.note {
  margin: 0;
  font-size: 0.9rem;
  color: var(--ink-600);
}

.emotion-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.42rem 0.8rem;
}

.emotion-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 1rem;
  color: var(--ink-700);
}

.emotion-legend-swatch {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.emotion-spaces {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.emotion-space {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-alt);
  padding: 0.7rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-width: 0;
}

.emotion-controls {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.35rem;
}

.select-label {
  font-size: 0.83rem;
  font-weight: 650;
  color: var(--ink-700);
}

.select-input {
  appearance: none;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--ink-900);
  padding: 0.46rem 0.62rem;
  font-size: 0.9rem;
}

.select-input:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 1px;
}

.empty {
  color: var(--ink-500);
  font-size: 0.92rem;
}

.conversation-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr);
  gap: 0.9rem;
  min-width: 0;
}

.conversation-master {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-alt);
  max-height: 460px;
  overflow: auto;
  padding: 0.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.conversation-row {
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 10px;
  text-align: left;
  padding: 0.62rem;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  color: var(--ink-900);
}

.conversation-row:hover {
  border-color: var(--border);
  background: var(--surface);
}

.conversation-row.active {
  border-color: #93c5fd;
  background: #eff6ff;
}

.conversation-pair {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 650;
}

.conversation-meta {
  margin: 0;
  font-size: 0.82rem;
  color: var(--ink-600);
}

.conversation-preview {
  margin: 0;
  font-size: 0.84rem;
  color: var(--ink-700);
}

.conversation-detail {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-alt);
  padding: 0.7rem;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.conversation-detail-header {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.chat-thread {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 460px;
  overflow: auto;
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  width: 100%;
}

.chat-row.robot {
  justify-content: flex-start;
}

.chat-row.human {
  justify-content: flex-end;
}

.chat-row.human .speaker-logo {
  order: 2;
}

.chat-row.human .chat-bubble {
  order: 1;
}

.speaker-logo {
  width: 2rem;
  height: 2rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  background: #f8fafc;
}

.chat-row.human .speaker-logo {
  background: #ffedd5;
  border-color: #fdba74;
}

.chat-row.robot .speaker-logo {
  background: #dbeafe;
  border-color: #93c5fd;
}

.chat-bubble {
  border-radius: 12px;
  border: 1px solid var(--border);
  padding: 0.55rem 0.7rem;
  width: fit-content;
  max-width: 70%;
  min-width: min(18rem, 70%);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.chat-bubble.human {
  background: #fff7ed;
  border-color: #fed7aa;
}

.chat-bubble.robot {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.chat-bubble.unknown {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.chat-meta {
  margin: 0;
  font-size: 0.78rem;
  color: var(--ink-600);
}

.chat-row.human .chat-meta {
  text-align: right;
}

.chat-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--ink-900);
}

@media (max-width: 1200px) {
  .grid.top-reports {
    grid-template-columns: 1fr;
  }

  .grid.two {
    grid-template-columns: 1fr;
  }

  .conversation-layout {
    grid-template-columns: 1fr;
  }

  .chat-bubble {
    max-width: 88%;
    min-width: min(14rem, 88%);
  }
}
</style>
