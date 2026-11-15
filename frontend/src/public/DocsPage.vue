<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowUpRight, KeyRound } from 'lucide-vue-next'
import CodeBlock from '@/components/CodeBlock.vue'
import { get } from '@/lib/api'
import { useSession } from '@/lib/session'
import { formatTokenWindow } from '@/lib/format'
import { reportError } from '@/public/support'
import type { Model, Protocol } from '@/types/api'

const session = useSession()
const site = computed(() => session.state.site)
const user = computed(() => session.state.user)

type Lang = 'curl' | 'python' | 'typescript'
const lang = ref<Lang>('curl')
const langs: { id: Lang; label: string }[] = [
  { id: 'curl', label: 'cURL' },
  { id: 'python', label: 'Python' },
  { id: 'typescript', label: 'TypeScript' },
]

const quickstartSnippets: Record<Lang, string> = {
  curl: `curl -sS "$NOEMA_BASE_URL/v1/systemone" \\
  -H "Authorization: Bearer $NOEMA_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "jev-latest",
    "state": "The customer was charged twice.",
    "questions": {
      "refund": {
        "type": "noul",
        "instructions": "Does the customer ask for a refund?"
      }
    }
  }'`,
  python: `import os
import requests

response = requests.post(
    f"{os.environ['NOEMA_BASE_URL']}/v1/systemone",
    headers={"Authorization": f"Bearer {os.environ['NOEMA_API_KEY']}"},
    json={
        "model": "jev-latest",
        "state": "The customer was charged twice.",
        "questions": {
            "refund": {
                "type": "noul",
                "instructions": "Does the customer ask for a refund?",
            }
        },
    },
    timeout=120,
)
response.raise_for_status()
print(response.json()["answers"]["refund"]["noul"])`,
  typescript: `const baseUrl = process.env.NOEMA_BASE_URL ?? 'https://api.noema.dev'

type NoulAnswer = { type: 'noul'; noul: number }
interface DecisionResponse {
  model?: string
  answers: Record<string, NoulAnswer>
}

const response = await fetch(\`\${baseUrl}/v1/systemone\`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: \`Bearer \${process.env.NOEMA_API_KEY}\`,
  },
  body: JSON.stringify({
    model: 'jev-latest',
    state: 'The customer was charged twice.',
    questions: {
      refund: {
        type: 'noul',
        instructions: 'Does the customer ask for a refund?',
      },
    },
  }),
})

if (!response.ok) {
  throw new Error(\`Decision request failed: \${response.status}\`)
}
const data = (await response.json()) as DecisionResponse
console.log(data.answers.refund.noul)`,
}

