<script setup lang="ts">
import { computed } from 'vue'
import type { Answer, Question } from '@/types/api'
import {
  answerConfidence,
  clamp,
  criteriaOf,
  formatProbability,
  instructionsOf,
  normalizedProbabilities,
  questionTypeBadge,
  questionTypeLabel,
  roundTo,
} from '../utils'
import { formatNumber } from '@/lib/format'

const props = defineProps<{
  question: Question
  answer: Answer | null | undefined
}>()

const instructions = computed(() => instructionsOf(props.question))
const type = computed(() => props.question.type)
const confidence = computed(() => answerConfidence(props.answer))

const noul = computed<number | null>(() =>
  props.answer?.type === 'noul' ? clamp(props.answer.noul, 0, 1) : null,
)
const noulConfidence = computed(() =>
  noul.value === null ? null : Math.max(noul.value, 1 - noul.value),
)
const noulTrueLabel = computed(() => {
  const option = criteriaOf(props.question).find((item) => item.key === 'true' || item.key === '1')
  return option?.description || 'True'
})
const noulFalseLabel = computed(() => {
  const option = criteriaOf(props.question).find((item) => item.key === 'false' || item.key === '0')
  return option?.description || 'False'
})
const noulPercent = computed(() => (noul.value === null ? 0 : noul.value * 100))
const noulLabel = computed(() => probabilityLabel(noul.value ?? 0))
const noulFalseLabelText = computed(() => probabilityLabel(1 - (noul.value ?? 0)))
const noulTrueWidth = computed(() => `${noulPercent.value}%`)
const noulFalseWidth = computed(() => `${100 - noulPercent.value}%`)

interface ChoiceRow {
  key: string
  label: string
  description: string
  probability: number
  winner: boolean
}

const choiceRows = computed<ChoiceRow[]>(() => {
  const answer = props.answer
  if (!answer || answer.type !== 'choice') return []
  const probabilities = normalizedProbabilities(answer.probabilities)
  const options = criteriaOf(props.question)
  const keys = options.length ? options.map((option) => option.key) : Object.keys(probabilities)
  return keys.map((key) => {
    const option = options.find((item) => item.key === key)
    return {
      key,
      label: option?.label || key,
      description: option?.description || '',
      probability: probabilities[key] ?? 0,
      winner: key === answer.choice,
    }
  })
})
const winnerLabel = computed(() => {
  const answer = props.answer
  if (!answer || answer.type !== 'choice') return ''
  const row = choiceRows.value.find((item) => item.key === answer.choice)
  return row?.description || row?.label || answer.choice
})

interface ScoreRow {
  key: string
  index: number
  label: string
  description: string
  probability: number
}

const scoreRows = computed<ScoreRow[]>(() => {
  const answer = props.answer
  if (!answer || answer.type !== 'score') return []
  const probabilities = normalizedProbabilities(answer.probabilities)
  const options = criteriaOf(props.question)
  return options.map((option, index) => ({
    key: option.key,
    index,
    label: option.label,
    description: option.description,
    probability: probabilities[option.key] ?? 0,
  }))
})
const scoreValue = computed(() => (props.answer?.type === 'score' ? props.answer.score : null))
const scoreMax = computed(() => Math.max(0, criteriaOf(props.question).length - 1))
const scoreLegend = computed(() => (props.answer?.type === 'score' ? props.answer.legend || {} : {}))

function probabilityLabel(value: number): string {
  return formatProbability(value, 0)
}

function scoreDisplay(value: number): string {
  return formatNumber(roundTo(value, 2), 2)
}
</script>

<template>
  <article class="adm-answer-card">
    <header class="adm-q-head">
      <span class="badge" :class="questionTypeBadge(type)">{{ questionTypeLabel(type) }}</span>
      <span class="adm-q-id mono">{{ question.id }}</span>
      <span class="adm-answer-final">Final</span>
    </header>
    <p v-if="instructions" class="adm-q-instructions">{{ instructions }}</p>

    <template v-if="noul !== null">
      <div class="adm-answer-hero">
        <span class="adm-answer-hero-label">P(true)</span>
        <strong class="adm-answer-hero-value">{{ noulLabel }}</strong>
        <span v-if="noulConfidence !== null" class="adm-answer-conf muted tiny">
          confidence {{ probabilityLabel(noulConfidence) }}
        </span>
      </div>
      <div class="adm-dist" aria-hidden="true">
        <span class="adm-dist-yes" :style="{ width: noulTrueWidth }" />
        <span class="adm-dist-no" :style="{ width: noulFalseWidth }" />
      </div>
      <div class="adm-dist-legend">
        <span class="adm-dist-legend-true">True · {{ noulLabel }} <span class="muted">{{ noulTrueLabel }}</span></span>
        <span class="adm-dist-legend-false">False · {{ noulFalseLabelText }} <span class="muted">{{ noulFalseLabel }}</span></span>
      </div>
    </template>

    <template v-else-if="choiceRows.length">
      <div class="adm-answer-hero">
        <span class="adm-answer-hero-label">Winner</span>
        <strong class="adm-answer-hero-value adm-answer-hero-text">{{ winnerLabel }}</strong>
        <span v-if="confidence !== null" class="adm-answer-conf muted tiny">
          confidence {{ probabilityLabel(confidence) }}
        </span>
      </div>
      <ul class="adm-dist-list">
        <li v-for="row in choiceRows" :key="row.key" :class="{ 'is-winner': row.winner }">
          <span class="adm-dist-label">
            <span class="mono adm-dist-key">{{ row.key }}</span>
            <span class="adm-dist-desc">{{ row.description || row.label }}</span>
          </span>
          <span class="adm-dist-bar" aria-hidden="true">
            <span :style="{ width: `${row.probability * 100}%` }" />
          </span>
          <span class="adm-dist-pct mono">{{ probabilityLabel(row.probability) }}</span>
        </li>
      </ul>
    </template>

    <template v-else-if="scoreRows.length">
      <div class="adm-answer-hero">
        <span class="adm-answer-hero-label">Expected score</span>
        <strong class="adm-answer-hero-value">{{ scoreDisplay(scoreValue ?? 0) }}<span class="adm-answer-hero-max">/ {{ scoreMax }}</span></strong>
        <span v-if="confidence !== null" class="adm-answer-conf muted tiny">
          confidence {{ probabilityLabel(confidence) }}
        </span>
      </div>
      <ul class="adm-dist-list">
        <li v-for="row in scoreRows" :key="row.key">
          <span class="adm-dist-label">
            <span class="mono adm-dist-key">{{ row.index }}</span>
            <span class="adm-dist-desc">{{ row.description || scoreLegend[row.key] || row.label }}</span>
          </span>
          <span class="adm-dist-bar" aria-hidden="true">
            <span :style="{ width: `${row.probability * 100}%` }" />
          </span>
          <span class="adm-dist-pct mono">{{ probabilityLabel(row.probability) }}</span>
        </li>
      </ul>
    </template>

    <p v-else class="adm-answer-empty">No answer recorded for this question.</p>
  </article>
</template>
