<script setup lang="ts">
import { Inbox } from 'lucide-vue-next'
withDefaults(defineProps<{ title: string; description?: string }>(), { description: '' })
</script>

<template>
  <div class="empty">
    <div class="empty-icon"><Inbox :size="18" /></div>
    <p class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 44px 20px;
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  margin-bottom: 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface-2);
  color: var(--muted);
}

.empty-title {
  color: var(--ink-soft);
  font-size: 13.5px;
  font-weight: 560;
}

.empty-description {
  max-width: 380px;
  margin-top: 5px;
  color: var(--muted);
  font-size: 12.5px;
}
</style>
