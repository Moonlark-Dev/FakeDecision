<script setup lang="ts">
import { computed } from 'vue'
import type { RequestSummary } from '@/types/api'
import { statusLabel, truncate } from '@/lib/format'
import { formatAge, formatClock, shortId } from '../utils'

const props = withDefaults(
  defineProps<{
    request: RequestSummary
    selected?: boolean
    now?: number
  }>(),
  {
    selected: false,
    now: 0,
  },
)

const emit = defineEmits<{ select: [id: string] }>()

const nowValue = computed(() => props.now || Date.now())
const remaining = computed(() => Math.max(0, props.request.deadline_at - nowValue.value))
const total = computed(() => Math.max(1, props.request.deadline_at - props.request.created_at))
const urgent = computed(() => remaining.value / total.value < 0.2)
const age = computed(() => formatAge(nowValue.value - props.request.created_at))
const preview = computed(() => truncate(props.request.input_text || '', 92) || 'No text input')
const questionTotal = computed(() => props.request.total_questions || props.request.questions?.length || 0)
const answered = computed(() => props.request.answered_count || 0)
const progress = computed(() => (questionTotal.value ? Math.min(1, answered.value / questionTotal.value) : 0))
const assignedName = computed(() => props.request.assigned_to?.name || 'Unassigned')
const ariaLabel = computed(
  () =>
    `Request ${shortId(props.request.id, 8)}, ${props.request.model}, ${statusLabel(props.request.status)}, ` +
    `${questionTotal.value} questions, ${formatClock(remaining.value)} remaining`,
)
</script>

<template>
  <button
    type="button"
    class="adm-req-item"
    :class="{ 'is-selected': selected, 'is-urgent': urgent, 'is-assigned': request.status === 'assigned' }"
    :aria-current="selected ? 'true' : undefined"
    :aria-label="ariaLabel"
    @click="emit('select', request.id)"
  >
    <span class="adm-req-rail" aria-hidden="true" />
    <span class="adm-req-body">
      <span class="adm-req-top">
        <span class="adm-req-model">{{ request.model }}</span>
        <span class="adm-req-id mono" :title="request.id">#{{ shortId(request.id, 7) }}</span>
      </span>
      <span class="adm-req-preview">{{ preview }}</span>
      <span class="adm-req-meta">
        <span class="adm-req-status">{{ statusLabel(request.status) }}</span>
        <span class="adm-req-dot" aria-hidden="true">·</span>
        <span class="adm-req-assigned">{{ assignedName }}</span>
        <span class="adm-req-dot" aria-hidden="true">·</span>
        <span>{{ answered }}/{{ questionTotal }} q</span>
        <span class="adm-req-dot" aria-hidden="true">·</span>
        <span>{{ age }}</span>
      </span>
      <span class="adm-req-foot">
        <span class="adm-req-progress" aria-hidden="true">
          <span :style="{ width: `${progress * 100}%` }" />
        </span>
        <span class="adm-req-time" :class="{ 'is-urgent': urgent }">{{ formatClock(remaining) }}</span>
      </span>
    </span>
  </button>
</template>
