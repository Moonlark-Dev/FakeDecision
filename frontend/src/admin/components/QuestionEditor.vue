<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Loader2, Shuffle, TriangleAlert } from 'lucide-vue-next'
import type { Answer, ChoiceAnswer, Question, ScoreAnswer } from '@/types/api'
import {
  clamp,
  clamp01,
  criteriaOf,
  expectedScore,
  formatProbability,
  instructionsOf,
  maxProbabilityKey,
  normalizedProbabilities,
  optionKeys,
  probabilitySum,
  questionTypeBadge,
  questionTypeLabel,
  roundTo,
} from '../utils'

const props = withDefaults(
  defineProps<{
    question: Question
    answer?: Answer
    index: number
    disabled?: boolean
    randomizing?: boolean
  }>(),
  {
    answer: undefined,
    disabled: false,
    randomizing: false,
  },
)

const emit = defineEmits<{
  'update:answer': [answer: Answer]
  randomize: []
}>()

const options = computed(() => criteriaOf(props.question))
const instructions = computed(() => instructionsOf(props.question))
const type = computed(() => props.question.type)
const radioName = computed(() => `adm-choice-${props.index}`)

const NOUL_PRESETS = [
  { label: 'Decisive yes', value: 0.94 },
  { label: 'Lean yes', value: 0.72 },
  { label: 'Toss-up', value: 0.5 },
  { label: 'Lean no', value: 0.28 },
  { label: 'Decisive no', value: 0.06 },
]

function equalMap(keys: string[]): Record<string, number> {
  const map: Record<string, number> = {}
  if (!keys.length) return map
  let assigned = 0
  keys.forEach((key, index) => {
    const value = index === keys.length - 1 ? roundTo(1 - assigned, 2) : roundTo(1 / keys.length, 2)
    map[key] = value
    assigned = roundTo(assigned + value, 2)
  })
  return map
}

function optionDomId(index: number): string {
  return `adm-q-${props.index}-opt-${index}`
}

/* ------------------------------------------------------------------ noul */
const noul = ref(0.5)
const noulTouched = ref(false)
const noulConfidence = computed(() => Math.max(noul.value, 1 - noul.value))

function syncNoul() {
  const answer = props.answer
  if (answer && answer.type === 'noul') {
    noul.value = roundTo(clamp(answer.noul, 0.01, 0.99), 2)
    noulTouched.value = true
  } else if (!noulTouched.value) {
    noul.value = 0.5
  }
}

function commitNoul(raw: number | string) {
  if (typeof raw === 'string' && raw.trim() === '') return
  const numeric = typeof raw === 'string' ? Number(raw) : raw
  if (!Number.isFinite(numeric)) return
  const probability = roundTo(clamp(numeric, 0.01, 0.99), 2)
  noul.value = probability
  noulTouched.value = true
  emit('update:answer', {
    type: 'noul',
    noul: probability,
    confidence: roundTo(Math.max(probability, 1 - probability), 2),
  })
}

function applyPreset(value: number) {
  commitNoul(value)
}

function presetActive(value: number): boolean {
  return Math.abs(noul.value - value) < 0.005
}

/* ---------------------------------------------------------------- choice */
const choiceKeys = computed(() => optionKeys(props.question))
const choice = ref('')
const choiceTouched = ref(false)
const choiceProbs = ref<Record<string, number>>(equalMap(choiceKeys.value))

const choiceNormalized = computed(() => normalizedProbabilities(choiceProbs.value))
const choiceSum = computed(() => probabilitySum(choiceProbs.value))
const choiceMaxKey = computed(() => maxProbabilityKey(choiceNormalized.value))
const choiceConfidence = computed(() => {
  const winner = choiceMaxKey.value
  return winner ? choiceNormalized.value[winner] ?? 0 : 0
})
const choiceCorrection = computed(() => {
  if (!choiceKeys.value.length) return ''
  const notes: string[] = []
  if (choiceSum.value <= 0) {
    notes.push('All probabilities are zero — pick a winner.')
  } else if (Math.abs(choiceSum.value - 1) > 0.005) {
    notes.push(`Values total ${formatProbability(choiceSum.value)} — normalized on save.`)
  }
  if (choice.value && choiceMaxKey.value && choice.value !== choiceMaxKey.value) {
    notes.push('Selected option is not the highest — the server rebalances it on save.')
  }
  return notes.join(' ')
})

