import httpClient from '@/core/api/httpClient'
import { parseSelectResultTurtle, type SelectRow } from '@/shared/rdf/parseSelectResult'

export type TtlInsertPayload = {
  ttl_content: string
  user?: string
}

export type TtlInsertResponse = {
  message: string
  log_id: string
}

export type TtlValidationIssue = {
  severity: 'error' | 'warning'
  code: string
  message: string
  focus_node?: string | null
  predicate?: string | null
  value?: string | null
}

export type TtlValidationResponse = {
  valid: boolean
  syntax_ok: boolean
  semantic_ok: boolean
  triple_count: number
  issues: TtlValidationIssue[]
}

export type QueryValidationResponse = {
  valid: boolean
  query_kind: string
  allows_update_execution: boolean
  message: string
}

export type SharedContextResolvePayload = {
  event_kind: string
  observed_at: string
  subject_uri?: string
  modality?: string
  text?: string
  observation_uri?: string
  robot_uri?: string
  time_window_seconds?: number
}

export type SharedContextResolveResponse = {
  shared_context_uri: string
  status: 'matched' | 'created' | 'ambiguous'
  confidence: number
  resolver_version: string
  candidate_count: number
  matched_candidate_uri?: string | null
  close_candidates: string[]
  score_breakdown: Record<string, number>
}

export type SharedContextReconcileResponse = {
  scanned_ambiguous: number
  merged_count: number
  mappings: Record<string, string>
  resolver_version: string
  pending_cases: number
}

export type SharedContextStatsResponse = {
  resolver_version: string
  active_contexts: number
  ambiguous_contexts: number
  merged_contexts: number
  aliases: number
}

export type SharedContextReviewObservation = {
  observed_at: string
  subject_uri: string | null
  modality: string | null
  text: string | null
  observation_uri: string | null
  robot_uri: string | null
}

export type SharedContextReviewRecord = {
  uri: string
  event_kind: string
  status: 'active' | 'ambiguous' | 'merged'
  observed_at: string
  subject_uri: string | null
  modality: string | null
  canonical_text: string
  observation_count: number
  observations: SharedContextReviewObservation[]
}

export type SharedContextReviewCandidate = {
  context_uri: string
  score: number
  score_breakdown: Record<string, number>
}

export type SharedContextReviewCase = {
  case_id: string
  source_context_uri: string
  candidates: SharedContextReviewCandidate[]
  status: 'pending' | 'accepted' | 'rejected'
  created_at: string
  decided_at: string | null
  selected_context_uri: string | null
}

export type SharedContextReviewQueueResponse = {
  resolver_version: string
  unresolved_count: number
  pending_count: number
  unresolved_contexts: SharedContextReviewRecord[]
  contexts: SharedContextReviewRecord[]
  pending_cases: SharedContextReviewCase[]
}

export type SharedContextReviewDecisionResponse = {
  case_id: string
  status: 'accepted' | 'rejected'
  source_context_uri: string
  selected_context_uri: string | null
  resulting_context_uri: string | null
  resolver_version: string
}

export type ReadyResponse = {
  ready: boolean
  virtuoso: boolean
}

export type AuthModeResponse = {
  auth_enabled: boolean
}

export type ServerLogEntry = {
  timestamp: string | null
  level: string | null
  logger: string | null
  request_id: string | null
  actor: string | null
  origin_ip: string | null
  message: string
  raw: string
}

export type ServerLogsFilters = {
  limit: number
  level: string | null
  contains: string | null
}

export type ServerLogsResponse = {
  log_file: string
  count: number
  filters: ServerLogsFilters
  entries: ServerLogEntry[]
}

export type ServerLogsParams = {
  limit?: number
  level?: string
  contains?: string
}

function fromJsonLikePayload(payload: unknown): string {
  if (typeof payload === 'string') {
    return payload
  }

  if (typeof payload === 'object' && payload !== null) {
    const data = payload as Record<string, unknown>
    const detail = typeof data.detail === 'string' ? data.detail : null
    const message = typeof data.message === 'string' ? data.message : null
    if (detail || message) {
      throw new Error(detail ?? message ?? 'Backend query failed.')
    }
  }

  throw new Error('Unexpected /query response format. Expected text/turtle.')
}

