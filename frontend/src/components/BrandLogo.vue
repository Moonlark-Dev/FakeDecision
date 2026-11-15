<script setup lang="ts">
withDefaults(
  defineProps<{
    name?: string
    compact?: boolean
    tone?: 'ink' | 'inverse'
    size?: number
  }>(),
  {
    name: 'Noema',
    compact: false,
    tone: 'ink',
    size: 28,
  },
)
</script>

<template>
  <span class="brand" :class="[`brand-${tone}`, { 'brand-compact': compact }]">
    <span class="brand-mark" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="currentColor" />
        <path d="M9 22V10h6.2c4.2 0 7 2.2 7 6s-2.8 6-7 6H9Zm4.4-3.4h1.7c2.1 0 3.4-1 3.4-2.6s-1.3-2.6-3.4-2.6h-1.7v5.2Z" fill="var(--surface)" />
        <circle cx="24.2" cy="9.2" r="2.15" fill="var(--lime)" />
      </svg>
    </span>
    <span v-if="!compact" class="brand-word">{{ name }}</span>
  </span>
</template>

<style scoped>
.brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: var(--ink);
  line-height: 1;
}

.brand-inverse {
  color: #fff;
}

.brand-mark {
  display: block;
  color: var(--ink);
  flex: 0 0 auto;
}

.brand-inverse .brand-mark {
  color: #fff;
}

.brand-mark svg {
  width: 100%;
  height: 100%;
}

.brand-word {
  font-size: 16px;
  font-weight: 640;
  letter-spacing: -0.045em;
}

.brand-compact .brand-mark {
  color: var(--ink);
}
</style>