const systemoneRequest = `{
  "model": "jev-latest",
  "state": "The customer was charged twice.",
  "questions": {
    "refund": {
      "type": "noul",
      "instructions": "Does the customer ask for a refund?",
      "criteria": { "true": "Explicit refund request", "false": "No request" }
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

const systemoneResponse = `{
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

const systemoneCurl = `curl -sS "$NOEMA_BASE_URL/v1/systemone" \\
  -H "Authorization: Bearer $NOEMA_API_KEY" \\
  -H "Content-Type: application/json" \\
  -H "X-Decision-Timeout-Ms: 60000" \\
  -d @request.json`

const geminiRequest = `{
  "model": "gemini-decision-1",
  "input": "The customer was charged twice.",
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

const geminiMultimodal = `{
  "model": "gemini-decision-1",
  "input": [
    { "type": "text", "text": "Does this invoice appear to be paid in full?" },
    {
      "type": "image",
      "mime_type": "image/png",
      "uri": "https://storage.example/invoice-4021.png"
    }
  ],
  "questions": {
    "paid": {
      "type": "noul",
      "instructions": "Is the invoice paid in full?"
    }
  }
}`

const geminiResponse = `{
  "answers": {
    "refund": { "type": "noul", "noul": 0.91, "confidence": 0.91 },
    "action": {
      "type": "choice",
      "choice": "refund",
      "probabilities": { "refund": 0.88, "replace": 0.12 },
      "confidence": 0.88
    }
  }
}`

const geminiCurl = `curl -sS "$NOEMA_BASE_URL/v1beta/decisions" \\
  -H "x-goog-api-key: $NOEMA_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d @request.json

# Also accepted:
# POST /v1beta/models/gemini-decision-1:decisions
# POST /v1/decisions`

const noulShape = `{
  "refund": {
    "type": "noul",
    "instructions": "Does the customer ask for a refund?",
    "criteria": { "true": "Explicit request", "false": "No request" }
  }
}`

const choiceShape = `{
  "action": {
    "type": "choice",
    "instructions": "Pick the next action.",
    "criteria": {
      "refund": "Refund the duplicate charge",
      "replace": "Send a replacement",
      "escalate": "Escalate the case"
    }
  }
}`

const scoreShape = `{
  "urgency": {
    "type": "score",
    "instructions": "How urgent is this?",
    "criteria": ["Low", "Medium", "High"]
  }
}`

const errorSystemone = `{
  "error": {
    "message": "API key missing",
    "type": "invalid_api_key",
    "code": "invalid_api_key",
    "status": 401
  }
}`

const errorGemini = `{
  "error": {
    "code": 401,
    "message": "API key missing",
    "status": "invalid_api_key"
  }
}`

const models = ref<Model[]>([])
const modelsError = ref('')

function protocolsOf(model: Model): Protocol[] {
  if (model.protocols && model.protocols.length) return model.protocols
  if (model.protocol === 'both') return ['systemone', 'google']
  return [model.protocol]
}

function protocolLabel(protocol: Protocol): string {
  return protocol === 'systemone' ? 'System One' : 'Gemini Decisions'
}

async function loadModels() {
  try {
    const payload = await get<{ models: Model[] }>('/api/models')
    models.value = payload.models ?? []
  } catch (error) {
    modelsError.value = reportError(error, 'Could not load the model catalog.')
  }
}

const groups = [
  {
    title: 'Getting started',
    items: [
      { id: 'overview', label: 'Overview' },
      { id: 'quickstart', label: 'Quickstart' },
      { id: 'authentication', label: 'Authentication' },
    ],
  },
  {
    title: 'Endpoints',
    items: [
      { id: 'system-one', label: 'System One' },
      { id: 'gemini-decisions', label: 'Gemini Decisions' },
      { id: 'model-listing', label: 'Model listing' },
    ],
  },
  {
    title: 'Reference',
    items: [
      { id: 'questions', label: 'Question types' },
      { id: 'timeout', label: 'Timeouts' },
      { id: 'errors', label: 'Errors' },
      { id: 'models', label: 'Models' },
      { id: 'limits', label: 'Limits' },
    ],
  },
  {
    title: 'Deployment',
    items: [
      { id: 'privacy', label: 'Privacy' },
      { id: 'terms', label: 'Terms' },
      { id: 'security', label: 'Security' },
    ],
  },
]

const allIds = groups.flatMap((group) => group.items.map((item) => item.id))
const activeSection = ref('overview')
let observer: IntersectionObserver | null = null

onMounted(async () => {
  await loadModels()
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      if (visible[0]) activeSection.value = visible[0].target.id
    },
    { rootMargin: '-96px 0px -68% 0px', threshold: [0, 1] },
  )
  for (const id of allIds) {
    const element = document.getElementById(id)
    if (element) observer.observe(element)
  }
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <main class="pub-docs">
    <div class="container pub-docs-head">
      <p class="eyebrow">Documentation</p>
      <h1 class="pub-docs-title">Decision API</h1>
      <p class="pub-docs-lede">
        Two protocols, one answer format. Send a state or input, declare typed questions, and receive calibrated
        probabilities, a bounded choice and a rubric score. Answers are always JSON that matches the schema you
        declared.
      </p>
      <div class="pub-docs-meta">
        <span class="mono">v1</span>
        <span class="pub-meta-dot" aria-hidden="true" />
        <span class="mono">2 protocols</span>
        <span class="pub-meta-dot" aria-hidden="true" />
        <span class="mono">3 question types</span>
      </div>
    </div>

    <div class="container pub-docs-layout">
      <aside class="pub-docs-side">
        <nav class="pub-docs-nav" aria-label="Documentation sections">
          <div v-for="group in groups" :key="group.title" class="pub-docs-nav-group">
            <p class="pub-docs-nav-title mono">{{ group.title }}</p>
            <a
              v-for="item in group.items"
              :key="item.id"
              :href="`#${item.id}`"
              class="pub-docs-nav-link"
              :class="{ 'is-active': activeSection === item.id }"
            >
              {{ item.label }}
            </a>
          </div>
        </nav>

        <div class="pub-docs-side-card">
          <span class="pub-docs-side-icon"><KeyRound :size="15" /></span>
          <p class="pub-docs-side-title">Need an API key?</p>
          <p class="pub-docs-side-body">Keys are created in the console and shown once.</p>
          <RouterLink v-if="user" to="/console/keys" class="btn btn-sm">Manage keys</RouterLink>
          <template v-else>
            <RouterLink v-if="site?.registration_enabled" to="/register" class="btn btn-primary btn-sm">
              Create account
            </RouterLink>
            <RouterLink v-else to="/login" class="btn btn-sm">Sign in</RouterLink>
          </template>
        </div>
      </aside>

      <article class="pub-docs-body">
        <section id="overview" class="pub-doc-section">
          <h2 class="pub-doc-h2">Overview</h2>
          <p>
            The Decision API turns a shared context and a set of questions into a typed answer object. There is
            no generated text: you declare the shape of the answer you need, and the API returns exactly that
            shape.
          </p>

          <div class="pub-doc-callout">
            <p>
              <strong>Base URL.</strong> All examples read <code>NOEMA_BASE_URL</code> from the environment.
              Set it to this deployment's origin, for example <code>https://api.noema.dev</code>.
            </p>
          </div>

          <div class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Protocol</th>
                  <th scope="col">Endpoint</th>
                  <th scope="col">Auth header</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>System One</td>
                  <td><code>POST /v1/systemone</code></td>
                  <td><code>Authorization: Bearer fd_live_…</code></td>
                </tr>
                <tr>
                  <td>Gemini Decisions</td>
                  <td><code>POST /v1beta/decisions</code></td>
                  <td><code>x-goog-api-key: fd_live_…</code></td>
                </tr>
              </tbody>
            </table>
          </div>

          <h3 class="pub-doc-h3">What you get back</h3>
          <ul class="pub-doc-list">
            <li><code>noul</code> — P(true), bounded to <code>[0.01, 0.99]</code>.</li>
            <li><code>choice</code> — the selected label plus a distribution over every declared option.</li>
            <li><code>score</code> — the expected level plus the distribution and your legend.</li>
          </ul>
        </section>

        <section id="quickstart" class="pub-doc-section">
          <h2 class="pub-doc-h2">Quickstart</h2>
          <ol class="pub-doc-steps">
            <li>Create an API key in the <RouterLink to="/console/keys">console</RouterLink>.</li>
            <li>Export <code>NOEMA_BASE_URL</code> and <code>NOEMA_API_KEY</code>.</li>
            <li>Send a request and read the <code>answers</code> object.</li>
          </ol>

          <div class="pub-doc-tabs" role="tablist" aria-label="Quickstart language">
            <button
              v-for="option in langs"
              :key="option.id"
              type="button"
              role="tab"
              class="pub-doc-tab"
              :class="{ 'is-active': lang === option.id }"
              :aria-selected="lang === option.id"
              @click="lang = option.id"
            >
              {{ option.label }}
            </button>
          </div>
          <CodeBlock :code="quickstartSnippets[lang]" :label="`request · ${lang}`" max-height="460px" />

          <div class="pub-doc-callout">
            <p>
              A successful response returns <code>200</code> and an <code>X-Request-Id</code> header. Keep that
              header when contacting support — it identifies one decision request.
            </p>
          </div>
        </section>

        <section id="authentication" class="pub-doc-section">
          <h2 class="pub-doc-h2">Authentication</h2>
          <p>
            Both protocols authenticate with an API key created in the console. Only a hash of each key is
            stored; the secret is displayed once, at creation time.
          </p>

          <div class="pub-doc-split">
            <div class="pub-doc-panel">
              <p class="pub-doc-panel-title mono">System One</p>
              <CodeBlock code='Authorization: Bearer fd_live_…' label="header" />
            </div>
            <div class="pub-doc-panel">
              <p class="pub-doc-panel-title mono">Gemini Decisions</p>
              <CodeBlock code='x-goog-api-key: fd_live_…' label="header" />
            </div>
          </div>

          <p class="pub-doc-note">
            Gemini Decisions also accepts <code>Authorization: Bearer</code> and a <code>key</code> query
            parameter. Prefer headers so keys never appear in URLs or logs.
          </p>
          <p class="pub-doc-note">
            Revoking a key takes effect immediately for both protocols. Requests made with a revoked key fail
            with <code>401</code>.
          </p>
        </section>

        <section id="system-one" class="pub-doc-section">
          <h2 class="pub-doc-h2">System One</h2>
          <p class="pub-doc-endpoint"><span class="pub-method mono">POST</span> <code>/v1/systemone</code></p>
          <p>
            Send a <code>state</code> and a map of named questions. If <code>model</code> is omitted, the
            deployment's default model is used. <code>boolean</code> is accepted as an alias for
            <code>noul</code>.
          </p>

          <h3 class="pub-doc-h3">Request</h3>
          <CodeBlock :code="systemoneRequest" label="json" max-height="480px" />
          <CodeBlock :code="systemoneCurl" label="curl" />

          <h3 class="pub-doc-h3">Response</h3>
          <CodeBlock :code="systemoneResponse" label="200 · application/json" max-height="480px" />

          <div class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Type</th>
                  <th scope="col">Notes</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>model</code></td>
                  <td>string</td>
                  <td>The model that produced the answers.</td>
                </tr>
                <tr>
                  <td><code>answers</code></td>
                  <td>object</td>
                  <td>One entry per question id, keyed by the id you supplied.</td>
                </tr>
                <tr>
                  <td><code>usage.input_tokens</code></td>
                  <td>number</td>
                  <td>Estimated input size. <code>output_tokens</code> is always <code>0</code>.</td>
                </tr>
                <tr>
                  <td><code>rounding</code></td>
                  <td>object</td>
                  <td>Decimal precision applied once, server-side.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="gemini-decisions" class="pub-doc-section">
          <h2 class="pub-doc-h2">Gemini Decisions</h2>
          <p class="pub-doc-endpoint"><span class="pub-method mono">POST</span> <code>/v1beta/decisions</code></p>
          <p>
            A compatible request shape: <code>model</code>, <code>input</code> and <code>questions</code>. The
            input may be a string or an array of content blocks. Also accepted:
            <code>POST /v1beta/models/{model}:decisions</code> and <code>POST /v1/decisions</code>.
          </p>

          <h3 class="pub-doc-h3">Request</h3>
          <CodeBlock :code="geminiRequest" label="json" max-height="420px" />
          <CodeBlock :code="geminiCurl" label="curl" />

          <h3 class="pub-doc-h3">Multimodal input</h3>
          <CodeBlock :code="geminiMultimodal" label="json" max-height="360px" />
          <p class="pub-doc-note">
            Content blocks may reference images, audio, video, documents or PDFs. Text blocks are concatenated in
            order; media blocks contribute their type, MIME type and name to the decision context.
          </p>

          <h3 class="pub-doc-h3">Response</h3>
          <CodeBlock :code="geminiResponse" label="200 · application/json" />
        </section>

        <section id="model-listing" class="pub-doc-section">
          <h2 class="pub-doc-h2">Model listing</h2>
          <p>Both protocols expose a model list, authenticated with the same key.</p>
          <div class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Endpoint</th>
                  <th scope="col">Response</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>GET /v1/models</code></td>
                  <td><code>{ object: "list", data: [...] }</code></td>
                </tr>
                <tr>
                  <td><code>GET /v1beta/models</code></td>
                  <td><code>{ models: [{ name: "models/…", displayName, … }] }</code></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="questions" class="pub-doc-section">
          <h2 class="pub-doc-h2">Question types</h2>
          <p>
            Questions are a JSON object keyed by id. Every id must be unique within the request, and every
            question needs <code>type</code> and <code>instructions</code>.
          </p>

          <h3 class="pub-doc-h3">noul — probability of true</h3>
          <CodeBlock :code="noulShape" label="json" />
          <p class="pub-doc-note">
            <code>criteria</code> is optional. When supplied it is an object whose keys describe the true and
            false sides. The response is <code>{ "type": "noul", "noul": 0.91 }</code>. Values are clamped to
            <code>[0.01, 0.99]</code>.
          </p>

          <h3 class="pub-doc-h3">choice — one of a closed set</h3>
          <CodeBlock :code="choiceShape" label="json" />
          <p class="pub-doc-note">
            A choice question needs at least two options. The response includes
            <code>choice</code> (always the highest-probability option), a full
            <code>probabilities</code> map and <code>confidence</code>, which equals
            <code>max(p, 1 - p)</code>.
          </p>

          <h3 class="pub-doc-h3">score — ordered levels</h3>
          <CodeBlock :code="scoreShape" label="json" />
          <p class="pub-doc-note">
            Score criteria are an ordered array from lowest to highest, with at least two levels. The response
            contains the expected level as <code>score</code>, the distribution as
            <code>probabilities</code> keyed by level index, and a <code>legend</code>.
          </p>

          <div class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col">criteria</th>
                  <th scope="col">Answer fields</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>noul</code></td>
                  <td>object, optional</td>
                  <td><code>noul</code></td>
                </tr>
                <tr>
                  <td><code>choice</code></td>
                  <td>object, 2+ options</td>
                  <td><code>choice</code>, <code>probabilities</code>, <code>confidence</code></td>
                </tr>
                <tr>
                  <td><code>score</code></td>
                  <td>array, 2+ levels</td>
                  <td><code>score</code>, <code>probabilities</code>, <code>confidence</code>, <code>legend</code></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="timeout" class="pub-doc-section">
          <h2 class="pub-doc-h2">Timeouts</h2>
          <p>
            Every request is bounded by a response window. The deployment default is set per server. To shorten
            it for one request, send a timeout header; the value is milliseconds.
          </p>

          <div class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Header</th>
                  <th scope="col">Range</th>
                  <th scope="col">Effect</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>X-Decision-Timeout-Ms</code></td>
                  <td>1000 – 900000</td>
                  <td>Shortens the window for this request.</td>
                </tr>
                <tr>
                  <td><code>X-Request-Timeout-Ms</code></td>
                  <td>1000 – 900000</td>
                  <td>Alias for the same behavior.</td>
                </tr>
                <tr>
                  <td><code>X-Timeout-Ms</code></td>
                  <td>1000 – 900000</td>
                  <td>Alias, for clients that strip custom prefixes.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="pub-doc-note">
            The timeout can only shorten the deployment window, never extend it. If the window elapses the API
            returns <code>504</code> with <code>request_timeout</code> (Gemini:
            <code>DEADLINE_EXCEEDED</code>).
          </p>
        </section>

        <section id="errors" class="pub-doc-section">
          <h2 class="pub-doc-h2">Errors</h2>
          <p>
            Errors use protocol-specific envelopes. System One returns a flat
            <code>error</code> object with a string <code>code</code>; Gemini Decisions returns a numeric
            <code>code</code> plus a string <code>status</code>.
          </p>

          <div class="pub-doc-split">
            <div class="pub-doc-panel">
              <p class="pub-doc-panel-title mono">System One</p>
              <CodeBlock :code="errorSystemone" label="401" />
            </div>
            <div class="pub-doc-panel">
              <p class="pub-doc-panel-title mono">Gemini Decisions</p>
              <CodeBlock :code="errorGemini" label="401" />
            </div>
          </div>

          <div class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">System One code</th>
                  <th scope="col">Gemini status</th>
                  <th scope="col">Meaning</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>400</code></td>
                  <td><code>invalid_request</code></td>
                  <td><code>INVALID_ARGUMENT</code></td>
                  <td>Malformed body, question or criteria.</td>
                </tr>
                <tr>
                  <td><code>401</code></td>
                  <td><code>invalid_api_key</code></td>
                  <td><code>invalid_api_key</code></td>
                  <td>Missing, malformed or revoked API key.</td>
                </tr>
                <tr>
                  <td><code>403</code></td>
                  <td><code>account_disabled</code></td>
                  <td><code>account_disabled</code></td>
                  <td>The account is disabled.</td>
                </tr>
                <tr>
                  <td><code>404</code></td>
                  <td><code>model_not_found</code></td>
                  <td><code>NOT_FOUND</code></td>
                  <td>The model is not enabled on this deployment.</td>
                </tr>
                <tr>
                  <td><code>413</code></td>
                  <td><code>request_too_large</code></td>
                  <td><code>request_too_large</code></td>
                  <td>Body exceeds 8 MB.</td>
                </tr>
                <tr>
                  <td><code>429</code></td>
                  <td><code>rate_limit_exceeded</code></td>
                  <td><code>RESOURCE_EXHAUSTED</code></td>
                  <td>Rate limit or too many pending requests.</td>
                </tr>
                <tr>
                  <td><code>504</code></td>
                  <td><code>request_timeout</code></td>
                  <td><code>DEADLINE_EXCEEDED</code></td>
                  <td>The response window elapsed.</td>
                </tr>
                <tr>
                  <td><code>503</code></td>
                  <td><code>request_cancelled</code></td>
                  <td><code>UNAVAILABLE</code></td>
                  <td>The request was cancelled.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="models" class="pub-doc-section">
          <h2 class="pub-doc-h2">Models</h2>
          <p>Models currently served by this deployment:</p>

          <div v-if="models.length" class="pub-doc-table-wrap">
            <table class="table pub-doc-table">
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col">ID</th>
                  <th scope="col">Protocols</th>
                  <th scope="col">Context</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="model in models" :key="model.name">
                  <td>{{ model.display_name }}</td>
                  <td><code>{{ model.name }}</code></td>
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
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else-if="modelsError" class="pub-doc-note">{{ modelsError }}</p>
          <p v-else class="pub-doc-note">The model catalog is loading. The <RouterLink to="/models">models page</RouterLink> has the full list.</p>
        </section>

        <section id="limits" class="pub-doc-section">
          <h2 class="pub-doc-h2">Limits</h2>
          <ul class="pub-doc-list">
            <li>Request body: up to <strong>8 MB</strong>.</li>
            <li>Questions per request: up to <strong>1,000</strong>.</li>
            <li>Options per choice question and levels per score question: up to <strong>255</strong>.</li>
            <li>Instructions: up to <strong>200,000</strong> characters per question.</li>
            <li>Question ids: 1–128 printable characters, unique within a request.</li>
            <li>Rate limit: requests are limited per key; pending requests are limited per account.</li>
          </ul>
          <p class="pub-doc-note">
            When a limit is reached the API returns <code>429</code>. Retry after a short backoff; for pending
            requests, wait for earlier requests to complete.
          </p>
        </section>

        <section id="privacy" class="pub-doc-section">
          <h2 class="pub-doc-h2">Privacy</h2>
          <p>
            This is a private deployment. Request metadata — model, protocol, outcome, timing — is retained for
            usage accounting and operational debugging. Request content is retained according to the
            deployment's retention policy.
          </p>
          <p class="pub-doc-note">
            API keys are stored as hashes and are visible only once. You can revoke any key from the console at
            any time.
          </p>
        </section>

        <section id="terms" class="pub-doc-section">
          <h2 class="pub-doc-h2">Terms</h2>
          <p>
            Access is provided to registered accounts of this deployment. Use the API only for lawful purposes
            and within your account's limits. Do not attempt to bypass authentication, rate limits or usage
            accounting.
          </p>
          <p class="pub-doc-note">
            The service is provided as-is for evaluation and internal use. Availability and model catalog are
            controlled by the deployment owner.
          </p>
        </section>

        <section id="security" class="pub-doc-section">
          <h2 class="pub-doc-h2">Security</h2>
          <ul class="pub-doc-list">
            <li>API keys are stored as hashes; the secret is shown once at creation.</li>
            <li>Keys can be revoked immediately from the console.</li>
            <li>Send keys in headers, never in query strings or source control.</li>
            <li>All console sessions are HttpOnly cookies; passwords are hashed server-side.</li>
          </ul>
          <p class="pub-doc-note">
            To report a vulnerability, email
            <a :href="`mailto:${site?.support_email || 'support@noema.dev'}`" class="pub-doc-mail">
              {{ site?.support_email || 'support@noema.dev' }}
            </a>
            with steps to reproduce. Include request ids where relevant.
          </p>
        </section>

        <div class="pub-docs-foot">
          <p>Still deciding how to shape a question?</p>
          <div class="pub-docs-foot-actions">
            <RouterLink to="/console/playground" class="btn btn-primary btn-sm">
              Open the playground
              <ArrowUpRight :size="14" />
            </RouterLink>
            <RouterLink to="/models" class="btn btn-sm">Browse models</RouterLink>
          </div>
        </div>
      </article>
    </div>
  </main>
</template>