function syncChoice() {
  const answer = props.answer
  const keys = choiceKeys.value
  if (answer && answer.type === 'choice') {
    choice.value = answer.choice
    const map: Record<string, number> = {}
    for (const key of keys) map[key] = Number(answer.probabilities[key] ?? 0)
    choiceProbs.value = map
    choiceTouched.value = true
  } else if (!choiceTouched.value) {
    choice.value = ''
    choiceProbs.value = equalMap(keys)
  }
}

function emitChoice(selected: string, probabilities: Record<string, number>) {
  const keys = choiceKeys.value
  const clean: Record<string, number> = {}
  for (const key of keys) {
    const raw = Number(probabilities[key] ?? 0)
    clean[key] = roundTo(clamp(Number.isFinite(raw) ? raw : 0, 0, 1), 2)
  }
  let payload = clean
  if (probabilitySum(payload) <= 0) {
    payload = {}
    for (const key of keys) payload[key] = key === selected ? 1 : 0
  }
  const normalized = normalizedProbabilities(payload)
  let finalChoice = selected
  if (!finalChoice || !keys.includes(finalChoice) || (normalized[finalChoice] ?? 0) <= 0) {
    finalChoice = maxProbabilityKey(normalized) || keys[0]
    choice.value = finalChoice
  }
  const confidence = roundTo(Math.max(...Object.values(normalized), 0), 2)
  const answer: ChoiceAnswer = {
    type: 'choice',
    choice: finalChoice,
    probabilities: payload,
    confidence,
  }
  emit('update:answer', answer)
}

function commitChoice() {
  const keys = choiceKeys.value
  if (!keys.length) return
  let selected = choice.value
  if (!selected || !keys.includes(selected)) {
    selected = maxProbabilityKey(choiceNormalized.value) || keys[0]
    choice.value = selected
  }
  choiceTouched.value = true
  emitChoice(selected, choiceProbs.value)
}

function selectChoice(key: string) {
  choiceTouched.value = true
  let current = normalizedProbabilities(choiceProbs.value)
  if (choiceSum.value <= 0) current = equalMap(choiceKeys.value)
  const currentMax = maxProbabilityKey(current)
  if (currentMax === key) {
    choice.value = key
    commitChoice()
    return
  }
  const others = choiceKeys.value.filter((candidate) => candidate !== key)
  const winnerTarget = roundTo(
    clamp(Math.max(current[key] ?? 0, (current[currentMax] ?? 0) + 0.01, 0.6), 0.51, 0.99),
    2,
  )
  const remaining = roundTo(1 - winnerTarget, 2)
  const otherTotal = others.reduce((total, candidate) => total + (current[candidate] ?? 0), 0)
  const next: Record<string, number> = {}
  for (const other of others) {
    next[other] =
      otherTotal > 0
        ? roundTo(remaining * ((current[other] ?? 0) / otherTotal), 2)
        : roundTo(remaining / Math.max(1, others.length), 2)
  }
  next[key] = winnerTarget
  const drift = roundTo(1 - probabilitySum(next), 2)
  next[key] = roundTo(clamp((next[key] ?? 0) + drift, 0, 1), 2)
  choice.value = key
  choiceProbs.value = next
  commitChoice()
}

function updateChoiceProbability(key: string, raw: number | string) {
  if (typeof raw === 'string' && raw.trim() === '') return
  const numeric = typeof raw === 'string' ? Number(raw) : raw
  if (!Number.isFinite(numeric)) return
  choiceTouched.value = true
  choiceProbs.value = { ...choiceProbs.value, [key]: roundTo(clamp01(numeric), 2) }
  if (!choice.value || !choiceKeys.value.includes(choice.value)) {
    const normalized = normalizedProbabilities(choiceProbs.value)
    choice.value = maxProbabilityKey(normalized) || choiceKeys.value[0] || ''
  }
  commitChoice()
}

/* ----------------------------------------------------------------- score */
const scoreKeys = computed(() => optionKeys(props.question))
const scoreTouched = ref(false)
const scoreProbs = ref<Record<string, number>>(equalMap(scoreKeys.value))
const scoreNormalized = computed(() => normalizedProbabilities(scoreProbs.value))
const scoreSum = computed(() => probabilitySum(scoreProbs.value))
const scoreConfidence = computed(() => Math.max(...Object.values(scoreNormalized.value), 0))
const expectedScoreValue = computed(() => expectedScore(scoreProbs.value))
const scoreCorrection = computed(() => {
  if (!scoreKeys.value.length) return ''
  if (scoreSum.value <= 0) return 'All probabilities are zero — adjusting levels is required.'
  if (Math.abs(scoreSum.value - 1) > 0.005) {
    return `Values total ${formatProbability(scoreSum.value)} — normalized on save.`
  }
  return ''
})

