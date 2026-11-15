<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  ChevronDown,
  Clock,
  FlaskConical,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Terminal,
  Trash2,
  TriangleAlert,
  X,
} from 'lucide-vue-next'
import CopyButton from '@/components/CopyButton.vue'
import { ApiError, get, post } from '@/lib/api'
import { formatDuration } from '@/lib/format'
import { toast } from '@/lib/toast'
import {
  highlightJson,
  prettyJson,
  pythonRaw,
  reportError,
  shellQuote,
} from '@/public/support'
import type { Model, PlaygroundResult, Protocol, QuestionType } from '@/types/api'

interface BuilderOption {
  key: string
  value: string
}

interface BuilderQuestion {
  uid: number
  id: string
  type: QuestionType
  instructions: string
  options: BuilderOption[]
  levels: string[]
  trueCriteria: string
  falseCriteria: string
  criteriaOpen: boolean
}

type ResultTab = 'response' | 'request' | 'curl' | 'python' | 'typescript'

let uidSeq = 1

function makeQuestion(type: QuestionType, id: string): BuilderQuestion {
  return {
    uid: uidSeq++,
    id,
    type,
    instructions: '',
    options:
      type === 'choice'
        ? [
            { key: '', value: '' },
            { key: '', value: '' },
          ]
        : [],
    levels: type === 'score' ? ['Low', 'Medium', 'High'] : [],
    trueCriteria: '',
    falseCriteria: '',
    criteriaOpen: false,
  }
}

function refundQuestions(): BuilderQuestion[] {
  const refund = makeQuestion('noul', 'refund')
  refund.instructions = 'Does the customer ask for a refund?'
  refund.trueCriteria = 'Explicit refund request'
  refund.falseCriteria = 'No refund request'

  const action = makeQuestion('choice', 'action')
  action.instructions = 'Pick the next action.'
  action.options = [
    { key: 'refund', value: 'Refund the duplicate charge' },
    { key: 'replace', value: 'Send a replacement' },
  ]

  const urgency = makeQuestion('score', 'urgency')
  urgency.instructions = 'How urgent is this?'
  urgency.levels = ['Low', 'Medium', 'High']

  return [refund, action, urgency]
}

function invoiceQuestions(): BuilderQuestion[] {
  const paid = makeQuestion('noul', 'paid')
  paid.instructions = 'Is the invoice paid in full?'
  paid.trueCriteria = 'Full payment received'
  paid.falseCriteria = 'Any outstanding balance'
  paid.criteriaOpen = true

  const next = makeQuestion('choice', 'next_step')
  next.instructions = 'What should happen next?'
  next.options = [
    { key: 'close', value: 'Close the invoice as paid' },
    { key: 'remind', value: 'Send a payment reminder' },
    { key: 'escalate', value: 'Escalate the case' },
  ]

  const risk = makeQuestion('score', 'risk')
  risk.instructions = 'How risky is this account?'
  risk.levels = ['Low', 'Medium', 'High', 'Critical']

  return [paid, next, risk]
}

interface Example {
  id: string
  label: string
  state: string
  build: () => BuilderQuestion[]
}

const examples: Example[] = [
  {
    id: 'refund',
    label: 'Refund routing',
    state:
      'The customer was charged twice for the same order. They wrote in asking for the duplicate charge to be refunded and mentioned the amount is holding up their monthly budget.',
    build: refundQuestions,
  },
  {
    id: 'invoice',
    label: 'Invoice review',
    state:
      'Invoice 4021 for $1,840 was issued on 3 March and is due on 31 March. A partial payment of $600 was received on 20 March and no further payment has arrived.',
    build: invoiceQuestions,
  },
]

const EXAMPLES = new Map(examples.map((example) => [example.id, example]))

const protocol = ref<Protocol>('systemone')
const models = ref<Model[]>([])
const modelsLoading = ref(true)
const modelsError = ref('')
const selectedModel = ref('')

const stateText = ref(examples[0].state)
const questions = ref<BuilderQuestion[]>(refundQuestions())
const timeoutText = ref('120')
const activeExample = ref('refund')

