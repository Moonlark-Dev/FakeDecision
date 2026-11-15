<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowRight, ArrowUpRight, Braces, Image, RefreshCw } from 'lucide-vue-next'
import CodeBlock from '@/components/CodeBlock.vue'
import EmptyState from '@/components/EmptyState.vue'
import { get } from '@/lib/api'
import { useSession } from '@/lib/session'
import { formatTokenWindow } from '@/lib/format'
import { reportError } from '@/public/support'
import type { Model, Protocol } from '@/types/api'

const route = useRoute()
const session = useSession()
const canRegister = computed(() => Boolean(session.state.site?.registration_enabled))
const models = ref<Model[]>([])
const loading = ref(true)
const error = ref('')

function protocolsOf(model: Model): Protocol[] {
  if (model.protocols && model.protocols.length) return model.protocols
  if (model.protocol === 'both') return ['systemone', 'google']
  return [model.protocol]
}

function protocolLabel(protocol: Protocol): string {
  return protocol === 'systemone' ? 'System One' : 'Gemini Decisions'
}

function endpointFor(protocol: Protocol): string {
  return protocol === 'systemone' ? '/v1/systemone' : '/v1beta/decisions'
}

function sampleFor(model: Model): string {
  const primary = protocolsOf(model)[0]
  if (primary === 'google') {
    return `{
  "model": "${model.name}",
  "input": "The customer was charged twice for the same order.",
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
    }
  }
}`
  }
  return `{
  "model": "${model.name}",
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
    }
  }
}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const payload = await get<{ models: Model[] }>('/api/models')
    models.value = payload.models ?? []
    await nextTick()
    scrollToHash()
  } catch (err) {
    error.value = reportError(err, 'Could not load the model catalog.')
  } finally {
    loading.value = false
  }
}

function scrollToHash() {
  const hash = route.hash.replace('#', '')
  if (!hash) return
  const target = document.getElementById(hash)
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(() => route.hash, () => void nextTick(scrollToHash))
onMounted(load)

const totals = computed(() => ({
  models: models.value.length,
  protocols: new Set(models.value.flatMap(protocolsOf)).size,
  context: models.value.reduce((max, model) => Math.max(max, model.context_window || 0), 0),
}))
</script>

<template>
  <main class="pub-page">
    <section class="pub-page-head">
      <div class="container">
        <p class="eyebrow">Model catalog</p>
        <h1 class="pub-page-title">Models</h1>
        <p class="pub-page-lede">
          Every model on this deployment speaks at least one of the two decision protocols. Protocol determines
          the request shape, not the answers you get back.
        </p>
        <div class="pub-page-meta">
          <span class="mono">{{ totals.models }} models</span>
          <span class="pub-meta-dot" aria-hidden="true" />
          <span class="mono">{{ totals.protocols }} protocol{{ totals.protocols === 1 ? '' : 's' }}</span>
          <span class="pub-meta-dot" aria-hidden="true" />
          <span class="mono">up to {{ formatTokenWindow(totals.context) }} context</span>
        </div>
      </div>
    </section>

    <div class="container">
      <div class="pub-protocol-cards">
        <article class="pub-protocol-card">
          <div class="pub-protocol-card-head">
            <span class="badge badge-blue">System One</span>
            <code class="mono">POST /v1/systemone</code>
          </div>
          <p>
            A single <code>state</code> plus a map of named questions. Answers include usage and rounding metadata
            alongside the typed results.
          </p>
          <div class="pub-protocol-card-foot">
            <span class="mono">auth · Authorization: Bearer</span>
            <RouterLink :to="{ path: '/docs', hash: '#system-one' }" class="pub-text-link">
              Reference
              <ArrowUpRight :size="14" />
            </RouterLink>
          </div>
        </article>
        <article class="pub-protocol-card">
          <div class="pub-protocol-card-head">
            <span class="badge badge-green">Gemini Decisions</span>
            <code class="mono">POST /v1beta/decisions</code>
          </div>
          <p>
            A request shape compatible with Gemini-style decisions: <code>input</code> may be text or content
            blocks, including images and documents.
          </p>
          <div class="pub-protocol-card-foot">
            <span class="mono">auth · x-goog-api-key</span>
            <RouterLink :to="{ path: '/docs', hash: '#gemini-decisions' }" class="pub-text-link">
              Reference
              <ArrowUpRight :size="14" />
            </RouterLink>
          </div>
        </article>
      </div>
    </div>

    <section class="pub-models-page-section">
      <div class="container">
        <div v-if="loading" class="pub-model-list" aria-busy="true">
          <div v-for="index in 2" :key="index" class="pub-model-detail pub-model-card-loading">
            <span class="pub-skeleton pub-skeleton-title" />
            <span class="pub-skeleton" />
            <span class="pub-skeleton" />
            <span class="pub-skeleton pub-skeleton-short" />
          </div>
        </div>

        <div v-else-if="error" class="pub-inline-error">
          <p>{{ error }}</p>
          <button type="button" class="btn btn-sm" @click="load">
            <RefreshCw :size="14" />
            Retry
          </button>
        </div>

        <EmptyState
          v-else-if="!models.length"
          title="No models are enabled"
          description="The catalog is empty right now. Documentation and console access are unaffected."
        >
          <RouterLink to="/docs" class="btn btn-sm">Read the docs</RouterLink>
        </EmptyState>

        <div v-else class="pub-model-list">
          <article v-for="model in models" :id="model.name" :key="model.name" class="pub-model-detail">
            <header class="pub-model-detail-head">
              <div class="pub-model-detail-id">
                <h2 class="pub-model-detail-name">{{ model.display_name }}</h2>
                <p class="mono">{{ model.name }}</p>
              </div>
              <div class="pub-model-badges">
                <span
                  v-for="protocol in protocolsOf(model)"
                  :key="protocol"
                  class="badge"
                  :class="protocol === 'systemone' ? 'badge-blue' : 'badge-green'"
                >
                  {{ protocolLabel(protocol) }}
                </span>
              </div>
            </header>

            <p class="pub-model-detail-desc">{{ model.description }}</p>

            <div class="pub-model-facts">
              <div class="pub-model-fact">
                <span class="pub-mono-label mono">Context window</span>
                <span>{{ formatTokenWindow(model.context_window) }} tokens</span>
              </div>
              <div class="pub-model-fact">
                <span class="pub-mono-label mono">Endpoint</span>
                <code>{{ endpointFor(protocolsOf(model)[0]) }}</code>
              </div>
              <div class="pub-model-fact">
                <span class="pub-mono-label mono">Answer types</span>
                <span>noul · choice · score</span>
              </div>
            </div>

            <div class="pub-model-sample-head">
              <span class="pub-mono-label mono">Request</span>
              <span class="pub-model-sample-note">
                <Image v-if="protocolsOf(model).includes('google')" :size="13" />
                {{ protocolsOf(model).includes('google') ? 'text or content blocks' : 'text or structured state' }}
              </span>
            </div>
            <CodeBlock :code="sampleFor(model)" :label="`POST ${endpointFor(protocolsOf(model)[0])}`" max-height="340px" />

            <footer class="pub-model-detail-foot">
              <RouterLink :to="{ path: '/docs', hash: protocolsOf(model)[0] === 'systemone' ? '#system-one' : '#gemini-decisions' }" class="pub-text-link">
                <Braces :size="14" />
                Protocol reference
              </RouterLink>
              <div class="pub-model-detail-actions">
                <RouterLink :to="canRegister ? '/register' : '/login'" class="btn btn-sm">
                  {{ canRegister ? 'Get an API key' : 'Sign in for a key' }}
                </RouterLink>
                <RouterLink to="/console/playground" class="btn btn-primary btn-sm">
                  Try in playground
                  <ArrowRight :size="14" />
                </RouterLink>
              </div>
            </footer>
          </article>
        </div>
      </div>
    </section>

    <section class="section-tight">
      <div class="container">
        <div class="pub-section-head">
          <div>
            <p class="eyebrow">At a glance</p>
            <h2 class="pub-section-title">Choose by protocol and context.</h2>
          </div>
        </div>

        <div class="card pub-compare-wrap">
          <table class="table">
            <thead>
              <tr>
                <th scope="col">Model</th>
                <th scope="col">Protocols</th>
                <th scope="col">Context</th>
                <th scope="col">Primary endpoint</th>
                <th scope="col"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="model in models" :key="model.name">
                <td>
                  <RouterLink :to="{ path: '/models', hash: `#${model.name}` }" class="pub-compare-name">
                    <span class="pub-compare-display">{{ model.display_name }}</span>
                    <span class="mono tiny muted">{{ model.name }}</span>
                  </RouterLink>
                </td>
                <td>
                  <span class="pub-compare-badges">
                    <span
                      v-for="protocol in protocolsOf(model)"
                      :key="protocol"
                      class="badge"
                      :class="protocol === 'systemone' ? 'badge-blue' : 'badge-green'"
                    >
                      {{ protocolLabel(protocol) }}
                    </span>
                  </span>
                </td>
                <td class="mono">{{ formatTokenWindow(model.context_window) }}</td>
                <td><code class="mono tiny">{{ endpointFor(protocolsOf(model)[0]) }}</code></td>
                <td class="pub-compare-action">
                  <RouterLink to="/console/playground" class="pub-text-link">
                    Open
                    <ArrowUpRight :size="14" />
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="pub-footnote">
          Availability is controlled per deployment. If a model is absent from this page, it is not enabled.
        </p>
      </div>
    </section>
  </main>
</template>
