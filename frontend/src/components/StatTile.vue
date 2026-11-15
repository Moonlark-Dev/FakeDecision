<script setup lang="ts">
withDefaults(defineProps<{ label: string; value: string | number; hint?: string; accent?: boolean }>(), {
  hint: '',
  accent: false,
})
</script>

<template>
  <div class="stat-tile" :class="{ accent }">
    <p class="stat-label">{{ label }}</p>
    <p class="stat-value">{{ value }}</p>
    <p v-if="hint" class="stat-hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.stat-tile {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}

.stat-tile.accent {
  background: var(--ink);
  color: var(--bg);
  border-color: var(--ink);
}

.stat-label {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.accent .stat-label,
.accent .stat-hint {
  color: color-mix(in srgb, var(--bg) 62%, transparent);
}

.stat-value {
  margin-top: 8px;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.05em;
  line-height: 1;
}

.stat-hint {
  margin-top: 7px;
  color: var(--muted);
  font-size: 11.5px;
}
</style>