const running = ref(false)
const result = ref<PlaygroundResult | null>(null)
const runError = ref<{ message: string; code?: string } | null>(null)
const elapsed = ref(0)
const activeTab = ref<ResultTab>('response')
const responseRef = ref<HTMLElement | null>(null)

let timer: number | undefined
let startedAt = 0

function stopTimer() {
  if (timer !== undefined) {
    window.clearInterval(timer)
    timer = undefined
  }
}

function startTimer() {
  stopTimer()
  startedAt = Date.now()
  elapsed.value = 0
  timer = window.setInterval(() => {
    elapsed.value = Date.now() - startedAt
  }, 100)
}

function protocolsOf(model: Model): Protocol[] {
  if (model.protocols && model.protocols.length) return model.protocols
  if (model.protocol === 'both') return ['systemone', 'google']
  return [model.protocol]
}

const availableModels = computed(() => models.value.filter((model) => protocolsOf(model).includes(protocol.value)))

function ensureModel() {
  const list = availableModels.value
  if (!list.some((model) => model.name === selectedModel.value)) {
    selectedModel.value = list[0]?.name ?? ''
  }
}

async function loadModels() {
  modelsLoading.value = true
  modelsError.value = ''
  try {
    const payload = await get<{ models: Model[] }>('/api/console/models')
    models.value = payload.models ?? []
  } catch (error) {
    modelsError.value = reportError(error, 'Could not load the available models.')
  } finally {
    modelsLoading.value = false
    ensureModel()
  }
}

watch(availableModels, ensureModel)

function setProtocol(next: Protocol) {
  protocol.value = next
}

function loadExample(id: string) {
  const example = EXAMPLES.get(id)
  if (!example) return
  activeExample.value = id
  stateText.value = example.state
  questions.value = example.build()
  activeTab.value = 'response'
}

function clearBuilder() {
  activeExample.value = ''
  stateText.value = ''
  questions.value = []
}

function addQuestion(type: QuestionType) {
  activeExample.value = ''
  const existing = new Set(questions.value.map((question) => question.id))
  const base = type === 'choice' ? 'choice' : type === 'score' ? 'score' : 'question'
  let counter = questions.value.length + 1
  let id = `${base}_${counter}`
  while (existing.has(id)) {
    counter += 1
    id = `${base}_${counter}`
  }
  questions.value.push(makeQuestion(type, id))
}

function removeQuestion(uid: number) {
  activeExample.value = ''
  questions.value = questions.value.filter((question) => question.uid !== uid)
}

function addOption(question: BuilderQuestion) {
  question.options.push({ key: '', value: '' })
}

function removeOption(question: BuilderQuestion, index: number) {
  question.options.splice(index, 1)
}

function addLevel(question: BuilderQuestion) {
  question.levels.push('')
}

function removeLevel(question: BuilderQuestion, index: number) {
  question.levels.splice(index, 1)
}

function typeBadgeClass(type: QuestionType): string {
  if (type === 'noul') return 'badge badge-blue'
  if (type === 'choice') return 'badge badge-lime'
  return 'badge badge-amber'
}

function buildQuestionsPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const question of questions.value) {
    const id = question.id.trim()
    const spec: Record<string, unknown> = {
      type: question.type,
      instructions: question.instructions.trim(),
    }
    if (question.type === 'choice') {
      const criteria: Record<string, string> = {}
      for (const option of question.options) {
        const key = option.key.trim()
        if (key) criteria[key] = option.value.trim()
      }
      spec.criteria = criteria
    } else if (question.type === 'score') {
      spec.criteria = question.levels.map((level) => level.trim())
    } else {
      const criteria: Record<string, string> = {}
      if (question.trueCriteria.trim()) criteria.true = question.trueCriteria.trim()
      if (question.falseCriteria.trim()) criteria.false = question.falseCriteria.trim()
      if (Object.keys(criteria).length) spec.criteria = criteria
    }
    payload[id] = spec
  }
  return payload
}

