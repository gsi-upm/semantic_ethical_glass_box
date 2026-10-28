import { describe, expect, it } from 'vitest'

import { parseSelectResultTurtle } from '@/shared/rdf/parseSelectResult'

describe('parseSelectResultTurtle', () => {
  it('parses row-shaped turtle results into table entries', () => {
    const ttl = `
      @prefix ex: <http://example.org/> .
      @prefix result: <http://example.org/> .

      _:row1 a result:Result ;
        result:s <https://example.org/robot/ari> ;
        result:p <https://example.org/name> ;
        result:o "ARI" .
    `

    const rows = parseSelectResultTurtle(ttl)
    expect(rows).toEqual([
      {
        s: 'https://example.org/robot/ari',
        p: 'https://example.org/name',
        o: 'ARI',
      },
    ])
  })

  it('joins repeated variable bindings with separator', () => {
    const ttl = `
      @prefix result: <http://example.org/> .
      _:row1 a result:Result ;
        result:o "A" ;
        result:o "B" .
    `
    const rows = parseSelectResultTurtle(ttl)
    expect(rows).toEqual([{ o: 'A | B' }])
  })
})
