import { computed, ref } from 'vue'

import { runSelectQuery } from '@/core/api/segbApi'
import { compactUri, formatRatioAsPercent, formatUtcTimestamp, titleCase, toNumber } from '@/shared/utils/format'
import { reportQueries } from '@/features/reports/queries'
import type {
  ReportConversationMessage,
  ReportConversationSession,
  ReportDisplacementSummary,
  ReportEmotionSample,
  ReportMlUsage,
  ReportParticipantInteraction,
  ReportStateSample,
} from '@/features/reports/types'

const PARTICIPANT_SEPARATOR = '__SEGB_LINE_BREAK__'
const CONVERSATION_GAP_MS = 2 * 60 * 1000

function normalizeEmotionLabel(uri: string): string {
  const compact = compactUri(uri)
  return titleCase(compact.replace(/^big6[_-]/i, ''))
}

function asLines(value: string): string[] {
  return value
    .split(PARTICIPANT_SEPARATOR)
    .flatMap((chunk) => chunk.split('\n'))
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function decorateParticipants(value: string, icon: string): string {
  const unique = Array.from(new Set(asLines(value)))
  if (unique.length === 0) {
    return ''
  }
  return unique.map((name) => `${icon} ${name}`).join('\n')
}

function decorateParticipant(name: string, icon: string): string {
  const normalized = name.trim()
  return normalized.length > 0 ? `${icon} ${normalized}` : ''
}

function mergeParticipantLists(...lists: string[]): string {
  const merged = Array.from(new Set(lists.flatMap((value) => asLines(value))))
  return merged.join('\n')
}

function firstPipeValue(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  const candidate = value
    .split(' | ')
    .map((item) => item.trim())
    .find((item) => item.length > 0)
  return candidate ?? ''
}

function resolveEmotionTrigger(row: ReportEmotionSample): string {
  const triggerMessageText = firstPipeValue(row.triggerMessageText)
  const targetLabel = firstPipeValue(row.targetLabel)
  const targetEntity = firstPipeValue(row.targetEntity)
  const subject = targetLabel || compactUri(targetEntity)

  if (triggerMessageText.length > 0) {
    if (subject.length > 0) {
      return `Observed context for ${subject}: "${triggerMessageText}"`
    }
    return `Observed context: "${triggerMessageText}"`
  }

  return subject.length > 0 ? `Observed context for ${subject}` : ''
}

function normalizeRatio(raw: string | null | undefined): number | null {
  const numeric = toNumber(raw)
  if (numeric === null) {
    return null
  }
  if (numeric > 1 && numeric <= 100) {
    return numeric / 100
  }
  return numeric
}

function normalizePercent(raw: string | null | undefined): number | null {
  const ratio = normalizeRatio(raw)
  if (ratio === null) {
    return null
  }
  return ratio * 100
}

function parseTimestampMs(raw: string): number | null {
  if (!raw) {
    return null
  }
  const timestamp = Date.parse(raw)
  if (Number.isNaN(timestamp)) {
    return null
  }
  return timestamp
}

function normalizeSenderRole(raw: string): 'human' | 'robot' | 'unknown' {
  const normalized = raw.trim().toLowerCase()
  if (normalized === 'human' || normalized === 'robot') {
    return normalized
  }
  return 'unknown'
}

function normalizeEntityType(raw: string): 'human' | 'robot' | 'entity' | 'unknown' {
  const normalized = raw.trim().toLowerCase()
  if (normalized === 'human' || normalized === 'robot' || normalized === 'entity') {
    return normalized
  }
  return 'unknown'
}

function isEmotionTargetHuman(row: ReportEmotionSample): boolean {
  const targetType = normalizeEntityType(row.targetType)
  if (targetType === 'human') {
    return true
  }
  const targetEntity = row.targetEntity.trim().toLowerCase()
  return targetEntity.includes('/human_') || targetEntity.includes('#human_')
}

function isEmotionActorRobot(row: ReportEmotionSample): boolean {
  const actorType = normalizeEntityType(row.performedByType)
  if (actorType === 'robot') {
    return true
  }
  const performedBy = row.performedBy.trim().toLowerCase()
  return performedBy.includes('/robot_') || performedBy.includes('#robot_') || performedBy.includes('/robots/')
}

function inferSenderRole(rawRole: string, rawMessageType: string, rawPerformedByRole: string): 'human' | 'robot' | 'unknown' {
  const explicitRole = normalizeSenderRole(rawRole)
  if (explicitRole !== 'unknown') {
    return explicitRole
  }

  const messageType = rawMessageType.trim().toLowerCase()
  if (messageType.includes('initialmessage')) {
    return 'human'
  }
  if (messageType.includes('responsemessage')) {
    return 'robot'
  }
  return normalizeSenderRole(rawPerformedByRole)
}

function truncatePreview(raw: string, maxLength = 110): string {
  const trimmed = raw.trim()
  if (trimmed.length <= maxLength) {
    return trimmed
  }
  return `${trimmed.slice(0, maxLength - 1)}…`
}

function extractQueryErrorMessage(reason: unknown): string {
  if (reason instanceof Error && reason.message.trim().length > 0) {
    return reason.message.trim()
  }
  if (typeof reason === 'string' && reason.trim().length > 0) {
    return reason.trim()
  }
  return 'Unexpected query error.'
}

export function useReports() {
  const loading = ref(false)
  const error = ref('')
  const reportWarnings = ref<string[]>([])

  const humanParticipants = ref<ReportParticipantInteraction[]>([])
  const robotParticipants = ref<ReportParticipantInteraction[]>([])
  const mlUsage = ref<ReportMlUsage[]>([])
  const emotionTimeline = ref<ReportEmotionSample[]>([])
  const extremeEmotion = ref<ReportEmotionSample[]>([])
  const robotStates = ref<ReportStateSample[]>([])
  const displacementSummary = ref<ReportDisplacementSummary[]>([])
  const conversationMessages = ref<ReportConversationMessage[]>([])
  const conversationSessions = ref<ReportConversationSession[]>([])

  function groupEmotionTimelineByDimension(dimension: 'human-target' | 'robot-actor') {
    const groupedByEntity = new Map<
      string,
      {
        label: string
        points: Array<{
          xLabel: string
          y: number
          tag: string
          subject: string
          activity: string
          trigger: string
          confidence: number | null
          sortKey: string
        }>
      }
    >()
    const labelToEntities = new Map<string, Set<string>>()

    for (const row of emotionTimeline.value) {
      if (dimension === 'human-target' && !isEmotionTargetHuman(row)) {
        continue
      }
      if (dimension === 'robot-actor' && !isEmotionActorRobot(row)) {
        continue
      }

      const intensity = normalizePercent(row.intensity)
      const confidence = normalizePercent(row.confidence)
      if (intensity === null) {
        continue
      }

      const entityKey =
        dimension === 'human-target'
          ? row.targetEntity || row.targetLabel || row.sourceActivity || 'unknown_target'
          : row.performedBy || row.performedByLabel || row.sourceActivity || 'unknown_robot'
      const baseLabel =
        (
          dimension === 'human-target'
            ? row.targetLabel || compactUri(entityKey)
            : row.performedByLabel || compactUri(entityKey)
        ).trim() || compactUri(entityKey)

      if (!labelToEntities.has(baseLabel)) {
        labelToEntities.set(baseLabel, new Set<string>())
      }
      labelToEntities.get(baseLabel)?.add(entityKey)

      if (!groupedByEntity.has(entityKey)) {
        groupedByEntity.set(entityKey, {
          label: baseLabel,
          points: [],
        })
      }

      groupedByEntity.get(entityKey)?.points.push({
        xLabel: formatUtcTimestamp(row.t).replace(' UTC', ''),
        y: intensity,
        tag: normalizeEmotionLabel(row.category),
        subject: baseLabel,
        activity: dimension === 'human-target' ? `Emotion analysis for ${baseLabel}` : `Emotion analysis by ${baseLabel}`,
        trigger: resolveEmotionTrigger(row),
        confidence,
        sortKey: row.t,
      })
    }

    for (const group of groupedByEntity.values()) {
      group.points.sort((a, b) => a.sortKey.localeCompare(b.sortKey))
    }

    const ordered = Array.from(groupedByEntity.entries()).sort(([, left], [, right]) => left.label.localeCompare(right.label))
    const grouped = new Map<
      string,
      Array<{
        xLabel: string
        y: number
        tag: string
        subject: string
        activity: string
        trigger: string
        confidence: number | null
        sortKey: string
      }>
    >()

    for (const [entityKey, group] of ordered) {
      const duplicatedLabel = (labelToEntities.get(group.label)?.size ?? 0) > 1
      const participantBase = duplicatedLabel ? `${group.label} (${compactUri(entityKey)})` : group.label
      const icon = dimension === 'robot-actor' ? '🤖' : '🧑'
      const participant = decorateParticipant(participantBase, icon) || participantBase
      grouped.set(participant, group.points)
    }

    return grouped
  }

  const emotionTimelineByHumanParticipant = computed(() => groupEmotionTimelineByDimension('human-target'))
  const emotionTimelineByRobotParticipant = computed(() => groupEmotionTimelineByDimension('robot-actor'))

  const maxEmotionIntensity = computed<number | null>(() => {
    let maxValue: number | null = null
    for (const row of emotionTimeline.value) {
      const intensity = normalizeRatio(row.intensity)
      if (intensity === null) {
        continue
      }
      maxValue = maxValue === null ? intensity : Math.max(maxValue, intensity)
    }
    return maxValue
  })

  const extremeEmotionBars = computed(() => {
    const counters = new Map<string, number>()
    for (const row of extremeEmotion.value) {
      const emotion = normalizeEmotionLabel(row.category)
      counters.set(emotion, (counters.get(emotion) ?? 0) + 1)
    }
    return Array.from(counters.entries())
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
  })

  async function loadAllReports(): Promise<void> {
    loading.value = true
    error.value = ''
    reportWarnings.value = []

    try {
      const queryPlan = [
        { label: 'Participants (humans)', query: reportQueries.participantsHumans },
        { label: 'Participants (robots)', query: reportQueries.participantsRobots },
        { label: 'ML usage', query: reportQueries.mlUsage },
        { label: 'Emotion timeline', query: reportQueries.emotionTimeline },
        { label: 'Extreme emotions', query: reportQueries.extremeEmotion },
        { label: 'Robot state', query: reportQueries.robotState },
        { label: 'Conversation history', query: reportQueries.conversationHistory },
      ] as const

      const settledResults = await Promise.allSettled(queryPlan.map((item) => runSelectQuery(item.query)))

      const getRows = (index: number): Array<Record<string, string>> => {
        const result = settledResults[index]
        const planItem = queryPlan[index]
        if (!result || !planItem) {
          return []
        }
        if (result.status === 'fulfilled') {
          return result.value
        }
        reportWarnings.value.push(`${planItem.label}: ${extractQueryErrorMessage(result.reason)}`)
        return []
      }

      const humanParticipantsRows = getRows(0)
      const robotParticipantsRows = getRows(1)
      const mlRows = getRows(2)
      const emotionRows = getRows(3)
      const extremeRows = getRows(4)
      const stateRows = getRows(5)
      const conversationRows = getRows(6)

      humanParticipants.value = humanParticipantsRows
        .map((row) => ({
          participant: decorateParticipant(row.participant ?? '', '🧑'),
          interactedWith: decorateParticipants(row.interactedRobots ?? '', '🤖'),
        }))
        .filter((row) => row.participant.length > 0)

      robotParticipants.value = robotParticipantsRows
        .map((row) => ({
          participant: decorateParticipant(row.participant ?? '', '🤖'),
          interactedWith: mergeParticipantLists(
            decorateParticipants(row.interactedHumans ?? '', '🧑'),
            decorateParticipants(row.interactedRobots ?? '', '🤖'),
          ),
        }))
        .filter((row) => row.participant.length > 0)

      mlUsage.value = mlRows.map((row) => ({
        activity: compactUri(row.activity ?? ''),
        activityType: compactUri(row.activityType ?? ''),
        usedBy: row.usedByName ?? compactUri(row.usedBy ?? ''),
        usedAt: formatUtcTimestamp(row.startedAt ?? ''),
        model: compactUri(row.model ?? ''),
        modelLabel: row.modelLabel ?? '',
        version: row.version ?? '',
        dataset: compactUri(row.dataset ?? ''),
        datasetLabel: row.datasetLabel ?? '',
        score: formatRatioAsPercent(row.score ?? ''),
      }))

      emotionTimeline.value = emotionRows.map((row) => ({
        t: row.t ?? '',
        sourceActivity: compactUri(row.sourceActivity ?? ''),
        sourceActivityLabel: row.sourceActivityLabel ?? '',
        performedBy: firstPipeValue(row.performedBy ?? ''),
        performedByLabel: firstPipeValue(row.performedByLabel ?? '') || compactUri(row.performedBy ?? ''),
        performedByType: firstPipeValue(row.performedByType ?? ''),
        triggerActivity: compactUri(row.triggerActivity ?? ''),
        triggerActivityLabel: row.triggerActivityLabel ?? '',
        triggerEntity: compactUri(row.triggerEntity ?? ''),
        triggerEntityLabel: row.triggerEntityLabel ?? '',
        triggerMessageText: row.triggerMessageText ?? '',
        targetEntity: firstPipeValue(row.targetEntity ?? ''),
        targetType: firstPipeValue(row.targetType ?? ''),
        targetLabel: firstPipeValue(row.targetLabel ?? '') || compactUri(row.targetEntity ?? ''),
        category: row.category ?? '',
        intensity: row.intensity ?? '',
        confidence: row.confidence ?? '',
      }))

      extremeEmotion.value = extremeRows.map((row) => ({
        t: row.t ?? '',
        sourceActivity: compactUri(row.sourceActivity ?? ''),
        sourceActivityLabel: '',
        performedBy: '',
        performedByLabel: '',
        performedByType: '',
        triggerActivity: '',
        triggerActivityLabel: '',
        triggerEntity: '',
        triggerEntityLabel: '',
        triggerMessageText: '',
        targetEntity: firstPipeValue(row.targetEntity ?? ''),
        targetType: firstPipeValue(row.targetType ?? ''),
        targetLabel: firstPipeValue(row.targetLabel ?? '') || compactUri(row.targetEntity ?? ''),
        category: row.category ?? '',
        intensity: row.intensity ?? '',
        confidence: row.confidence ?? '',
      }))

      robotStates.value = stateRows.map((row) => ({
        robot: row.robot ?? '',
        robotName: row.robotName ?? compactUri(row.robot ?? ''),
        t: row.t ?? '',
        location: compactUri(row.location ?? ''),
      }))

      buildConversationMessages(conversationRows)
      buildConversationSessions()
      buildDisplacementSummary()

      if (reportWarnings.value.length === queryPlan.length) {
        error.value = 'Could not load any report block. Check backend query capabilities and dataset semantics.'
      }
    } catch (backendError) {
      error.value = backendError instanceof Error ? backendError.message : 'Failed to load reports.'
    } finally {
      loading.value = false
    }
  }

  function buildDisplacementSummary(): void {
    const grouped = new Map<string, ReportStateSample[]>()
    for (const row of robotStates.value) {
      const key = row.robotName || compactUri(row.robot)
      if (!grouped.has(key)) {
        grouped.set(key, [])
      }
      grouped.get(key)?.push(row)
    }

    const summary: ReportDisplacementSummary[] = []
    for (const [robot, samples] of grouped.entries()) {
      const ordered = [...samples].sort((a, b) => a.t.localeCompare(b.t))
      const rawPath = ordered.map((row) => row.location)
      const transitionPath: string[] = []
      for (const location of rawPath) {
        if (transitionPath.length === 0 || transitionPath[transitionPath.length - 1] !== location) {
          transitionPath.push(location)
        }
      }
      const changes = Math.max(transitionPath.length - 1, 0)
      const observedPath =
        transitionPath.length === 0 ? '' : changes === 0 ? (transitionPath[0] ?? '') : transitionPath.join(' -> ')

      summary.push({
        robot,
        samples: rawPath.length,
        locationChanges: changes,
        path: observedPath,
      })
    }

    summary.sort((a, b) => a.robot.localeCompare(b.robot))
    displacementSummary.value = summary
  }

  function buildConversationMessages(rows: Array<Record<string, string>>): void {
    const unique = new Map<string, ReportConversationMessage>()

    rows.forEach((row, index) => {
      const messageId = firstPipeValue(row.message ?? '') || `message-${index + 1}`
      const human = firstPipeValue(row.human ?? '')
      const robot = firstPipeValue(row.robot ?? '')
      const humanLabel = firstPipeValue(row.humanLabel ?? '') || compactUri(human)
      const robotLabel = firstPipeValue(row.robotLabel ?? '') || compactUri(robot)
      const pairKey = `${human}__${robot}`
      const messageType = firstPipeValue(row.messageType ?? '')
      const senderRole = inferSenderRole(
        firstPipeValue(row.senderRole ?? ''),
        messageType,
        firstPipeValue(row.performedByRole ?? ''),
      )
      const t = firstPipeValue(row.t ?? '')
      const text = row.text ?? ''
      const normalizedMessageType = messageType || compactUri(row.messageType ?? '')

      if (!human || !robot || !text.trim()) {
        return
      }

      const senderLabel = senderRole === 'human' ? humanLabel : senderRole === 'robot' ? robotLabel : robotLabel || humanLabel
      const message: ReportConversationMessage = {
        id: messageId,
        pairKey,
        human,
        humanLabel,
        robot,
        robotLabel,
        t,
        text,
        senderRole,
        senderLabel,
        messageType: normalizedMessageType,
      }

      const uniqueKey = `${pairKey}__${messageId}`
      if (!unique.has(uniqueKey)) {
        unique.set(uniqueKey, message)
      }
    })

    const ordered = Array.from(unique.values())
    ordered.sort((a, b) => {
      if (a.pairKey !== b.pairKey) {
        return a.pairKey.localeCompare(b.pairKey)
      }

      const aTime = parseTimestampMs(a.t)
      const bTime = parseTimestampMs(b.t)
      if (aTime !== null && bTime !== null && aTime !== bTime) {
        return aTime - bTime
      }
      if (aTime !== null && bTime === null) {
        return -1
      }
      if (aTime === null && bTime !== null) {
        return 1
      }
      if (a.t !== b.t) {
        return a.t.localeCompare(b.t)
      }
      return a.id.localeCompare(b.id)
    })

    conversationMessages.value = ordered
  }

  function buildConversationSessions(): void {
    const sessions: ReportConversationSession[] = []
    const pairCounters = new Map<string, number>()
    const lastByPair = new Map<
      string,
      {
        session: ReportConversationSession
        lastTimestampMs: number | null
      }
    >()

    for (const message of conversationMessages.value) {
      const currentTimeMs = parseTimestampMs(message.t)
      const lastSessionByPair = lastByPair.get(message.pairKey)
      const canAppendToCurrentSession =
        lastSessionByPair !== undefined &&
        lastSessionByPair.lastTimestampMs !== null &&
        currentTimeMs !== null &&
        currentTimeMs >= lastSessionByPair.lastTimestampMs &&
        currentTimeMs - lastSessionByPair.lastTimestampMs < CONVERSATION_GAP_MS

      let session: ReportConversationSession
      if (canAppendToCurrentSession && lastSessionByPair) {
        session = lastSessionByPair.session
      } else {
        const pairCount = (pairCounters.get(message.pairKey) ?? 0) + 1
        pairCounters.set(message.pairKey, pairCount)
        session = {
          id: `${message.pairKey}::${pairCount}`,
          pairKey: message.pairKey,
          human: message.human,
          humanLabel: message.humanLabel,
          robot: message.robot,
          robotLabel: message.robotLabel,
          startedAt: message.t,
          endedAt: message.t,
          messageCount: 0,
          preview: '',
          messages: [],
        }
        sessions.push(session)
      }

      session.messages.push(message)
      session.messageCount = session.messages.length
      if (!session.startedAt && message.t) {
        session.startedAt = message.t
      }
      if (message.t) {
        session.endedAt = message.t
      }
      if (!session.preview) {
        session.preview = truncatePreview(message.text)
      }

      lastByPair.set(message.pairKey, {
        session,
        lastTimestampMs: currentTimeMs,
      })
    }

    sessions.sort((a, b) => {
      const aTime = parseTimestampMs(a.endedAt || a.startedAt)
      const bTime = parseTimestampMs(b.endedAt || b.startedAt)
      if (aTime !== null && bTime !== null && aTime !== bTime) {
        return bTime - aTime
      }
      if (aTime !== null && bTime === null) {
        return -1
      }
      if (aTime === null && bTime !== null) {
        return 1
      }
      return a.id.localeCompare(b.id)
    })

    conversationSessions.value = sessions
  }

  return {
    loading,
    error,
    reportWarnings,
    humanParticipants,
    robotParticipants,
    mlUsage,
    emotionTimeline,
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
  }
}