const judgeRequest = computed<Record<string, unknown>>(() => {
  const fallbackModel = protocol.value === 'systemone' ? 'jev-latest' : 'gemini-decision-1'
  const body: Record<string, unknown> = { model: selectedModel.value || fallbackModel }
  if (protocol.value === 'systemone') body.state = stateText.value
  else body.input = stateText.value
  body.questions = buildQuestionsPayload()
  return body
})

const timeoutInvalid = computed(() => {
  if (!timeoutText.value.trim()) return false
  const seconds = Number(timeoutText.value)
  return !Number.isFinite(seconds)
})

const timeoutMs = computed<number | null>(() => {
  if (!timeoutText.value.trim()) return null
  const seconds = Number(timeoutText.value)
  if (!Number.isFinite(seconds)) return null
  return Math.round(seconds * 1000)
})

function validate(): string | null {
  if (!selectedModel.value) return 'Select a model before running.'
  if (!stateText.value.trim()) {
    return protocol.value === 'systemone' ? 'Add a state to decide over.' : 'Add an input to decide over.'
  }
  if (!questions.value.length) return 'Add at least one question.'
  const seen = new Set<string>()
  for (const question of questions.value) {
    const id = question.id.trim()
    if (!id) return 'Every question needs an id.'
    if (id.length > 128 || /[\x00-\x1F\x7F]/.test(id)) return 'Question ids must be 1–128 printable characters.'
    if (seen.has(id)) return `Question id "${id}" is used twice.`
    seen.add(id)
    if (!question.instructions.trim()) return `Add instructions for "${id}".`
    if (question.type === 'choice') {
      if (question.options.some((option) => !option.key.trim() && option.value.trim())) {
        return `Every option in "${id}" needs a key.`
      }
      const keys = question.options.map((option) => option.key.trim()).filter(Boolean)
      if (keys.length < 2) return `Choice "${id}" needs at least two options.`
      if (new Set(keys).size !== keys.length) return `Option keys in "${id}" must be unique.`
      if (question.options.some((option) => option.key.trim() && !option.value.trim())) {
        return `Every option in "${id}" needs a description.`
      }
    }
    if (question.type === 'score') {
      if (question.levels.some((level) => !level.trim())) return `Every level in "${id}" needs a label.`
      if (question.levels.length < 2) return `Score "${id}" needs at least two levels.`
    }
  }
  if (timeoutInvalid.value) return 'Timeout must be a number of seconds.'
  if (timeoutMs.value !== null && (timeoutMs.value < 1000 || timeoutMs.value > 900000)) {
    return 'Timeout must be between 1 and 900 seconds.'
  }
  return null
}

