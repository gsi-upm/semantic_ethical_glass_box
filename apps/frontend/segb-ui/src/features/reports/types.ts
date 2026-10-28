export type ReportParticipantInteraction = {
  participant: string
  interactedWith: string
}

export type ReportMlUsage = {
  activity: string
  activityType: string
  usedBy: string
  usedAt: string
  model: string
  modelLabel: string
  version: string
  dataset: string
  datasetLabel: string
  score: string
}

export type ReportEmotionSample = {
  t: string
  sourceActivity: string
  sourceActivityLabel: string
  performedBy: string
  performedByLabel: string
  performedByType: string
  triggerActivity: string
  triggerActivityLabel: string
  triggerEntity: string
  triggerEntityLabel: string
  triggerMessageText: string
  targetEntity: string
  targetType: string
  targetLabel: string
  category: string
  intensity: string
  confidence: string
}

export type ReportStateSample = {
  robot: string
  robotName: string
  t: string
  location: string
}

export type ReportDisplacementSummary = {
  robot: string
  samples: number
  locationChanges: number
  path: string
}

export type ReportConversationMessage = {
  id: string
  pairKey: string
  human: string
  humanLabel: string
  robot: string
  robotLabel: string
  t: string
  text: string
  senderRole: 'human' | 'robot' | 'unknown'
  senderLabel: string
  messageType: string
}

export type ReportConversationSession = {
  id: string
  pairKey: string
  human: string
  humanLabel: string
  robot: string
  robotLabel: string
  startedAt: string
  endedAt: string
  messageCount: number
  preview: string
  messages: ReportConversationMessage[]
}
