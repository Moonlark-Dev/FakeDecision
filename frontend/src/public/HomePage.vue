<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowRight, ArrowUpRight, Braces, Layers, ShieldCheck, Waypoints } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import CodeBlock from '@/components/CodeBlock.vue'
import { get } from '@/lib/api'
import { useSession } from '@/lib/session'
import { formatTokenWindow } from '@/lib/format'
import { reportError } from '@/public/support'
import type { Model, Protocol } from '@/types/api'

const session = useSession()
const site = computed(() => session.state.site)
const user = computed(() => session.state.user)
const canRegister = computed(() => Boolean(site.value?.registration_enabled && site.value?.show_register_cta))

const models = ref<Model[]>([])
const modelsLoading = ref(true)
const modelsError = ref('')

function protocolsOf(model: Model): Protocol[] {
  if (model.protocols && model.protocols.length) return model.protocols
  if (model.protocol === 'both') return ['systemone', 'google']
  return [model.protocol]
}

function protocolLabel(protocol: Protocol): string {
  return protocol === 'systemone' ? 'System One' : 'Gemini Decisions'
}

const featuredModels = computed(() => models.value.slice(0, 2))

async function loadModels() {
  modelsLoading.value = true
  modelsError.value = ''
  try {
    const payload = await get<{ models: Model[] }>('/api/models')
    models.value = payload.models ?? []
  } catch (error) {
    modelsError.value = reportError(error, 'Could not load the model catalog.')
  } finally {
    modelsLoading.value = false
  }
}

onMounted(loadModels)

const requestSample = `POST /v1/systemone
Authorization: Bearer fd_live_••••

{
  "model": "jev-latest",
  "state": "The customer was charged twice for the same order.",
  "questions": {
    "refund": {
      "type": "noul",
      "instructions": "Does the customer ask for a refund?"
    },
    "action": {
      "type": "choice",
      "instructions": "Pick the next action.",
      "criteria": {
        "refund": "Refund the duplicate charge",
        "replace": "Send a replacement"
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this?",
      "criteria": ["Low", "Medium", "High"]
    }
  }
}`

const responseSample = `200 OK
X-Request-Id: req_8f2c•••

{
  "model": "jev-latest",
  "answers": {
    "refund": { "type": "noul", "noul": 0.91 },
    "action": {
      "type": "choice",
      "choice": "refund",
      "probabilities": { "refund": 0.88, "replace": 0.12 },
      "confidence": 0.88
    },
    "urgency": {
      "type": "score",
      "score": 1.64,
      "probabilities": { "0": 0.07, "1": 0.22, "2": 0.71 },
      "confidence": 0.71,
      "legend": { "0": "Low", "1": "Medium", "2": "High" }
    }
  },
  "usage": { "input_tokens": 48, "output_tokens": 0 },
  "rounding": { "probabilityDecimals": 2, "scoreDecimals": 2 }
}`

const primitives = [
  {
    index: '01',
    type: 'noul',
    title: 'Calibrated yes / no',
    body: 'One probability for a binary question. Bounded to [0.01, 0.99] so downstream code never has to special-case a certainty.',
    shape: '{ noul: 0.91 }',
  },
  {
    index: '02',
    type: 'choice',
    title: 'Closed-set choice',
    body: 'A bounded set of options with a distribution across all of them. The selected label is always the argmax, so it is safe to switch on.',
    shape: '{ choice: "refund", probabilities }',
  },
  {
    index: '03',
    type: 'score',
    title: 'Rubric score',
    body: 'A probability-weighted expectation over ordered levels, plus the full distribution and the legend you supplied.',
    shape: '{ score: 1.64, legend }',
  },
]

const pipelineSteps = [
  {
    label: 'Request',
    detail: 'state + typed questions',
    lines: ['"state": "…"', '"questions": { "refund": … }'],
  },
  {
    label: 'Decision',
    detail: 'schema validated',
    lines: ['P(question) per type', 'argmax · expectation'],
  },
  {
    label: 'Response',
    detail: 'answers object',
    lines: ['"noul": 0.91', '"choice": "refund"', '"score": 1.64'],
  },
]
</script>

