<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import { copyText } from '@/lib/api'

const props = withDefaults(defineProps<{ text: string; label?: string; small?: boolean }>(), {
  label: 'Copy',
  small: true,
})
const copied = ref(false)
async function copy() {
  if (await copyText(props.text)) {
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1600)
  }
}
</script>

<template>
  <button type="button" class="btn btn-ghost" :class="{ 'btn-sm': small }" @click.prevent.stop="copy">
    <Check v-if="copied" :size="14" />
    <Copy v-else :size="14" />
    <span>{{ copied ? 'Copied' : label }}</span>
  </button>
</template>
