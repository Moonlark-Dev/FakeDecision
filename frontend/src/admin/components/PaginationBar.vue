<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { formatNumber } from '@/lib/format'

const props = withDefaults(
  defineProps<{
    total: number
    limit: number
    offset: number
    loading?: boolean
  }>(),
  {
    loading: false,
  },
)

const emit = defineEmits<{ 'update:offset': [offset: number] }>()

const page = computed(() => Math.floor(props.offset / Math.max(1, props.limit)) + 1)
const pages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.limit))))
const from = computed(() => (props.total === 0 ? 0 : props.offset + 1))
const to = computed(() => Math.min(props.total, props.offset + props.limit))
const canPrev = computed(() => props.offset > 0 && !props.loading)
const canNext = computed(() => props.offset + props.limit < props.total && !props.loading)

function go(delta: number) {
  const next = Math.max(0, props.offset + delta * props.limit)
  if (next === props.offset) return
  emit('update:offset', next)
}
</script>

<template>
  <nav class="adm-pagination" aria-label="Pagination">
    <span class="adm-pagination-info">
      <span class="mono">{{ formatNumber(from) }}–{{ formatNumber(to) }}</span>
      <span class="muted">of {{ formatNumber(total) }}</span>
    </span>
    <div class="adm-pagination-actions">
      <span class="adm-pagination-page muted">Page {{ page }} / {{ pages }}</span>
      <button type="button" class="btn btn-sm" :disabled="!canPrev" aria-label="Previous page" @click="go(-1)">
        <ChevronLeft :size="14" />
        <span>Prev</span>
      </button>
      <button type="button" class="btn btn-sm" :disabled="!canNext" aria-label="Next page" @click="go(1)">
        <span>Next</span>
        <ChevronRight :size="14" />
      </button>
    </div>
  </nav>
</template>
