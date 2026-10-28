import { defineStore } from 'pinia'

import { env } from '@/core/config/env'
import { decodeTokenPayload, isTokenExpired, type DecodedToken } from '@/core/auth/token'
import { useAuthModeStore } from '@/core/auth/authModeStore'
import { ALL_ROLES, normalizeRole, type Role } from '@/core/auth/roles'

type SessionState = {
  token: string
}

function loadStoredToken(): string {
  const value = sessionStorage.getItem(env.tokenStorageKey)
  return value ?? ''
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    token: loadStoredToken(),
  }),
  getters: {
    isAuthenticated: (state): boolean => state.token.length > 0,
    decodedToken: (state): DecodedToken | null => {
      if (!state.token) {
        return null
      }
      return decodeTokenPayload(state.token)
    },
    isExpired: (state): boolean => {
      if (!state.token) {
        return false
      }
      return isTokenExpired(state.token)
    },
    roles(): string[] {
      return this.decodedToken?.roles ?? []
    },
    tokenRoles(): Role[] {
      const deduplicated: Role[] = []
      for (const rawRole of this.roles) {
        const role = normalizeRole(rawRole)
        if (!role || deduplicated.includes(role)) {
          continue
        }
        deduplicated.push(role)
      }
      return deduplicated
    },
    effectiveRoles(): Role[] {
      const authMode = useAuthModeStore()
      if (authMode.isAuthDisabled) {
        return [...ALL_ROLES]
      }
      if (this.isExpired) {
        return []
      }
      return this.tokenRoles
    },
  },
  actions: {
    setToken(token: string): void {
      const trimmed = token.trim()
      this.token = trimmed
      if (trimmed) {
        sessionStorage.setItem(env.tokenStorageKey, trimmed)
      } else {
        sessionStorage.removeItem(env.tokenStorageKey)
      }
    },
    clearToken(): void {
      this.token = ''
      sessionStorage.removeItem(env.tokenStorageKey)
    },
    hasAnyRole(allowed: readonly Role[]): boolean {
      if (allowed.length === 0) {
        return true
      }
      return this.effectiveRoles.some((role) => allowed.includes(role))
    },
  },
})
