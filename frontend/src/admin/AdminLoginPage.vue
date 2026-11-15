<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Eye, EyeOff, Loader2, Lock, Moon, ShieldCheck, Sun } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import { useSession } from '@/lib/session'
import { useTheme } from '@/lib/theme'
import { errorMessage } from './utils'
import '@/styles/admin.css'

const route = useRoute()
const router = useRouter()
const session = useSession()
const theme = useTheme()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const error = ref('')

const isDark = computed(() => theme.theme.value === 'dark')
const brandName = computed(() => session.state.site?.site_name || 'Noema')
const version = computed(() => session.state.site?.version || '')

const adminOnlyPrefixes = ['/admin/users', '/admin/operators', '/admin/models', '/admin/settings', '/admin/audit']

function redirectTarget(): string {
  const raw = route.query.next
  const next = typeof raw === 'string' ? raw : Array.isArray(raw) && typeof raw[0] === 'string' ? raw[0] : ''
  if (!next.startsWith('/admin') || next.startsWith('/admin/login')) return '/admin'
  return next
}

async function submit() {
  if (submitting.value) return
  error.value = ''
  if (!email.value.trim() || !password.value) {
    error.value = 'Enter your operator email and password.'
    return
  }
  submitting.value = true
  try {
    const admin = await session.adminLogin(email.value.trim(), password.value)
    let next = redirectTarget()
    if (admin.role !== 'admin' && adminOnlyPrefixes.some((prefix) => next.startsWith(prefix))) {
      next = '/admin'
    }
    await router.replace(next)
  } catch (err) {
    error.value = errorMessage(err, 'Sign in failed. Check your credentials and try again.')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="adm-login-page">
    <header class="adm-login-top">
      <span class="adm-login-top-note"><Lock :size="12" /> Internal operations console · private deployment</span>
      <button
        type="button"
        class="btn btn-ghost btn-icon btn-sm"
        :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
        :title="isDark ? 'Light theme' : 'Dark theme'"
        @click="theme.toggle()"
      >
        <Sun v-if="isDark" :size="15" />
        <Moon v-else :size="15" />
      </button>
    </header>

    <main class="adm-login-main">
      <section class="adm-login-card" aria-labelledby="adm-login-title">
        <div class="adm-login-brand">
          <BrandLogo :name="brandName" :size="26" />
          <span class="adm-env-badge">Internal</span>
        </div>

        <p class="eyebrow adm-login-eyebrow">Operations</p>
        <h1 id="adm-login-title" class="adm-login-title">Operator sign in</h1>
        <p class="adm-login-sub">
          Provisioned backoffice accounts only. Operators answer live decision requests; administrators manage the
          deployment.
        </p>

        <form class="adm-login-form" novalidate @submit.prevent="submit">
          <div class="field">
            <label class="label" for="adm-login-email">Email</label>
            <input
              id="adm-login-email"
              v-model="email"
              class="input"
              type="email"
              name="email"
              autocomplete="username"
              inputmode="email"
              placeholder="operator@deployment.internal"
              :disabled="submitting"
              required
            />
          </div>

          <div class="field">
            <label class="label" for="adm-login-password">Password</label>
            <div class="adm-password-wrap">
              <input
                id="adm-login-password"
                v-model="password"
                class="input"
                :type="showPassword ? 'text' : 'password'"
                name="password"
                autocomplete="current-password"
                placeholder="Account password"
                :disabled="submitting"
                required
              />
              <button
                type="button"
                class="adm-password-toggle"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
                :aria-pressed="showPassword"
                tabindex="0"
                @click="showPassword = !showPassword"
              >
                <EyeOff v-if="showPassword" :size="15" />
                <Eye v-else :size="15" />
              </button>
            </div>
          </div>

          <p v-if="error" class="adm-login-error" role="alert" aria-live="assertive">{{ error }}</p>

          <button type="submit" class="btn btn-primary adm-login-submit" :disabled="submitting">
            <Loader2 v-if="submitting" :size="15" class="adm-spin" />
            <span>{{ submitting ? 'Signing in…' : 'Sign in' }}</span>
            <ArrowRight v-if="!submitting" :size="15" />
          </button>
        </form>

        <div class="adm-login-legal">
          <p><ShieldCheck :size="13" /> Authorized operators only. Every action is recorded in the audit log.</p>
          <p>
            This console is part of a private deployment. It is intentionally not linked from the public product, and
            there are no billing, pricing or monetization surfaces.
          </p>
        </div>

        <footer class="adm-login-foot">
          <span class="mono">{{ brandName }}{{ version ? ` · v${version}` : '' }}</span>
          <span class="muted">Session cookies required</span>
        </footer>
      </section>
    </main>
  </div>
</template>
