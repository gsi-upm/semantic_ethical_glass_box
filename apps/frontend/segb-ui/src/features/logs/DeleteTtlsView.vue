<template>
  <div class="stack">
    <BaseCard
      title="Delete TTLs"
      subtitle="Clear the current Knowledge Graph (KG)."
    >
      <label class="field">
        <input
          v-model="confirmationText"
          class="text-input"
          type="text"
          placeholder="Type DELETE to enable deletion"
          spellcheck="false"
          autocomplete="off"
        />
      </label>

      <div class="actions">
        <button class="btn danger" :disabled="loading || !isConfirmationValid" @click="clearKnowledgeGraph">
          {{ loading ? 'Clearing…' : 'Delete all TTLs' }}
        </button>
      </div>

      <StatusBanner v-if="statusMessage" tone="success" :message="statusMessage" />
      <StatusBanner v-if="errorMessage" tone="error" :message="errorMessage" />
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import BaseCard from '@/shared/ui/BaseCard.vue'
import StatusBanner from '@/shared/ui/StatusBanner.vue'
import { deleteAllTtls } from '@/core/api/segbApi'
import { normalizeApiError } from '@/core/api/error'

const loading = ref(false)
const statusMessage = ref('')
const errorMessage = ref('')
const confirmationText = ref('')
const isConfirmationValid = computed(() => confirmationText.value.trim() === 'DELETE')

async function clearKnowledgeGraph(): Promise<void> {
  if (!isConfirmationValid.value) {
    return
  }

  loading.value = true
  statusMessage.value = ''
  errorMessage.value = ''

  try {
    const response = await deleteAllTtls()
    statusMessage.value = response.message
    confirmationText.value = ''
  } catch (unknownError) {
    const normalized = normalizeApiError(unknownError)
    errorMessage.value = normalized.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.text-input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.6rem 0.7rem;
  background: #ffffff;
}

.actions {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
}
</style>