async function run() {
  if (running.value) return
  const problem = validate()
  if (problem) {
    runError.value = { message: problem }
    activeTab.value = 'response'
    toast(problem, 'warning')
    return
  }

  runError.value = null
  result.value = null
  running.value = true
  activeTab.value = 'response'
  startTimer()

  try {
    const body: Record<string, unknown> = {
      protocol: protocol.value,
      model: selectedModel.value,
      input: stateText.value,
      questions: buildQuestionsPayload(),
    }
    if (timeoutMs.value !== null) body.timeout_ms = timeoutMs.value
    const response = await post<PlaygroundResult>('/api/console/playground', body)
    result.value = response
    toast('Decision received', 'success', { detail: formatDuration(response.elapsed_ms) })
    if (responseRef.value && window.innerWidth < 1100) {
      responseRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  } catch (error) {
    const message = reportError(error, 'The playground request failed.')
    runError.value = { message, code: error instanceof ApiError ? error.code : undefined }
  } finally {
    running.value = false
    stopTimer()
  }
}

const endpoint = computed(() => (protocol.value === 'systemone' ? '/v1/systemone' : '/v1beta/decisions'))

const requestJson = computed(() => prettyJson(judgeRequest.value))

const curlSnippet = computed(() => {
  const lines = [`curl -sS "$NOEMA_BASE_URL${endpoint.value}" \\`]
  lines.push(
    protocol.value === 'systemone'
      ? '  -H "Authorization: Bearer $NOEMA_API_KEY" \\'
      : '  -H "x-goog-api-key: $NOEMA_API_KEY" \\',
  )
  lines.push('  -H "Content-Type: application/json" \\')
  if (timeoutMs.value !== null) lines.push(`  -H "X-Decision-Timeout-Ms: ${timeoutMs.value}" \\`)
  lines.push(`  -d ${shellQuote(requestJson.value)}`)
  return lines.join('\n')
})

const pythonSnippet = computed(() => {
  const headers =
    protocol.value === 'systemone'
      ? `{"Authorization": f"Bearer {os.environ['NOEMA_API_KEY']}"}`
      : `{"x-goog-api-key": os.environ['NOEMA_API_KEY']}`
  const timeoutHeader = timeoutMs.value !== null ? `    "X-Decision-Timeout-Ms": "${timeoutMs.value}",\n` : ''
  return `import json
import os
import requests

payload = json.loads(
    ${pythonRaw(requestJson.value)}
)

response = requests.post(
    f"{os.environ['NOEMA_BASE_URL']}${endpoint.value}",
    headers={${headers}},
${timeoutHeader}    json=payload,
    timeout=120,
)
response.raise_for_status()
print(json.dumps(response.json(), indent=2))`
})

const typescriptSnippet = computed(() => {
  const auth =
    protocol.value === 'systemone'
      ? `    Authorization: \`Bearer \${process.env.NOEMA_API_KEY}\`,`
      : `    'x-goog-api-key': process.env.NOEMA_API_KEY ?? '',`
  const timeoutLine = timeoutMs.value !== null ? `    'X-Decision-Timeout-Ms': '${timeoutMs.value}',\n` : ''
  return `const baseUrl = process.env.NOEMA_BASE_URL ?? 'https://api.noema.dev'

const payload = ${requestJson.value} as const

const response = await fetch(\`\${baseUrl}${endpoint.value}\`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
${auth}
${timeoutLine}  },
  body: JSON.stringify(payload),
})

if (!response.ok) {
  throw new Error(\`Decision request failed: \${response.status}\`)
}

const data = await response.json()
console.log(JSON.stringify(data, null, 2))`
})

const tabs: { id: ResultTab; label: string }[] = [
  { id: 'response', label: 'Response' },
  { id: 'request', label: 'Request' },
  { id: 'curl', label: 'cURL' },
  { id: 'python', label: 'Python' },
  { id: 'typescript', label: 'TypeScript' },
]

const activeText = computed(() => {
  switch (activeTab.value) {
    case 'request':
      return requestJson.value
    case 'curl':
      return curlSnippet.value
    case 'python':
      return pythonSnippet.value
    case 'typescript':
      return typescriptSnippet.value
    default:
      return result.value ? prettyJson(result.value.response) : ''
  }
})

const responseJson = computed(() => (result.value ? prettyJson(result.value.response) : ''))

const protocolHint = computed(() =>
  protocol.value === 'systemone'
    ? 'The state is shared context for every question. Questions are keyed objects with a type and instructions.'
    : 'The input is shared context. The playground sends plain text; the API also accepts content blocks for images and documents.',
)

function onRunShortcut(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    event.preventDefault()
    void run()
  }
}

onMounted(() => {
  void loadModels()
  window.addEventListener('keydown', onRunShortcut)
})

onBeforeUnmount(() => {
  stopTimer()
  window.removeEventListener('keydown', onRunShortcut)
})
</script>

