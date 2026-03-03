import { defineStore } from 'pinia'

import { getAuthMode } from '@/core/api/segbApi'

type AuthModeState = {
  authEnabled: boolean | null
  loading: boolean
  loaded: boolean
}

let loadPromise: Promise<void> | null = null

export const useAuthModeStore = defineStore('auth-mode', {
  state: (): AuthModeState => ({
    authEnabled: null,
    loading: false,
    loaded: false,
  }),
  getters: {
    isAuthDisabled: (state): boolean => state.authEnabled === false,
    isAuthEnabled: (state): boolean => state.authEnabled !== false,
  },
  actions: {
    async refresh(): Promise<void> {
      this.loading = true
      try {
        const response = await getAuthMode()
        this.authEnabled = response.auth_enabled
      } catch {
        // Secure-by-default fallback: if mode cannot be determined, keep restricted visibility.
        this.authEnabled = true
      } finally {
        this.loaded = true
        this.loading = false
      }
    },
    async ensureLoaded(): Promise<void> {
      if (this.loaded) {
        return
      }
      if (loadPromise) {
        await loadPromise
        return
      }
      loadPromise = this.refresh().finally(() => {
        loadPromise = null
      })
      await loadPromise
    },
  },
})
