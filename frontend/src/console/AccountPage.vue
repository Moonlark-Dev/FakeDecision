<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { KeyRound, LifeBuoy, Loader2, Mail, ShieldCheck } from 'lucide-vue-next'
import { patch, post } from '@/lib/api'
import { formatDate, timeAgo } from '@/lib/format'
import { useSession } from '@/lib/session'
import { toast } from '@/lib/toast'
import { reportError } from '@/public/support'
import type { User } from '@/types/api'

const router = useRouter()
const session = useSession()
const user = computed(() => session.state.user)
const site = computed(() => session.state.site)
const supportEmail = computed(() => site.value?.support_email || 'support@noema.dev')

const name = ref('')
const profileSaving = ref(false)
const profileError = ref('')
const profileNotice = ref('')

watch(
  () => session.state.user,
  (current) => {
    name.value = current?.name ?? ''
  },
  { immediate: true },
)

const profileChanged = computed(() => name.value.trim() !== (user.value?.name ?? '').trim())

async function saveProfile() {
  const value = name.value.trim()
  profileError.value = ''
  profileNotice.value = ''
  if (!value) {
    profileError.value = 'Enter a name.'
    return
  }
  if (!profileChanged.value) return
  profileSaving.value = true
  try {
    const result = await patch<{ user: User }>('/api/account', { name: value })
    session.state.user = result.user
    name.value = result.user.name
    profileNotice.value = 'Profile updated.'
    toast('Profile updated', 'success')
  } catch (error) {
    profileError.value = reportError(error, 'Could not update your profile.')
  } finally {
    profileSaving.value = false
  }
}

const password = reactive({ current: '', next: '', confirm: '' })
const passwordErrors = reactive({ current: '', next: '', confirm: '', form: '' })
const passwordSaving = ref(false)

function resetPasswordErrors() {
  passwordErrors.current = ''
  passwordErrors.next = ''
  passwordErrors.confirm = ''
  passwordErrors.form = ''
}

async function changePassword() {
  if (passwordSaving.value) return
  resetPasswordErrors()
  let valid = true
  if (!password.current) {
    passwordErrors.current = 'Enter your current password.'
    valid = false
  }
  if (!password.next) {
    passwordErrors.next = 'Choose a new password.'
    valid = false
  } else if (password.next.length < 10) {
    passwordErrors.next = 'Password must be at least 10 characters.'
    valid = false
  }
  if (password.confirm !== password.next) {
    passwordErrors.confirm = 'Passwords do not match.'
    valid = false
  }
  if (!valid) return

  passwordSaving.value = true
  try {
    await post<{ ok: boolean }>('/api/account/password', {
      current_password: password.current,
      new_password: password.next,
    })
    password.current = ''
    password.next = ''
    password.confirm = ''
    toast('Password changed', 'success', { detail: 'All sessions were signed out.' })
    try {
      await session.logout()
    } catch {
      // The server already invalidated the session; continue to sign-in.
    }
    await router.replace({ name: 'login', query: { next: '/console/account' } })
  } catch (error) {
    passwordErrors.form = reportError(error, 'Could not change the password.')
  } finally {
    passwordSaving.value = false
  }
}
</script>

