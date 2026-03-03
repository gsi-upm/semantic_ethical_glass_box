import { describe, expect, it } from 'vitest'

import { highlightTurtle } from '@/shared/rdf/highlightTurtle'

describe('highlightTurtle', () => {
  it('escapes html and wraps turtle tokens with classes', () => {
    const source = '@prefix ex: <https://example.org/> .\nex:a ex:b "text" . # comment'
    const html = highlightTurtle(source)

    expect(html).toContain('ttl-token-directive')
    expect(html).toContain('ttl-token-uri')
    expect(html).toContain('ttl-token-prefixed')
    expect(html).toContain('ttl-token-string')
    expect(html).toContain('ttl-token-comment')
    expect(html).toContain('&lt;https://example.org/&gt;')
  })
})
