export const ALL_ROLES = ['auditor', 'logger', 'admin'] as const

export type Role = (typeof ALL_ROLES)[number]

const ALL_ROLE_SET = new Set<string>(ALL_ROLES)

export function normalizeRole(rawRole: string): Role | null {
  const normalized = rawRole.trim().toLowerCase()
  return ALL_ROLE_SET.has(normalized) ? (normalized as Role) : null
}