function syncScore() {
  const answer = props.answer
  const keys = scoreKeys.value
  if (answer && answer.type === 'score') {
    const map: Record<string, number> = {}
    for (const key of keys) map[key] = Number(answer.probabilities[key] ?? 0)
    scoreProbs.value = map
    scoreTouched.value = true
  } else if (!scoreTouched.value) {
    scoreProbs.value = equalMap(keys)
  }
}

function emitScore() {
  const keys = scoreKeys.value
  if (!keys.length) return
  let payload: Record<string, number> = {}
  for (const key of keys) {
    const raw = Number(scoreProbs.value[key] ?? 0)
    payload[key] = roundTo(clamp(Number.isFinite(raw) ? raw : 0, 0, 1), 2)
  }
  if (probabilitySum(payload) <= 0) payload = equalMap(keys)
  const normalized = normalizedProbabilities(payload)
  const expected = roundTo(
    Object.entries(normalized).reduce((total, [key, value]) => {
      const level = Number(key)
      return total + (Number.isFinite(level) ? level * value : 0)
    }, 0),
    2,
  )
  const confidence = roundTo(Math.max(...Object.values(normalized), 0), 2)
  const legend: Record<string, string> = {}
  for (const option of options.value) legend[option.key] = option.description || option.label
  const answer: ScoreAnswer = {
    type: 'score',
    score: expected,
    probabilities: payload,
    confidence,
    legend,
  }
  emit('update:answer', answer)
}

function updateScoreProbability(key: string, raw: number | string) {
  if (typeof raw === 'string' && raw.trim() === '') return
  const numeric = typeof raw === 'string' ? Number(raw) : raw
  if (!Number.isFinite(numeric)) return
  scoreTouched.value = true
  scoreProbs.value = { ...scoreProbs.value, [key]: roundTo(clamp01(numeric), 2) }
  emitScore()
}

watch(
  () => props.answer,
  () => {
    syncNoul()
    syncChoice()
    syncScore()
  },
  { immediate: true, deep: true },
)
</script>