<template>
  <main class="pub-home">
    <section class="pub-hero">
      <div class="pub-hero-grid" aria-hidden="true" />
      <div class="container pub-hero-inner">
        <div class="pub-hero-copy">
          <p class="eyebrow">Decision API · v1</p>
          <h1 class="pub-hero-title">
            Typed decisions<br />
            for software.
          </h1>
          <p class="pub-hero-lede">
            {{ site?.description || 'Calibrated yes/no probabilities, bounded choices and rubric scores over one shared context. One endpoint, no output tokens.' }}
          </p>

          <div class="pub-hero-actions">
            <RouterLink v-if="canRegister && !user" to="/register" class="btn btn-primary btn-lg">
              Start building
              <ArrowRight :size="16" />
            </RouterLink>
            <RouterLink v-else-if="user" to="/console" class="btn btn-primary btn-lg">
              Open console
              <ArrowRight :size="16" />
            </RouterLink>
            <RouterLink to="/docs" class="btn btn-lg">Read the docs</RouterLink>
          </div>

          <div class="pub-hero-specs">
            <div class="pub-hero-spec">
              <span class="pub-hero-spec-key mono">POST</span>
              <span class="pub-hero-spec-value"><code>/v1/systemone</code></span>
            </div>
            <div class="pub-hero-spec">
              <span class="pub-hero-spec-key mono">POST</span>
              <span class="pub-hero-spec-value"><code>/v1beta/decisions</code></span>
            </div>
            <div class="pub-hero-spec">
              <span class="pub-hero-spec-key mono">HEADER</span>
              <span class="pub-hero-spec-value"><code>X-Decision-Timeout-Ms</code></span>
            </div>
          </div>
        </div>

        <div class="pub-hero-panel">
          <div class="pub-decision-card">
            <header class="pub-decision-head">
              <span class="pub-method mono">POST</span>
              <code class="pub-decision-path">/v1/systemone</code>
              <span class="pub-status mono">200 OK</span>
            </header>

            <div class="pub-decision-state">
              <span class="pub-mono-label mono">state</span>
              <p>“The customer was charged twice for the same order and asked for a refund.”</p>
            </div>

            <div class="pub-decision-questions">
              <div class="pub-dq">
                <div class="pub-dq-head">
                  <span class="pub-dq-name">refund <span class="badge">noul</span></span>
                  <span class="pub-dq-value mono">0.91</span>
                </div>
                <div class="pub-meter" role="img" aria-label="Probability of refund question: 0.91">
                  <span class="pub-meter-fill" style="width: 91%" />
                </div>
                <p class="pub-dq-caption mono">P(true) · explicit request</p>
              </div>

              <div class="pub-dq">
                <div class="pub-dq-head">
                  <span class="pub-dq-name">action <span class="badge">choice</span></span>
                  <span class="pub-dq-value mono">refund</span>
                </div>
                <div class="pub-choice-bars">
                  <div class="pub-choice-bar">
                    <span class="pub-choice-label mono">refund</span>
                    <span class="pub-meter pub-meter-sm"><span class="pub-meter-fill" style="width: 88%" /></span>
                    <span class="pub-choice-value mono">.88</span>
                  </div>
                  <div class="pub-choice-bar">
                    <span class="pub-choice-label mono">replace</span>
                    <span class="pub-meter pub-meter-sm"><span class="pub-meter-fill pub-meter-fill-muted" style="width: 12%" /></span>
                    <span class="pub-choice-value mono">.12</span>
                  </div>
                </div>
              </div>

              <div class="pub-dq">
                <div class="pub-dq-head">
                  <span class="pub-dq-name">urgency <span class="badge">score</span></span>
                  <span class="pub-dq-value mono">1.64</span>
                </div>
                <div class="pub-score-bars" role="img" aria-label="Urgency distribution: low 7 percent, medium 22 percent, high 71 percent">
                  <div class="pub-score-col"><span class="pub-score-fill" style="height: 7%" /><span class="mono">.07</span></div>
                  <div class="pub-score-col"><span class="pub-score-fill" style="height: 22%" /><span class="mono">.22</span></div>
                  <div class="pub-score-col"><span class="pub-score-fill" style="height: 71%" /><span class="mono">.71</span></div>
                  <div class="pub-score-col pub-score-col-lime" aria-hidden="true" />
                </div>
                <p class="pub-dq-caption mono">Low · Medium · High</p>
              </div>
            </div>

            <footer class="pub-decision-foot">
              <span class="mono">usage · in 48 / out 0</span>
              <span class="mono">rounded 2dp</span>
            </footer>
            <span class="pub-decision-notch" aria-hidden="true" />
          </div>
        </div>
      </div>
    </section>

    <div class="container">
      <div class="pub-band">
        <div class="pub-band-item">
          <Braces :size="16" />
          <div>
            <p class="pub-band-title">Structured answers</p>
            <p class="pub-band-sub mono">noul · choice · score</p>
          </div>
        </div>
        <div class="pub-band-item">
          <Layers :size="16" />
          <div>
            <p class="pub-band-title">One shared state</p>
            <p class="pub-band-sub mono">many questions per request</p>
          </div>
        </div>
        <div class="pub-band-item">
          <ShieldCheck :size="16" />
          <div>
            <p class="pub-band-title">Validated output</p>
            <p class="pub-band-sub mono">argmax + distribution</p>
          </div>
        </div>
        <div class="pub-band-item">
          <Waypoints :size="16" />
          <div>
            <p class="pub-band-title">Two protocols</p>
            <p class="pub-band-sub mono">drop-in request shapes</p>
          </div>
        </div>
      </div>
    </div>

    <section class="section">
      <div class="container">
        <div class="pub-section-head">
          <div>
            <p class="eyebrow">Primitives</p>
            <h2 class="pub-section-title">Three question types. Nothing to parse.</h2>
          </div>
          <p class="pub-section-note">
            Every answer is a number or a label you declared in the request. There is no free-text field to
            validate, retry or regex.
          </p>
        </div>

        <div class="pub-primitives">
          <article v-for="primitive in primitives" :key="primitive.type" class="pub-primitive">
            <div class="pub-primitive-head">
              <span class="pub-primitive-index mono">{{ primitive.index }}</span>
              <span class="badge" :class="`badge-${primitive.type === 'noul' ? 'blue' : primitive.type === 'choice' ? 'lime' : 'amber'}`">
                {{ primitive.type }}
              </span>
            </div>
            <h3 class="pub-primitive-title">{{ primitive.title }}</h3>
            <p class="pub-primitive-body">{{ primitive.body }}</p>
            <p class="pub-primitive-shape mono">{{ primitive.shape }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="pub-pipeline-section">
      <div class="container">
        <div class="pub-section-head">
          <div>
            <p class="eyebrow">Pipeline</p>
            <h2 class="pub-section-title">One call, from state to typed answer.</h2>
          </div>
        </div>

        <div class="pub-pipeline">
          <template v-for="(step, index) in pipelineSteps" :key="step.label">
            <div class="pub-pipe-node" :class="{ 'pub-pipe-node-core': index === 1 }">
              <div v-if="index === 1" class="pub-pipe-core-mark">
                <BrandLogo compact :size="22" />
                <span class="pub-pipe-core-name mono">Decision API</span>
              </div>
              <p class="pub-pipe-label mono">{{ step.label }}</p>
              <p class="pub-pipe-detail">{{ step.detail }}</p>
              <div class="pub-pipe-lines">
                <code v-for="line in step.lines" :key="line" class="pub-pipe-line mono">{{ line }}</code>
              </div>
            </div>
            <div v-if="index < pipelineSteps.length - 1" class="pub-pipe-link" aria-hidden="true">
              <svg viewBox="0 0 64 12" fill="none" preserveAspectRatio="none">
                <path d="M0 6h56" stroke="currentColor" stroke-width="1" stroke-dasharray="3 4" />
                <path d="m56 2 6 4-6 4" stroke="currentColor" stroke-width="1" />
              </svg>
            </div>
          </template>
        </div>

        <div class="pub-guarantees">
          <span class="pub-guarantee"><span class="pub-guarantee-dot" />Schema checked</span>
          <span class="pub-guarantee"><span class="pub-guarantee-dot" />Argmax consistent</span>
          <span class="pub-guarantee"><span class="pub-guarantee-dot" />Rounded once, server-side</span>
          <span class="pub-guarantee"><span class="pub-guarantee-dot" />No output tokens</span>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="pub-section-head">
          <div>
            <p class="eyebrow">Example</p>
            <h2 class="pub-section-title">A request you could send today.</h2>
          </div>
          <RouterLink to="/docs#quickstart" class="pub-text-link">
            Full quickstart
            <ArrowUpRight :size="15" />
          </RouterLink>
        </div>

        <div class="pub-example-grid">
          <CodeBlock :code="requestSample" label="request · system one" max-height="520px" />
          <CodeBlock :code="responseSample" label="response · 200" max-height="520px" />
        </div>
      </div>
    </section>

    <section class="pub-models-section">
      <div class="container">
        <div class="pub-section-head">
          <div>
            <p class="eyebrow">Models</p>
            <h2 class="pub-section-title">Served from one deployment.</h2>
          </div>
          <RouterLink to="/models" class="pub-text-link">
            All models
            <ArrowUpRight :size="15" />
          </RouterLink>
        </div>

        <div v-if="modelsLoading" class="pub-models-grid" aria-busy="true">
          <div v-for="index in 2" :key="index" class="pub-model-card pub-model-card-loading">
            <span class="pub-skeleton pub-skeleton-title" />
            <span class="pub-skeleton" />
            <span class="pub-skeleton pub-skeleton-short" />
          </div>
        </div>

        <div v-else-if="modelsError" class="pub-inline-error">
          <p>{{ modelsError }}</p>
          <button type="button" class="btn btn-sm" @click="loadModels">Retry</button>
        </div>

        <div v-else-if="!featuredModels.length" class="pub-inline-note">
          The catalog is being updated. Check the <RouterLink to="/models">models page</RouterLink> shortly.
        </div>

        <div v-else class="pub-models-grid">
          <RouterLink
            v-for="model in featuredModels"
            :key="model.name"
            :to="{ path: '/models', hash: `#${model.name}` }"
            class="pub-model-card"
          >
            <div class="pub-model-head">
              <div>
                <h3 class="pub-model-name">{{ model.display_name }}</h3>
                <p class="pub-model-id mono">{{ model.name }}</p>
              </div>
              <ArrowUpRight :size="17" class="pub-model-arrow" />
            </div>
            <div class="pub-model-badges">
              <span v-for="protocol in protocolsOf(model)" :key="protocol" class="badge badge-blue">
                {{ protocolLabel(protocol) }}
              </span>
              <span class="badge">{{ formatTokenWindow(model.context_window) }} context</span>
            </div>
            <p class="pub-model-desc">{{ model.description }}</p>
            <p class="pub-model-foot mono">POST · {{ protocolsOf(model)[0] === 'systemone' ? '/v1/systemone' : '/v1beta/decisions' }}</p>
          </RouterLink>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="pub-cta">
          <div class="pub-cta-grid" aria-hidden="true" />
          <div class="pub-cta-copy">
            <p class="eyebrow pub-cta-eyebrow">Start here</p>
            <h2 class="pub-cta-title">Replace the prompt with a schema.</h2>
            <p class="pub-cta-body">
              Create a key, send one request, and read the answer object. The console includes a playground,
              usage history and key management.
            </p>
            <div class="pub-cta-actions">
              <RouterLink v-if="canRegister && !user" to="/register" class="btn btn-primary btn-lg">
                Get started
                <ArrowRight :size="16" />
              </RouterLink>
              <RouterLink v-else-if="user" to="/console" class="btn btn-primary btn-lg">
                Open console
                <ArrowRight :size="16" />
              </RouterLink>
              <RouterLink v-else to="/login" class="btn btn-primary btn-lg">Sign in</RouterLink>
              <RouterLink to="/docs" class="btn btn-lg pub-cta-secondary">Read the docs</RouterLink>
            </div>
          </div>
          <div class="pub-cta-meta">
            <div class="pub-cta-meta-item">
              <span class="mono">01</span>
              <p>Create an API key</p>
            </div>
            <div class="pub-cta-meta-item">
              <span class="mono">02</span>
              <p>Send a typed request</p>
            </div>
            <div class="pub-cta-meta-item">
              <span class="mono">03</span>
              <p>Read the answer object</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
