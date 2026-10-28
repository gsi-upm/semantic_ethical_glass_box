<template>
  <header class="topbar">
    <div class="brand-wrap">
      <img :src="segbMark" alt="SEGB mark" class="brand-mark" />
      <div class="brand-copy">
        <p class="brand-title">SEGB</p>
        <p class="brand-subtitle">Semantic Ethical Glass Box</p>
      </div>
    </div>

    <div class="session-info">
      <span class="pill" :class="sessionTone">{{ sessionText }}</span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useAuthModeStore } from '@/core/auth/authModeStore'
import { useSessionStore } from '@/core/auth/sessionStore'
import segbMark from '@/assets/segb-mark.png'

const session = useSessionStore()
const authMode = useAuthModeStore()

onMounted(() => {
  void authMode.ensureLoaded()
})

const sessionTone = computed(() => {
  if (authMode.isAuthDisabled) {
    return 'ok'
  }
  if (!session.token) {
    return 'warning'
  }
  if (session.isExpired) {
    return 'error'
  }
  return 'ok'
})

const sessionText = computed(() => {
  if (authMode.isAuthDisabled) {
    return 'Authentication disabled: all roles active'
  }
  if (!session.token) {
    return 'No token in session'
  }
  if (session.isExpired) {
    return 'Token expired'
  }
  const user = session.decodedToken?.username ?? 'token-set'
  return `Token active: ${user}`
})
</script>

<style scoped>
.topbar {
  border: 1px solid #dde6ee;
  border-radius: 12px;
  background: #ffffff;
  color: var(--ink-900);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.06),
    0 6px 14px rgba(2, 45, 75, 0.05);
  padding: 0.95rem 1.05rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.1rem;
  min-height: 120px;
}

.brand-wrap {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
}

.brand-mark {
  width: auto;
  height: clamp(81px, 9.2vw, 108px);
  flex: 0 0 auto;
  display: block;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-title {
  margin: 0;
  font-size: clamp(1.5rem, 2.28vw, 1.77rem);
  font-weight: 1000;
  line-height: 1;
  letter-spacing: 0.01em;
  color: #0b5ea5;
}

.brand-subtitle {
  margin: 0.15rem 0 0;
  font-size: clamp(0.93rem, 1.21vw, 1.06rem);
  color: var(--ink-500);
  font-weight:1000;
  line-height: 1.2;
}

.session-info {
  display: flex;
  flex-direction: row;
  gap: 0.4rem;
  align-items: center;
}

.pill {
  font-size: clamp(0.86rem, 0.95vw, 0.96rem);
  font-weight: 650;
  border-radius: 999px;
  padding: 0.48rem 0.9rem;
  border: 1px solid transparent;
  line-height: 1.15;
  white-space: nowrap;
  box-shadow: 0 1px 3px rgba(2, 45, 75, 0.08);
}

.pill.ok {
  background: #edf6ff;
  color: #0a5b9f;
  border-color: #c7e2f8;
}

.pill.warning {
  background: #fff8dc;
  color: #8a5a00;
  border-color: #f2dc9a;
}

.pill.error {
  background: #ffecec;
  color: #a01c1c;
  border-color: #f4c0c0;
}

@media (max-width: 920px) {
  .topbar {
    flex-direction: column;
    align-items: flex-start;
    min-height: unset;
    gap: 0.55rem;
  }

  .session-info {
    width: 100%;
    justify-content: flex-start;
  }

  .brand-mark {
    width: auto;
    height: clamp(68px, 16.5vw, 86px);
  }

  .brand-title {
    font-size: clamp(1.37rem, 6.33vw, 1.56rem);
  }

  .brand-subtitle {
    font-size: clamp(0.89rem, 4.43vw, 1.01rem);
  }
}
</style>