function normalizeQueryResponse(data: unknown): string {
  if (typeof data !== 'string') {
    return fromJsonLikePayload(data)
  }

  const trimmed = data.trim()
  if (!trimmed) {
    return data
  }

  const mightBeJson =
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith('{') && trimmed.endsWith('}'))

  if (!mightBeJson) {
    return data
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown
    return fromJsonLikePayload(parsed)
  } catch {
    return data
  }
}

export async function getLiveHealth(): Promise<{ live: boolean }> {
  const { data } = await httpClient.get<{ live: boolean }>('/healthz/live')
  return data
}

export async function getReadyHealth(): Promise<ReadyResponse> {
  const { data } = await httpClient.get<ReadyResponse>('/healthz/ready')
  return data
}

export async function getAuthMode(): Promise<AuthModeResponse> {
  const { data } = await httpClient.get<AuthModeResponse>('/auth/mode')
  return data
}

export async function insertTtl(payload: TtlInsertPayload): Promise<TtlInsertResponse> {
  const { data } = await httpClient.post<TtlInsertResponse>('/ttl', payload)
  return data
}

export async function validateTtl(payload: TtlInsertPayload): Promise<TtlValidationResponse> {
  const { data } = await httpClient.post<TtlValidationResponse>('/ttl/validate', payload)
  return data
}

export async function getEventsTurtle(): Promise<string> {
  const { data } = await httpClient.get<string>('/events', {
    responseType: 'text',
  })
  return data
}

export async function runQueryTurtle(query: string): Promise<string> {
  const { data } = await httpClient.get<string>('/query', {
    params: { query },
    responseType: 'text',
  })
  return normalizeQueryResponse(data)
}

export async function validateQuery(query: string): Promise<QueryValidationResponse> {
  const { data } = await httpClient.post<QueryValidationResponse>('/query/validate', {
    query,
  })
  return data
}

export async function runSelectQuery(query: string): Promise<SelectRow[]> {
  const turtle = await runQueryTurtle(query)
  return parseSelectResultTurtle(turtle)
}

export async function deleteAllTtls(user?: string): Promise<{ message: string }> {
  const { data } = await httpClient.post<{ message: string }>('/ttl/delete_all', {
    user,
  })
  return data
}

export async function resolveSharedContext(
  payload: SharedContextResolvePayload,
): Promise<SharedContextResolveResponse> {
  const { data } = await httpClient.post<SharedContextResolveResponse>('/shared-context/resolve', payload)
  return data
}

export async function reconcileSharedContext(): Promise<SharedContextReconcileResponse> {
  const { data } = await httpClient.post<SharedContextReconcileResponse>('/shared-context/reconcile')
  return data
}

export async function getSharedContextStats(): Promise<SharedContextStatsResponse> {
  const { data } = await httpClient.get<SharedContextStatsResponse>('/shared-context/stats')
  return data
}

export async function getSharedContextReviewQueue(): Promise<SharedContextReviewQueueResponse> {
  const { data } = await httpClient.get<SharedContextReviewQueueResponse>('/shared-context/review/pending')
  return data
}

export async function acceptSharedContextReviewCase(
  caseId: string,
  targetContextUri: string,
): Promise<SharedContextReviewDecisionResponse> {
  const { data } = await httpClient.post<SharedContextReviewDecisionResponse>(
    `/shared-context/review/${encodeURIComponent(caseId)}/accept`,
    { target_context_uri: targetContextUri },
  )
  return data
}

export async function rejectSharedContextReviewCase(
  caseId: string,
): Promise<SharedContextReviewDecisionResponse> {
  const { data } = await httpClient.post<SharedContextReviewDecisionResponse>(
    `/shared-context/review/${encodeURIComponent(caseId)}/reject`,
  )
  return data
}

export async function getServerLogs(params: ServerLogsParams): Promise<ServerLogsResponse> {
  const { data } = await httpClient.get<ServerLogsResponse>('/logs/server', {
    params,
  })
  return data
}