<template>
  <div class="console-page console-playground">
    <div class="console-page-head">
      <div>
        <p class="eyebrow">Playground</p>
        <h1 class="console-h1">Run a typed decision.</h1>
        <p class="console-sub">
          Build the request visually, then send it through the console. No API key is used or exposed here.
        </p>
      </div>
      <div class="console-page-actions">
        <span class="badge badge-blue"><FlaskConical :size="12" /> session auth</span>
        <RouterLink :to="{ path: '/docs', hash: '#questions' }" class="btn btn-sm">Question reference</RouterLink>
      </div>
    </div>

    <div v-if="modelsError" class="console-alert console-alert-error" role="alert">
      <span>{{ modelsError }}</span>
      <button type="button" class="btn btn-sm" @click="loadModels">
        <RefreshCw :size="14" />
        Retry
      </button>
    </div>

    <div class="console-runbar panel">
      <div class="console-seg" role="tablist" aria-label="Protocol">
        <button
          type="button"
          role="tab"
          class="console-seg-btn"
          :class="{ 'is-active': protocol === 'systemone' }"
          :aria-selected="protocol === 'systemone'"
          :disabled="running"
          @click="setProtocol('systemone')"
        >
          System One
          <span class="mono">/v1/systemone</span>
        </button>
        <button
          type="button"
          role="tab"
          class="console-seg-btn"
          :class="{ 'is-active': protocol === 'google' }"
          :aria-selected="protocol === 'google'"
          :disabled="running"
          @click="setProtocol('google')"
        >
          Gemini Decisions
          <span class="mono">/v1beta/decisions</span>
        </button>
      </div>

      <label class="console-runbar-field console-runbar-model">
        <span class="sr-only">Model</span>
        <select v-model="selectedModel" class="select" :disabled="modelsLoading || !availableModels.length">
          <option v-if="modelsLoading" value="">Loading models…</option>
          <option v-else-if="!availableModels.length" value="">No models for this protocol</option>
          <option v-for="model in availableModels" :key="model.name" :value="model.name">
            {{ model.display_name }} — {{ model.name }}
          </option>
        </select>
      </label>

      <label class="console-runbar-field console-runbar-timeout">
        <span class="console-runbar-label">Timeout</span>
        <input
          v-model="timeoutText"
          class="input"
          type="number"
          min="1"
          max="900"
          step="1"
          inputmode="numeric"
          aria-label="Timeout in seconds"
        />
        <span class="console-runbar-unit mono">s</span>
      </label>

      <button type="button" class="btn btn-primary console-run" :disabled="running || !availableModels.length" @click="run">
        <Loader2 v-if="running" :size="16" class="pub-spin" />
        <Play v-else :size="15" />
        {{ running ? 'Running…' : 'Run decision' }}
      </button>
    </div>

    <p class="console-runbar-hint">
      {{ protocolHint }} <span class="mono">⌘ / Ctrl + Enter</span> runs the request. Leave timeout empty to use the
      deployment default.
    </p>

    <div class="console-playground-grid">
      <section class="console-builder">
        <div class="console-builder-block panel">
          <header class="console-block-head">
            <div>
              <h2 class="console-block-title">{{ protocol === 'systemone' ? 'State' : 'Input' }}</h2>
              <p class="console-block-sub">
                {{ protocol === 'systemone' ? 'The shared context every question is decided against.' : 'Text context sent with the request.' }}
              </p>
            </div>
            <div class="console-example-actions">
              <button
                v-for="example in examples"
                :key="example.id"
                type="button"
                class="btn btn-sm"
                :class="{ 'console-example-active': activeExample === example.id }"
                @click="loadExample(example.id)"
              >
                {{ example.label }}
              </button>
              <button type="button" class="btn btn-ghost btn-sm" @click="clearBuilder">
                <Trash2 :size="14" />
                Clear
              </button>
            </div>
          </header>

          <div class="console-block-body">
            <label class="sr-only" for="playground-state">{{ protocol === 'systemone' ? 'State' : 'Input' }}</label>
            <textarea
              id="playground-state"
              v-model="stateText"
              class="textarea console-state-input"
              rows="7"
              :placeholder="
                protocol === 'systemone'
                  ? 'Describe the situation the questions should be decided against…'
                  : 'Text the questions should be decided against…'
              "
            />
            <div class="console-state-meta">
              <span class="mono">{{ stateText.length }} chars</span>
              <span class="mono">model · {{ selectedModel || 'none' }}</span>
            </div>
          </div>
        </div>

        <div class="console-builder-block panel">
          <header class="console-block-head">
            <div>
              <h2 class="console-block-title">Questions</h2>
              <p class="console-block-sub">
                {{ questions.length }} typed question{{ questions.length === 1 ? '' : 's' }} in this request.
              </p>
            </div>
            <div class="console-add-group">
              <button type="button" class="btn btn-sm" @click="addQuestion('noul')">
                <Plus :size="14" />
                Yes / no
              </button>
              <button type="button" class="btn btn-sm" @click="addQuestion('choice')">
                <Plus :size="14" />
                Choice
              </button>
              <button type="button" class="btn btn-sm" @click="addQuestion('score')">
                <Plus :size="14" />
                Score
              </button>
            </div>
          </header>

          <div class="console-block-body">
            <div v-if="!questions.length" class="console-builder-empty">
              <p>No questions yet.</p>
              <p class="muted small">Add a yes/no, choice or score question to build the request.</p>
            </div>

            <article v-for="(question, index) in questions" :key="question.uid" class="console-question">
              <header class="console-question-head">
                <span class="console-q-index mono">{{ String(index + 1).padStart(2, '0') }}</span>
                <span :class="typeBadgeClass(question.type)">{{ question.type }}</span>
                <input
                  v-model="question.id"
                  class="input mono console-q-id"
                  type="text"
                  placeholder="question_id"
                  aria-label="Question id"
                  spellcheck="false"
                />
                <button
                  type="button"
                  class="btn btn-ghost btn-icon btn-sm console-q-remove"
                  aria-label="Remove question"
                  @click="removeQuestion(question.uid)"
                >
                  <Trash2 :size="15" />
                </button>
              </header>

              <div class="console-q-body">
                <label class="label" :for="`q-instructions-${question.uid}`">Instructions</label>
                <textarea
                  :id="`q-instructions-${question.uid}`"
                  v-model="question.instructions"
                  class="textarea console-q-instructions"
                  rows="2"
                  placeholder="What should be decided for this question?"
                />

                <template v-if="question.type === 'choice'">
                  <p class="label console-q-label">Options</p>
                  <div class="console-rows">
                    <div v-for="(option, optionIndex) in question.options" :key="optionIndex" class="console-row console-option-row">
                      <input
                        v-model="option.key"
                        class="input mono"
                        type="text"
                        placeholder="key"
                        aria-label="Option key"
                        spellcheck="false"
                      />
                      <input
                        v-model="option.value"
                        class="input"
                        type="text"
                        placeholder="What this option means"
                        aria-label="Option description"
                      />
                      <button
                        type="button"
                        class="btn btn-ghost btn-icon btn-sm"
                        aria-label="Remove option"
                        @click="removeOption(question, optionIndex)"
                      >
                        <X :size="14" />
                      </button>
                    </div>
                  </div>
                  <button type="button" class="btn btn-ghost btn-sm" @click="addOption(question)">
                    <Plus :size="14" />
                    Add option
                  </button>
                </template>

                <template v-else-if="question.type === 'score'">
                  <p class="label console-q-label">Levels, low to high</p>
                  <div class="console-rows">
                    <div v-for="(level, levelIndex) in question.levels" :key="levelIndex" class="console-row console-level-row">
                      <span class="console-level-index mono">{{ levelIndex }}</span>
                      <input
                        v-model="question.levels[levelIndex]"
                        class="input"
                        type="text"
                        :placeholder="`Level ${levelIndex}`"
                        :aria-label="`Level ${levelIndex} label`"
                      />
                      <button
                        type="button"
                        class="btn btn-ghost btn-icon btn-sm"
                        aria-label="Remove level"
                        @click="removeLevel(question, levelIndex)"
                      >
                        <X :size="14" />
                      </button>
                    </div>
                  </div>
                  <button type="button" class="btn btn-ghost btn-sm" @click="addLevel(question)">
                    <Plus :size="14" />
                    Add level
                  </button>
                </template>

                <template v-else>
                  <button
                    type="button"
                    class="console-criteria-toggle"
                    :aria-expanded="question.criteriaOpen"
                    @click="question.criteriaOpen = !question.criteriaOpen"
                  >
                    <ChevronDown :size="15" :class="{ 'is-open': question.criteriaOpen }" />
                    <span>Optional criteria</span>
                    <span class="console-criteria-summary mono">
                      {{ question.trueCriteria || question.falseCriteria ? 'set' : 'none' }}
                    </span>
                  </button>
                  <div v-if="question.criteriaOpen" class="console-criteria">
                    <div class="console-criteria-field">
                      <label class="label" :for="`q-true-${question.uid}`">True means</label>
                      <input
                        :id="`q-true-${question.uid}`"
                        v-model="question.trueCriteria"
                        class="input"
                        type="text"
                        placeholder="Explicit refund request"
                      />
                    </div>
                    <div class="console-criteria-field">
                      <label class="label" :for="`q-false-${question.uid}`">False means</label>
                      <input
                        :id="`q-false-${question.uid}`"
                        v-model="question.falseCriteria"
                        class="input"
                        type="text"
                        placeholder="No refund request"
                      />
                    </div>
                  </div>
                </template>
              </div>
            </article>

            <button type="button" class="btn btn-primary console-run-mobile" :disabled="running || !availableModels.length" @click="run">
              <Loader2 v-if="running" :size="16" class="pub-spin" />
              <Play v-else :size="15" />
              {{ running ? 'Running…' : 'Run decision' }}
            </button>
          </div>
        </div>
      </section>

      <section ref="responseRef" class="console-response panel">
        <header class="console-response-head">
          <div class="console-tabs" role="tablist" aria-label="Response views">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              type="button"
              role="tab"
              class="console-tab"
              :class="{ 'is-active': activeTab === tab.id }"
              :aria-selected="activeTab === tab.id"
              @click="activeTab = tab.id"
            >
              {{ tab.label }}
            </button>
          </div>
          <CopyButton v-if="activeText" :text="activeText" :label="activeTab === 'response' ? 'Copy JSON' : 'Copy'" />
        </header>

        <div class="console-response-body">
          <template v-if="activeTab === 'response'">
            <div v-if="running" class="console-response-state" aria-live="polite">
              <span class="console-response-spinner"><Loader2 :size="22" class="pub-spin" /></span>
              <p class="console-response-state-title">Waiting for the answer object…</p>
              <p class="console-response-state-sub mono">{{ (elapsed / 1000).toFixed(1) }}s elapsed</p>
            </div>

            <div v-else-if="runError" class="console-response-state console-response-state-error">
              <span class="console-response-error-icon"><TriangleAlert :size="20" /></span>
              <p class="console-response-state-title">{{ runError.message }}</p>
              <p v-if="runError.code" class="mono tiny muted">code · {{ runError.code }}</p>
              <button type="button" class="btn btn-sm" @click="run">
                <RefreshCw :size="14" />
                Try again
              </button>
            </div>

            <div v-else-if="!result" class="console-response-state">
              <span class="console-response-empty-icon"><Terminal :size="20" /></span>
              <p class="console-response-state-title">Your response will appear here.</p>
              <p class="console-response-state-sub">
                Build a request, then run it. Answers come back as typed JSON.
              </p>
            </div>

            <template v-else>
              <div class="console-result-meta">
                <span class="badge badge-green">200 OK</span>
                <span class="console-result-meta-item">
                  <Clock :size="13" />
                  {{ formatDuration(result.elapsed_ms) }}
                </span>
                <span class="console-result-meta-item mono console-result-id">
                  {{ result.request_id }}
                </span>
                <span class="console-result-meta-item mono muted">
                  {{ result.protocol === 'systemone' ? 'System One' : 'Gemini Decisions' }}
                </span>
              </div>
              <pre class="console-json" v-html="highlightJson(responseJson)" />
            </template>
          </template>

          <template v-else-if="activeTab === 'request'">
            <pre class="console-json" v-html="highlightJson(requestJson)" />
            <p class="console-code-note mono">Provider request · POST {{ endpoint }}</p>
          </template>

          <template v-else>
            <pre class="console-code">{{ activeText }}</pre>
            <p class="console-code-note mono">
              {{ activeTab }} · POST {{ endpoint }} · requires an API key in your environment
            </p>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>
