<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowRight, Check, Loader2 } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import { useSession } from '@/lib/session'
import { toast } from '@/lib/toast'
import { reportError, safeNextPath } from '@/public/support'

const route = useRoute()
const router = useRouter()
const session = useSession()

const site = computed(() => session.state.site)
const canRegister = computed(() => Boolean(site.value?.registration_enabled))
const nextPath = computed(() => safeNextPath(route.query.next))

const form = reactive({ name: '', email: '', password: '', confirm: '' })
const fieldErrors = reactive({ name: '', email: '', password: '', confirm: '' })
const formError = ref('')
const submitting = ref(false)
const nameInput = ref<HTMLInputElement | null>(null)

const loginLink = computed(() =>
  route.query.next ? { name: 'login', query: { next: nextPath.value } } : { name: 'login' },
)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_MIN = 10

const passwordHint = computed(() => {
  if (!form.password) return `At least ${PASSWORD_MIN} characters.`
  if (form.password.length < PASSWORD_MIN) {
    return `${PASSWORD_MIN - form.password.length} more character${PASSWORD_MIN - form.password.length === 1 ? '' : 's'} needed.`
  }
  return 'Long enough.'
})

function validate(): boolean {
  fieldErrors.name = ''
  fieldErrors.email = ''
  fieldErrors.password = ''
  fieldErrors.confirm = ''
  formError.value = ''
  let valid = true
  if (!form.name.trim()) {
    fieldErrors.name = 'Enter your name.'
    valid = false
  }
  if (!form.email.trim()) {
    fieldErrors.email = 'Enter your email address.'
    valid = false
  } else if (!EMAIL_RE.test(form.email.trim())) {
    fieldErrors.email = 'Enter a valid email address.'
    valid = false
  }
  if (!form.password) {
    fieldErrors.password = 'Choose a password.'
    valid = false
  } else if (form.password.length < PASSWORD_MIN) {
    fieldErrors.password = `Password must be at least ${PASSWORD_MIN} characters.`
    valid = false
  }
  if (form.confirm !== form.password) {
    fieldErrors.confirm = 'Passwords do not match.'
    valid = false
  }
  return valid
}

async function submit() {
  if (submitting.value || !canRegister.value) return
  if (!validate()) return
  submitting.value = true
  try {
    await session.register(form.email.trim().toLowerCase(), form.name.trim(), form.password)
    toast('Account created', 'success')
    await router.replace(nextPath.value)
  } catch (error) {
    formError.value = reportError(error, 'Could not create the account. Try again.')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (canRegister.value) nameInput.value?.focus()
})
</script>

<template>
  <main class="pub-auth">
    <div class="container pub-auth-grid">
      <aside class="pub-auth-aside">
        <p class="eyebrow">Get started</p>
        <h1 class="pub-auth-title">
          Ask for<br />
          answers, not<br />
          paragraphs.
        </h1>
        <p class="pub-auth-lede">
          Create an account to issue API keys, try both protocols and track usage. The playground runs against
          the same endpoints as production.
        </p>

        <ul class="pub-auth-points">
          <li><Check :size="15" /> Two protocols, one answer format</li>
          <li><Check :size="15" /> Keys shown once, stored as hashes</li>
          <li><Check :size="15" /> Session playground, no key required</li>
        </ul>

        <p class="pub-auth-aside-foot">
          Already have an account? <RouterLink to="/login">Sign in</RouterLink>
        </p>
      </aside>

      <section class="pub-auth-card">
        <div class="pub-auth-card-head">
          <BrandLogo :name="site?.site_name || 'Noema'" :size="26" />
          <span class="badge">Console</span>
        </div>

        <template v-if="canRegister">
          <h2 class="pub-auth-heading">Create your account</h2>
          <p class="pub-auth-sub">One endpoint, two protocols, typed answers.</p>

          <form class="pub-auth-form" novalidate @submit.prevent="submit">
            <div class="pub-field">
              <label class="label" for="register-name">Name</label>
              <input
                id="register-name"
                ref="nameInput"
                v-model="form.name"
                class="input"
                type="text"
                name="name"
                autocomplete="name"
                placeholder="Ada Lovelace"
                :aria-invalid="Boolean(fieldErrors.name)"
                :disabled="submitting"
              />
              <p v-if="fieldErrors.name" class="field-error" role="alert">{{ fieldErrors.name }}</p>
            </div>

            <div class="pub-field">
              <label class="label" for="register-email">Email</label>
              <input
                id="register-email"
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
              <label class="label" for="register-password">Password</label>
              <input
                id="register-password"
                v-model="form.password"
                class="input"
                type="password"
                name="new-password"
                autocomplete="new-password"
                placeholder="At least 10 characters"
                :aria-invalid="Boolean(fieldErrors.password)"
                :disabled="submitting"
              />
              <p class="field-hint" :class="{ 'pub-hint-ok': form.password.length >= PASSWORD_MIN }">{{ passwordHint }}</p>
              <p v-if="fieldErrors.password" class="field-error" role="alert">{{ fieldErrors.password }}</p>
            </div>

            <div class="pub-field">
              <label class="label" for="register-confirm">Confirm password</label>
              <input
                id="register-confirm"
                v-model="form.confirm"
                class="input"
                type="password"
                name="confirm-password"
                autocomplete="new-password"
                placeholder="Repeat your password"
                :aria-invalid="Boolean(fieldErrors.confirm)"
                :disabled="submitting"
              />
              <p v-if="fieldErrors.confirm" class="field-error" role="alert">{{ fieldErrors.confirm }}</p>
            </div>

            <p v-if="formError" class="pub-form-alert" role="alert">
              <span>{{ formError }}</span>
            </p>

            <button class="btn btn-primary pub-auth-submit" type="submit" :disabled="submitting">
              <Loader2 v-if="submitting" :size="16" class="pub-spin" />
              <span>{{ submitting ? 'Creating account…' : 'Create account' }}</span>
              <ArrowRight v-if="!submitting" :size="16" />
            </button>

            <p class="pub-auth-terms">
              By creating an account you agree to the
              <RouterLink :to="{ path: '/docs', hash: '#terms' }">terms</RouterLink> and
              <RouterLink :to="{ path: '/docs', hash: '#privacy' }">privacy notice</RouterLink>.
            </p>
          </form>

          <div class="pub-auth-links">
            <p>Already registered? <RouterLink :to="loginLink">Sign in</RouterLink></p>
          </div>
        </template>

        <template v-else>
          <h2 class="pub-auth-heading">Registration is closed</h2>
          <p class="pub-auth-sub">
            This deployment is not accepting new accounts right now. If you already have one, sign in to
            continue.
          </p>
          <div class="pub-auth-form">
            <RouterLink :to="loginLink" class="btn btn-primary pub-auth-submit">
              Sign in
              <ArrowRight :size="16" />
            </RouterLink>
            <p class="pub-auth-fine">
              Need access? Email
              <a :href="`mailto:${site?.support_email || 'support@noema.dev'}`" class="pub-text-link">
                {{ site?.support_email || 'support@noema.dev' }}
              </a>
              and include your team name.
            </p>
          </div>
        </template>
      </section>
    </div>
  </main>
</template>
