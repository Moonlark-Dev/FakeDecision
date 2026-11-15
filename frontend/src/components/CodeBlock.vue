<script setup lang="ts">
import CopyButton from './CopyButton.vue'

withDefaults(defineProps<{ code: string; label?: string; maxHeight?: string }>(), {
  label: '',
  maxHeight: '',
})
</script>

<template>
  <div class="code-shell">
    <div v-if="label" class="code-head">
      <span class="mono tiny muted">{{ label }}</span>
      <CopyButton :text="code" />
    </div>
    <div class="code-block" :style="{ maxHeight: maxHeight || undefined }">
      <CopyButton v-if="!label" class="code-copy" :text="code" />
      <pre><code>{{ code }}</code></pre>
    </div>
  </div>
</template>

<style scoped>
.code-shell {
  min-width: 0;
}

.code-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 2px 2px 7px;
}

.code-head :deep(.btn) {
  min-height: 26px;
  font-size: 11px;
}

.code-block {
  border-radius: 10px;
}
</style>
