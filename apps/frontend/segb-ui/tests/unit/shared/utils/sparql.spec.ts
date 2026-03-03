import { describe, expect, it } from 'vitest'

import { getSparqlQueryKind, isReadOnlySparql } from '@/shared/utils/sparql'

describe('sparql helpers', () => {
  it('detects read-only query verbs', () => {
    expect(isReadOnlySparql('SELECT ?s WHERE { ?s ?p ?o }')).toBe(true)
    expect(isReadOnlySparql('construct { ?s ?p ?o } where { ?s ?p ?o }')).toBe(true)
  })

  it('rejects update queries', () => {
    expect(isReadOnlySparql('INSERT DATA { <a> <b> <c> . }')).toBe(false)
    expect(isReadOnlySparql('DELETE WHERE { ?s ?p ?o }')).toBe(false)
  })

  it('extracts query kind from valid read-only queries', () => {
    expect(getSparqlQueryKind('ASK { ?s ?p ?o }')).toBe('ask')
    expect(getSparqlQueryKind('DESCRIBE ?s WHERE { ?s ?p ?o }')).toBe('describe')
    expect(getSparqlQueryKind('INSERT DATA { <a> <b> <c> . }')).toBe('unknown')
  })
})