<template>
  <article class="adm-question" :class="{ 'is-answered': answer, 'is-disabled': disabled }">
    <header class="adm-q-head">
      <span class="badge" :class="questionTypeBadge(type)">{{ questionTypeLabel(type) }}</span>
      <span class="adm-q-index mono">Q{{ index + 1 }}</span>
      <span class="adm-q-id mono">{{ question.id }}</span>
      <span v-if="answer" class="adm-q-answered"><Check :size="11" /> Answered</span>
      <span v-else class="adm-q-unanswered">Unanswered</span>
      <button
        type="button"
        class="btn btn-sm adm-randomize"
        :disabled="disabled"
        :aria-label="`Randomize answer for question ${question.id}`"
        @click="emit('randomize')"
      >
        <Loader2 v-if="randomizing" :size="12" class="adm-spin" />
        <Shuffle v-else :size="12" />
        <span>Randomize</span>
      </button>
    </header>

    <p v-if="instructions" class="adm-q-instructions">{{ instructions }}</p>
    <p v-else class="adm-q-instructions muted">No instructions provided.</p>

    <div v-if="type === 'noul' && options.length" class="adm-noul-criteria">
      <div v-for="option in options" :key="option.key" class="adm-noul-criterion">
        <span class="mono adm-criterion-key">{{ option.label }}</span>
        <span class="adm-criterion-desc">{{ option.description || '—' }}</span>
      </div>
    </div>

    <div v-if="type === 'noul'" class="adm-noul-editor">
      <div class="adm-noul-row">
        <label class="adm-noul-prob" :for="`adm-noul-range-${index}`">P(true) {{ formatProbability(noul) }}</label>
        <input
          :id="`adm-noul-range-${index}`"
          class="adm-range"
          type="range"
          min="0.01"
          max="0.99"
          step="0.01"
          :value="noul"
          :disabled="disabled"
          aria-label="Probability of true"
          @input="commitNoul(($event.target as HTMLInputElement).value)"
        />
        <input
          class="input adm-prob-input"
          type="number"
          min="0.01"
          max="0.99"
          step="0.01"
          :value="noul"
          :disabled="disabled"
          aria-label="Probability of true, numeric"
          @input="commitNoul(($event.target as HTMLInputElement).value)"
        />
      </div>
      <div class="adm-presets" role="group" aria-label="Probability presets">
        <button
          v-for="preset in NOUL_PRESETS"
          :key="preset.label"
          type="button"
          class="adm-preset"
          :class="{ 'is-active': presetActive(preset.value) }"
          :disabled="disabled"
          @click="applyPreset(preset.value)"
        >
          <span>{{ preset.label }}</span>
          <span class="mono">{{ preset.value.toFixed(2) }}</span>
        </button>
      </div>
      <div class="adm-editor-footer">
        <span>Confidence <strong>{{ formatProbability(noulConfidence) }}</strong></span>
        <span class="muted">P(false) {{ formatProbability(1 - noul) }}</span>
      </div>
    </div>

    <div v-else-if="type === 'choice'" class="adm-choice-editor">
      <div
        v-for="(option, optionIndex) in options"
        :key="option.key"
        class="adm-choice-row"
        :class="{ 'is-winner': choice === option.key }"
      >
        <label class="adm-choice-pick" :for="optionDomId(optionIndex)">
          <input
            :id="optionDomId(optionIndex)"
            type="radio"
            :name="radioName"
            :value="option.key"
            :checked="choice === option.key"
            :disabled="disabled"
            @change="selectChoice(option.key)"
          />
          <span class="adm-choice-copy">
            <span class="mono adm-choice-key">{{ option.key }}</span>
            <span class="adm-choice-desc">{{ option.description || option.label }}</span>
          </span>
        </label>
        <div class="adm-choice-prob">
          <input
            class="input adm-prob-input"
            type="number"
            min="0"
            max="1"
            step="0.01"
            :value="choiceProbs[option.key]"
            :disabled="disabled"
            :aria-label="`Probability for ${option.label}`"
            @input="updateChoiceProbability(option.key, ($event.target as HTMLInputElement).value)"
          />
          <span class="mono adm-choice-pct">{{ formatProbability(choiceNormalized[option.key] ?? 0) }}</span>
        </div>
        <span class="adm-choice-bar" aria-hidden="true">
          <span :style="{ width: `${(choiceNormalized[option.key] ?? 0) * 100}%` }" />
        </span>
      </div>
      <div class="adm-editor-footer">
        <span>Confidence <strong>{{ formatProbability(choiceConfidence) }}</strong></span>
        <span class="muted">Total {{ formatProbability(choiceSum) }}</span>
      </div>
      <p v-if="choiceCorrection" class="adm-norm-note">
        <TriangleAlert :size="12" />
        <span>{{ choiceCorrection }}</span>
      </p>
    </div>

    <div v-else-if="type === 'score'" class="adm-score-editor">
      <div v-for="(option, optionIndex) in options" :key="option.key" class="adm-score-row">
        <div class="adm-score-level">
          <span class="mono adm-score-index">{{ optionIndex }}</span>
          <span class="adm-score-desc">{{ option.description || option.label }}</span>
        </div>
        <input
          class="adm-range"
          type="range"
          min="0"
          max="1"
          step="0.01"
          :value="scoreProbs[option.key]"
          :disabled="disabled"
          :aria-label="`Probability for level ${optionIndex}`"
          @input="updateScoreProbability(option.key, ($event.target as HTMLInputElement).value)"
        />
        <input
          class="input adm-prob-input"
          type="number"
          min="0"
          max="1"
          step="0.01"
          :value="scoreProbs[option.key]"
          :disabled="disabled"
          :aria-label="`Probability for level ${optionIndex}, numeric`"
          @input="updateScoreProbability(option.key, ($event.target as HTMLInputElement).value)"
        />
        <span class="mono adm-score-pct">{{ formatProbability(scoreNormalized[option.key] ?? 0) }}</span>
      </div>
      <div class="adm-editor-footer">
        <span>Expected score <strong>{{ expectedScoreValue.toFixed(2) }}</strong></span>
        <span>Confidence <strong>{{ formatProbability(scoreConfidence) }}</strong></span>
        <span class="muted">Total {{ formatProbability(scoreSum) }}</span>
      </div>
      <p v-if="scoreCorrection" class="adm-norm-note">
        <TriangleAlert :size="12" />
        <span>{{ scoreCorrection }}</span>
      </p>
    </div>

    <p v-else class="adm-answer-empty">Unsupported question type: {{ type }}</p>
  </article>
</template>
