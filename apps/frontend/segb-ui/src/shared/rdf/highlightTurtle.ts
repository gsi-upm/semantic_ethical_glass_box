const TOKEN_PREFIX = '__TTL_HL_TOKEN_'

type TokenRule = {
  className: string
  regex: RegExp
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function stashPattern(input: string, rule: TokenRule, tokenStore: string[]): string {
  return input.replace(rule.regex, (match) => {
    const tokenId = `${TOKEN_PREFIX}${tokenStore.length}__`
    tokenStore.push(`<span class="${rule.className}">${match}</span>`)
    return tokenId
  })
}

function restoreTokens(input: string, tokenStore: string[]): string {
  let output = input
  tokenStore.forEach((token, index) => {
    output = output.split(`${TOKEN_PREFIX}${index}__`).join(token)
  })
  return output
}

export function highlightTurtle(ttl: string): string {
  const escaped = escapeHtml(ttl)
  const tokenStore: string[] = []
  const rules: TokenRule[] = [
    {
      className: 'ttl-token-string',
      regex: /"(?:\\.|[^"\\])*"(?:\^\^[A-Za-z_][\w.-]*:[A-Za-z_][\w.-]*|@[a-zA-Z-]+)?/g,
    },
    {
      className: 'ttl-token-uri',
      regex: /&lt;[^\n]*?&gt;/g,
    },
    {
      className: 'ttl-token-comment',
      regex: /#[^\n]*/g,
    },
    {
      className: 'ttl-token-directive',
      regex: /@prefix|@base/g,
    },
    {
      className: 'ttl-token-prefixed',
      regex: /\b[A-Za-z_][\w-]*:[A-Za-z_][\w.-]*\b|\b[A-Za-z_][\w-]*:(?=\s)/g,
    },
    {
      className: 'ttl-token-number',
      regex: /\b-?\d+(?:\.\d+)?\b/g,
    },
  ]

  let highlighted = escaped
  for (const rule of rules) {
    highlighted = stashPattern(highlighted, rule, tokenStore)
  }
  return restoreTokens(highlighted, tokenStore)
}
