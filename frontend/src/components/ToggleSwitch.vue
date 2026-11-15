<script setup lang="ts">
withDefaults(defineProps<{ modelValue: boolean; label?: string; disabled?: boolean }>(), {
  label: '',
  disabled: false,
})
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <button
    type="button"
    class="toggle"
    :class="{ 'toggle-on': modelValue }"
    role="switch"
    :aria-checked="modelValue"
    :aria-label="label || 'Toggle'"
    :disabled="disabled"
    @click="emit('update:modelValue', !modelValue)"
  >
    <span class="toggle-thumb" />
  </button>
</template>

<style scoped>
.toggle {
  position: relative;
  width: 38px;
  height: 22px;
  flex: 0 0 auto;
  padding: 0;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--surface-3);
  transition: background 160ms ease, border-color 160ms ease;
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: 0 1px 3px rgba(16, 21, 19, 0.22);
  transition: transform 160ms ease;
}

.toggle-on {
  background: var(--accent);
  border-color: var(--accent);
}

.toggle-on .toggle-thumb {
  transform: translateX(16px);
}

.toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
