export type ApiError = {
  statusCode: number | null
  message: string
  details?: string
}

export function normalizeApiError(error: unknown): ApiError {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as Record<string, unknown>).response === 'object' &&
    (error as Record<string, unknown>).response !== null
  ) {
    const response = (error as Record<string, unknown>).response as Record<string, unknown>
    const statusCode = typeof response.status === 'number' ? response.status : null
    let details: string | undefined
    const rawData = response.data
    if (typeof rawData === 'string') {
      const trimmed = rawData.trim()
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
          const parsed = JSON.parse(trimmed) as Record<string, unknown>
          details = typeof parsed.detail === 'string' ? parsed.detail : typeof parsed.message === 'string' ? parsed.message : undefined
        } catch {
          details = undefined
        }
      }
    } else if (typeof rawData === 'object' && rawData !== null) {
      const data = rawData as Record<string, unknown>
      details = typeof data.detail === 'string' ? data.detail : typeof data.message === 'string' ? data.message : undefined
    }
    return {
      statusCode,
      message: details ?? 'Backend request failed.',
      details,
    }
  }

  if (error instanceof Error) {
    return {
      statusCode: null,
      message: error.message,
    }
  }

  return {
    statusCode: null,
    message: 'Unexpected frontend error.',
  }
}
