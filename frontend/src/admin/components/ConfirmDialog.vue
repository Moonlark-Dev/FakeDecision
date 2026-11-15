<script setup lang="ts">
import { Loader2, TriangleAlert } from 'lucide-vue-next'
import BaseModal from '@/components/BaseModal.vue'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    detail?: string
    confirmLabel?: string
    tone?: 'danger' | 'primary'
    busy?: boolean
  }>(),
  {
    detail: '',
    confirmLabel: 'Confirm',
    tone: 'danger',
    busy: false,
  },
)

const emit = defineEmits<{ close: []; confirm: [] }>()
</script>

<template>
  <BaseModal :open="open" :title="title" width="440px" @close="emit('close')">
    <div class="adm-confirm">
      <span class="adm-confirm-icon" :class="`is-${tone}`"><TriangleAlert :size="18" /></span>
      <div class="adm-confirm-copy">
        <p class="adm-confirm-message">{{ message }}</p>
        <p v-if="detail" class="adm-confirm-detail">{{ detail }}</p>
      </div>
    </div>
    <template #footer>
      <button type="button" class="btn btn-sm" :disabled="busy" @click="emit('close')">Cancel</button>
      <button
        type="button"
        class="btn btn-sm"
        :class="tone === 'danger' ? 'btn-danger' : 'btn-primary'"
        :disabled="busy"
        @click="emit('confirm')"
      >
        <Loader2 v-if="busy" :size="13" class="adm-spin" />
        <span>{{ confirmLabel }}</span>
      </button>
    </template>
  </BaseModal>
</template>
