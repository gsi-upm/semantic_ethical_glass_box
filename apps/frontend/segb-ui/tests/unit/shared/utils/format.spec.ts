import { describe, expect, it } from 'vitest'

import { compactUri, formatRatioAsPercent, formatUtcTimestamp, titleCase, toNumber } from '@/shared/utils/format'

describe('format utilities', () => {
  it('compacts URI values using hash or final path segment', () => {
    expect(compactUri('https://example.org/robot/ari')).toBe('ari')
    expect(compactUri('https://example.org#Human')).toBe('Human')
    expect(compactUri(null)).toBe('')
  })

  it('formats UTC timestamps and returns input for invalid dates', () => {
    expect(formatUtcTimestamp('2026-03-01T12:00:00Z')).toContain('UTC')
    expect(formatUtcTimestamp('not-a-date')).toBe('not-a-date')
    expect(formatUtcTimestamp(undefined)).toBe('')
  })

  it('converts values to numbers when possible', () => {
    expect(toNumber('42.5')).toBe(42.5)
    expect(toNumber('abc')).toBeNull()
    expect(toNumber('')).toBeNull()
  })

  it('formats ratios as percent in 0..1 and 0..100 ranges', () => {
    expect(formatRatioAsPercent(0.52, 1)).toBe('52.0%')
    expect(formatRatioAsPercent(52, 0)).toBe('52%')
    expect(formatRatioAsPercent(120, 0)).toBe('120')
    expect(formatRatioAsPercent('bad')).toBe('bad')
  })

  it('converts snake or kebab case to title case', () => {
    expect(titleCase('shared_context-review')).toBe('Shared Context Review')
  })
})