<template>
  <div class="console-page">
    <div class="console-page-head">
      <div>
        <p class="eyebrow">Account</p>
        <h1 class="console-h1">Account</h1>
        <p class="console-sub">Profile, password and workspace details.</p>
      </div>
      <div class="console-page-actions">
        <RouterLink to="/console/keys" class="btn btn-sm">
          <KeyRound :size="14" />
          API keys
        </RouterLink>
      </div>
    </div>

    <div class="console-account-grid">
      <div class="console-account-main">
        <section class="panel console-panel">
          <header class="panel-header">
            <div>
              <h2 class="panel-title">Profile</h2>
              <p class="console-panel-sub">Used for console greetings and support.</p>
            </div>
          </header>
          <div class="panel-body">
            <form class="console-form" novalidate @submit.prevent="saveProfile">
              <div class="pub-field">
                <label class="label" for="account-name">Name</label>
                <input
                  id="account-name"
                  v-model="name"
                  class="input"
                  type="text"
                  name="name"
                  autocomplete="name"
                  maxlength="80"
                  :disabled="profileSaving"
                />
                <p v-if="profileError" class="field-error" role="alert">{{ profileError }}</p>
                <p v-else-if="profileNotice" class="field-hint console-field-ok">{{ profileNotice }}</p>
              </div>

              <div class="pub-field">
                <label class="label" for="account-email">Email</label>
                <input
                  id="account-email"
                  class="input"
                  type="email"
                  :value="user?.email || ''"
                  readonly
                  aria-describedby="account-email-hint"
                />
                <p id="account-email-hint" class="field-hint">Email changes are handled by support.</p>
              </div>

              <div class="console-form-actions">
                <button class="btn btn-primary" type="submit" :disabled="profileSaving || !profileChanged">
                  <Loader2 v-if="profileSaving" :size="15" class="pub-spin" />
                  {{ profileSaving ? 'Saving…' : 'Save profile' }}
                </button>
                <button
                  v-if="profileChanged"
                  type="button"
                  class="btn btn-ghost"
                  :disabled="profileSaving"
                  @click="name = user?.name || ''"
                >
                  Reset
                </button>
              </div>
            </form>
          </div>
        </section>

        <section class="panel console-panel">
          <header class="panel-header">
            <div>
              <h2 class="panel-title">Password</h2>
              <p class="console-panel-sub">Changing your password signs out every active session.</p>
            </div>
          </header>
          <div class="panel-body">
            <div class="console-warning">
              <ShieldCheck :size="16" />
              <p>
                After saving, every session — including this one — is signed out. You will be returned to the
                sign-in page with a fresh password.
              </p>
            </div>

            <form class="console-form" novalidate @submit.prevent="changePassword">
              <div class="pub-field">
                <label class="label" for="account-current">Current password</label>
                <input
                  id="account-current"
                  v-model="password.current"
                  class="input"
                  type="password"
                  autocomplete="current-password"
                  :disabled="passwordSaving"
                />
                <p v-if="passwordErrors.current" class="field-error" role="alert">{{ passwordErrors.current }}</p>
              </div>

              <div class="form-row">
                <div class="pub-field">
                  <label class="label" for="account-next">New password</label>
                  <input
                    id="account-next"
                    v-model="password.next"
                    class="input"
                    type="password"
                    autocomplete="new-password"
                    placeholder="At least 10 characters"
                    :disabled="passwordSaving"
                  />
                  <p v-if="passwordErrors.next" class="field-error" role="alert">{{ passwordErrors.next }}</p>
                </div>
                <div class="pub-field">
                  <label class="label" for="account-confirm">Confirm new password</label>
                  <input
                    id="account-confirm"
                    v-model="password.confirm"
                    class="input"
                    type="password"
                    autocomplete="new-password"
                    placeholder="Repeat new password"
                    :disabled="passwordSaving"
                  />
                  <p v-if="passwordErrors.confirm" class="field-error" role="alert">{{ passwordErrors.confirm }}</p>
                </div>
              </div>

              <p v-if="passwordErrors.form" class="pub-form-alert" role="alert">
                <span>{{ passwordErrors.form }}</span>
              </p>

              <div class="console-form-actions">
                <button class="btn btn-primary" type="submit" :disabled="passwordSaving">
                  <Loader2 v-if="passwordSaving" :size="15" class="pub-spin" />
                  {{ passwordSaving ? 'Updating…' : 'Update password' }}
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>

      <aside class="console-account-aside">
        <section class="panel console-panel">
          <header class="panel-header">
            <h2 class="panel-title">Account</h2>
          </header>
          <dl class="console-meta-list">
            <div class="console-meta-row">
              <dt>Email</dt>
              <dd class="mono">{{ user?.email }}</dd>
            </div>
            <div class="console-meta-row">
              <dt>Member since</dt>
              <dd class="mono">{{ user ? formatDate(user.created_at, false) : '—' }}</dd>
            </div>
            <div class="console-meta-row">
              <dt>Last sign-in</dt>
              <dd class="mono">{{ user ? timeAgo(user.last_login_at) : '—' }}</dd>
            </div>
            <div class="console-meta-row">
              <dt>Account ID</dt>
              <dd class="mono console-meta-id">{{ user?.id }}</dd>
            </div>
          </dl>
        </section>

        <section class="panel console-panel">
          <header class="panel-header">
            <h2 class="panel-title">Support</h2>
          </header>
          <div class="panel-body console-support">
            <div class="console-support-row">
              <LifeBuoy :size="16" />
              <div>
                <p class="console-support-title">Need help?</p>
                <p class="field-hint">Include the request id from any failed call.</p>
              </div>
            </div>
            <a :href="`mailto:${supportEmail}`" class="btn btn-sm console-support-link">
              <Mail :size="14" />
              <span class="console-support-email mono">{{ supportEmail }}</span>
            </a>
            <RouterLink :to="{ path: '/docs', hash: '#quickstart' }" class="pub-text-link">
              Quickstart and examples
            </RouterLink>
          </div>
        </section>

        <section class="console-privacy-note">
          <ShieldCheck :size="16" />
          <div>
            <p class="console-privacy-title">Private deployment</p>
            <p class="field-hint">
              This workspace belongs to a private deployment of {{ site?.site_name || 'Noema' }}. Access is
              limited to registered accounts. Keys are stored hashed, every key can be revoked immediately, and
              request metadata is retained only for usage accounting and debugging.
            </p>
            <RouterLink :to="{ path: '/docs', hash: '#privacy' }" class="pub-text-link">
              Privacy notice
            </RouterLink>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>
