<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Clock3, Zap, ZapOff } from 'lucide-vue-next'
import { formatClock } from '../utils'

const props = withDefaults(
  defineProps<{
    deadlineAt: number
    autoFillAt: number | null
    createdAt: number
    timeoutSeconds?: number
    offset?: number
    compact?: boolean
  }>(),
  {
    timeoutSeconds: 0,
    offset: 0,
    compact: false,
  },
)

const emit = defineEmits<{ expired: [] }>()

const now = ref(Date.now() + props.offset)
let timer: number | null = null
let fired = false

function tick() {
  now.value = Date.now() + props.offset
  if (!fired && now.value >= props.deadlineAt) {
    fired = true
    emit('expired')
  }
}

watch(
  () => props.offset,
  () => tick(),
)
watch(
  () => props.deadlineAt,
  () => {
    fired = false
    tick()
  },
)

onMounted(() => {
  tick()
  timer = window.setInterval(tick, 250)
})

onBeforeUnmount(() => {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
})

const totalWindow = computed(() => Math.max(1, props.deadlineAt - props.createdAt))
const remaining = computed(() => Math.max(0, props.deadlineAt - now.value))
const ratio = computed(() => remaining.value / totalWindow.value)
const urgent = computed(() => ratio.value < 0.2)

const autoFillRemaining = computed<number | null>(() =>
  props.autoFillAt === null ? null : Math.max(0, props.autoFillAt - now.value),
)
const autoFillLead = computed(() =>
  props.autoFillAt === null ? 1 : Math.max(1, props.deadlineAt - props.autoFillAt),
)
const autoFillRatio = computed(() =>
  autoFillRemaining.value === null ? 1 : autoFillRemaining.value / autoFillLead.value,
)
const autoFillUrgent = computed(() => autoFillRatio.value < 0.2)
const autoFillPassed = computed(() => autoFillRemaining.value !== null && autoFillRemaining.value <= 0)
const deadlineLabel = computed(() => `Time remaining ${formatClock(remaining.value)}`)
const autoFillLabel = computed(() => {
  if (props.autoFillAt === null) return 'Auto-fill disabled'
  if (autoFillPassed.value) return 'Auto-fill pending'
  return `Auto-fill in ${formatClock(autoFillRemaining.value)}`
})
</script>

<template>
  <div class="adm-countdown" :class="{ 'adm-countdown-compact': compact }">
    <div class="adm-countdown-row">
      <span class="adm-countdown-label"><Clock3 :size="12" /> Deadline</span>
      <span class="adm-countdown-value" :class="{ 'is-urgent': urgent }" role="timer" :aria-label="deadlineLabel">
        {{ formatClock(remaining) }}
      </span>
    </div>
    <div class="adm-countdown-track" aria-hidden="true">
      <span
        class="adm-countdown-fill"
        :class="{ 'is-urgent': urgent }"
        :style="{ width: `${Math.max(0, Math.min(100, ratio * 100))}%` }"
      />
    </div>
    <div class="adm-countdown-row adm-countdown-secondary">
      <span class="adm-countdown-label" :class="{ 'is-urgent': autoFillUrgent, 'is-off': autoFillAt === null }">
        <component :is="autoFillAt === null ? ZapOff : Zap" :size="12" />
        Auto-fill
      </span>
      <span
        v-if="autoFillAt === null"
        class="adm-countdown-value adm-countdown-off"
        title="Auto-fill is disabled for this deployment"
      >
        disabled
      </span>
      <span
        v-else
        class="adm-countdown-value adm-countdown-autofill"
        :class="{ 'is-urgent': autoFillUrgent }"
        :aria-label="autoFillLabel"
      >
        {{ autoFillPassed ? 'pending' : `in ${formatClock(autoFillRemaining)}` }}
      </span>
    </div>
    <span class="sr-only">{{ deadlineLabel }}. {{ autoFillLabel }}.</span>
  </div>
</template>
