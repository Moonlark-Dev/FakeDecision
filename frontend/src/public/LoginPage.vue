<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowRight, Loader2, LockKeyhole } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import { useSession } from '@/lib/session'
import { toast } from '@/lib/toast'
import { reportError, safeNextPath } from '@/public/support'

const route = useRoute()
const router = useRouter()
const session = useSession()

const site = computed(() => session.state.site)
const nextPath = computed(() => safeNextPath(route.query.next))
const canRegister = computed(() => Boolean(site.value?.registration_enabled))

const form = reactive({ email: '', password: '' })
const fieldErrors = reactive({ email: '', password: '' })
const formError = ref('')
const submitting = ref(false)
const emailInput = ref<HTMLInputElement | null>(null)

const registerLink = computed(() =>
  route.query.next ? { name: 'register', query: { next: nextPath.value } } : { name: 'register' },
)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(): boolean {
  fieldErrors.email = ''
  fieldErrors.password = ''
  formError.value = ''
  let valid = true
  if (!form.email.trim()) {
    fieldErrors.email = 'Enter your email address.'
    valid = false
  } else if (!EMAIL_RE.test(form.email.trim())) {
    fieldErrors.email = 'Enter a valid email address.'
    valid = false
  }
  if (!form.password) {
    fieldErrors.password = 'Enter your password.'
    valid = false
  }
  return valid
}

async function submit() {
  if (submitting.value) return
  if (!validate()) return
  submitting.value = true
  try {
    await session.login(form.email.trim().toLowerCase(), form.password)
    toast('Signed in', 'success')
    await router.replace(nextPath.value)
  } catch (error) {
    formError.value = reportError(error, 'Could not sign in. Try again.')
  } finally {
    submitting.value = false
  }
}

onMounted(() => emailInput.value?.focus())
</script>

<template>
  <main class="pub-auth">
    <div class="container pub-auth-grid">
      <aside class="pub-auth-aside">
        <p class="eyebrow">Console access</p>
        <h1 class="pub-auth-title">
          Decisions keep<br />
          their shape.
        </h1>
        <p class="pub-auth-lede">
          Sign in to manage API keys, inspect usage and run typed decisions in the playground.
        </p>

        <div class="pub-auth-sample">
          <div class="pub-auth-sample-head">
            <span class="mono">noul</span>
            <span class="mono">0.91</span>
          </div>
          <div class="pub-meter"><span class="pub-meter-fill" style="width: 91%" /></div>
          <div class="pub-auth-sample-head">
            <span class="mono">choice · refund</span>
            <span class="mono">0.88</span>
          </div>
          <div class="pub-meter"><span class="pub-meter-fill pub-meter-fill-lime" style="width: 88%" /></div>
          <p class="pub-auth-sample-foot mono">P(true) · argmax · expected level</p>
        </div>

        <p class="pub-auth-aside-foot">
          New to the API? <RouterLink to="/docs">Read the documentation</RouterLink>
        </p>
      </aside>

      <section class="pub-auth-card">
        <div class="pub-auth-card-head">
          <BrandLogo :name="site?.site_name || 'Noema'" :size="26" />
          <span class="badge">Console</span>
        </div>

        <h2 class="pub-auth-heading">Welcome back</h2>
        <p class="pub-auth-sub">Sign in to continue to your workspace.</p>

        <form class="pub-auth-form" novalidate @submit.prevent="submit">
          <div class="pub-field">
            <label class="label" for="login-email">Email</label>
            <input
              id="login-email"
              ref="emailInput"
              v-model="form.email"
              class="input"
              type="email"
              name="email"
              autocomplete="email"
              placeholder="you@company.com"
              :aria-invalid="Boolean(fieldErrors.email)"
              :disabled="submitting"
            />
            <p v-if="fieldErrors.email" class="field-error" role="alert">{{ fieldErrors.email }}</p>
          </div>

          <div class="pub-field">
            <label class="label" for="login-password">Password</label>
            <input
              id="login-password"
              v-model="form.password"
              class="input"
              type="password"
              name="password"
              autocomplete="current-password"
              placeholder="••••••••••"
              :aria-invalid="Boolean(fieldErrors.password)"
              :disabled="submitting"
            />
            <p v-if="fieldErrors.password" class="field-error" role="alert">{{ fieldErrors.password }}</p>
          </div>

          <p v-if="formError" class="pub-form-alert" role="alert">
            <LockKeyhole :size="15" />
            <span>{{ formError }}</span>
          </p>

          <button class="btn btn-primary pub-auth-submit" type="submit" :disabled="submitting">
            <Loader2 v-if="submitting" :size="16" class="pub-spin" />
            <span>{{ submitting ? 'Signing in…' : 'Sign in' }}</span>
            <ArrowRight v-if="!submitting" :size="16" />
          </button>
        </form>

        <div class="pub-auth-links">
          <template v-if="canRegister">
            <p>New here? <RouterLink :to="registerLink">Create an account</RouterLink></p>
          </template>
          <p v-else class="muted">Registration is closed on this deployment. Contact the deployment owner for access.</p>
          <p class="pub-auth-fine">
            Sessions use an HttpOnly cookie. Everything else is API keys — no passwords in code.
          </p>
        </div>
      </section>
    </div>
  </main>
</template>
