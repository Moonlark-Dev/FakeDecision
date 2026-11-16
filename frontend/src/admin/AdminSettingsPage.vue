<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Loader2, ImagePlus, RefreshCw, RotateCcw, Save, Terminal, Trash2 } from 'lucide-vue-next'
import type { SettingsPayload } from '@/types/api'
import { del, get, post, put } from '@/lib/api'
import { toast } from '@/lib/toast'
import { useSession } from '@/lib/session'
import BrandLogo from '@/components/BrandLogo.vue'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import { errorMessage } from './utils'

type SettingValue = string | number | boolean

const numericKeys = [
  'request_timeout_seconds',
  'timeout_fill_lead_seconds',
  'max_pending_per_user',
  'rate_limit_per_minute',
  'history_retention_days',
]

const form = ref<Record<string, SettingValue>>({})
const original = ref<Record<string, SettingValue>>({})
const numberText = reactive<Record<string, string>>({})
const limits = ref<Record<string, [number, number]>>({})
const version = ref('')
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saveError = ref('')

const session = useSession()
const route = useRoute()
const logoUrl = ref('')
const logoBusy = ref(false)
const logoError = ref('')
const logoInput = ref<HTMLInputElement | null>(null)
const LOGO_MAX_BYTES = 512 * 1024
const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml']

function str(key: string): string {
  const value = form.value[key]
  return typeof value === 'string' ? value : ''
}

function bool(key: string): boolean {
  return form.value[key] === true
}

function numberTextValue(key: string): string {
  return numberText[key] ?? ''
}

function setString(key: string, value: string) {
  form.value = { ...form.value, [key]: value }
}

function setBool(key: string, value: boolean) {
  form.value = { ...form.value, [key]: value }
}

function setNumberText(key: string, raw: string) {
  numberText[key] = raw
  const numeric = Number(raw)
  if (raw.trim() !== '' && Number.isFinite(numeric)) {
    form.value = { ...form.value, [key]: Math.trunc(numeric) }
  }
}

function limitsFor(key: string): [number, number] | undefined {
  return limits.value[key]
}

function minFor(key: string): number | undefined {
  return limitsFor(key)?.[0]
}

function maxFor(key: string): number | undefined {
  return limitsFor(key)?.[1]
}

const dirtyKeys = computed(() => {
  const keys = new Set<string>()
  for (const key of Object.keys(form.value)) {
    if (JSON.stringify(form.value[key]) !== JSON.stringify(original.value[key])) keys.add(key)
  }
  for (const key of numericKeys) {
    if ((numberText[key] ?? '') !== String(original.value[key] ?? '')) keys.add(key)
  }
  return [...keys]
})

const fieldErrors = computed<Record<string, string>>(() => {
  const errors: Record<string, string> = {}
  if (!str('site_name').trim()) errors.site_name = 'Site name is required.'
  for (const key of numericKeys) {
    const raw = numberText[key] ?? ''
    const numeric = Number(raw)
    if (raw.trim() === '' || !Number.isFinite(numeric) || !Number.isInteger(numeric)) {
      errors[key] = 'Enter a whole number.'
      continue
    }
    const bounds = limitsFor(key)
    if (bounds && (numeric < bounds[0] || numeric > bounds[1])) {
      errors[key] = `Must be between ${bounds[0]} and ${bounds[1]}.`
    }
  }
  const timeout = Number(numberText.request_timeout_seconds)
  const lead = Number(numberText.timeout_fill_lead_seconds)
  if (Number.isFinite(timeout) && Number.isFinite(lead) && lead >= timeout) {
    errors.timeout_fill_lead_seconds = 'Auto-fill lead must be less than the request timeout.'
  }
  return errors
})

const hasErrors = computed(() => Object.keys(fieldErrors.value).length > 0)
const dirtyCount = computed(() => dirtyKeys.value.length)
const canSave = computed(() => dirtyCount.value > 0 && !saving.value && !hasErrors.value && !loading.value)

async function load() {
  loading.value = true
  error.value = ''
  saveError.value = ''
  try {
    const response = await get<SettingsPayload>('/api/admin/settings')
    form.value = { ...response.values }
    original.value = { ...response.values }
    limits.value = {
      history_retention_days: [1, 3650],
      ...(response.limits || {}),
    }
    version.value = response.version
    logoUrl.value = session.state.site?.logo_url || ''
    for (const key of numericKeys) numberText[key] = String(response.values[key] ?? '')
  } catch (err) {
    error.value = errorMessage(err, 'Could not load settings.')
  } finally {
    loading.value = false
  }
}

function resetChanges() {
  form.value = { ...original.value }
  for (const key of numericKeys) numberText[key] = String(original.value[key] ?? '')
  saveError.value = ''
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  saveError.value = ''
  const payload: Record<string, SettingValue> = {}
  for (const key of dirtyKeys.value) {
    if (numericKeys.includes(key)) payload[key] = Number(numberText[key])
    else payload[key] = form.value[key]
  }
  try {
    const response = await put<{ values: Record<string, SettingValue> }>('/api/admin/settings', { values: payload })
    form.value = { ...response.values }
    original.value = { ...response.values }
    for (const key of numericKeys) numberText[key] = String(response.values[key] ?? '')
    const brandKeys = [
      'site_name',
      'site_tagline',
      'site_description',
      'announcement',
      'support_email',
      'registration_enabled',
      'show_register_cta',
    ]
    if (brandKeys.some((key) => key in payload)) {
      // The header/footer/logos read the shared site state, so a brand rename
      // must update it immediately instead of waiting for the next reload.
      await session.refreshSite()
      const brand = session.state.site?.site_name || 'Noema'
      const pageTitle = route.meta.title as string | undefined
      document.title = pageTitle ? `${pageTitle} · ${brand}` : brand
    }
    toast('Settings saved', 'success', {
      detail: `${Object.keys(payload).length} value${Object.keys(payload).length === 1 ? '' : 's'} updated.`,
    })
  } catch (err) {
    saveError.value = errorMessage(err, 'Could not save settings.')
    toast('Settings not saved', 'error', { detail: saveError.value })
  } finally {
    saving.value = false
  }
}

function pickLogo() {
  if (!logoBusy.value && !saving.value) logoInput.value?.click()
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Could not read the selected file.'))
    reader.readAsDataURL(file)
  })
}

async function onLogoChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  logoError.value = ''
  if (!LOGO_TYPES.includes(file.type)) {
    logoError.value = 'Use a PNG, JPEG, WebP or SVG image.'
    return
  }
  if (file.size > LOGO_MAX_BYTES) {
    logoError.value = 'Logo must be 512 KB or smaller.'
    return
  }
  logoBusy.value = true
  try {
    const data = await readFileAsDataUrl(file)
    const response = await post<{ logo_url: string }>('/api/admin/branding/logo', {
      filename: file.name,
      data,
    })
    logoUrl.value = response.logo_url
    await session.refreshSite()
    toast('Logo updated', 'success', { detail: 'The new logo is live on the public site and admin console.' })
  } catch (err) {
    logoError.value = errorMessage(err, 'Could not upload the logo.')
    toast('Logo not updated', 'error', { detail: logoError.value })
  } finally {
    logoBusy.value = false
  }
}

async function resetLogo() {
  if (logoBusy.value || !logoUrl.value) return
  logoBusy.value = true
  logoError.value = ''
  try {
    await del('/api/admin/branding/logo')
    logoUrl.value = ''
    await session.refreshSite()
    toast('Logo reset', 'success', { detail: 'The built-in mark is back.' })
  } catch (err) {
    logoError.value = errorMessage(err, 'Could not reset the logo.')
    toast('Logo not reset', 'error', { detail: logoError.value })
  } finally {
    logoBusy.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="adm-page">
    <header class="adm-page-head">
      <div>
        <p class="eyebrow adm-page-eyebrow">Administration</p>
        <h1 class="adm-page-title">Settings</h1>
        <p class="adm-page-sub">
          Runtime copy, registration, timing and safety controls. Changes apply without a restart.
        </p>
      </div>
      <div class="adm-page-actions">
        <span v-if="version" class="badge mono">build {{ version }}</span>
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Reload</span>
        </button>
        <button type="button" class="btn btn-sm" :disabled="!dirtyCount || saving" @click="resetChanges">
          <RotateCcw :size="14" />
          <span>Discard</span>
        </button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="!canSave" @click="save">
          <Loader2 v-if="saving" :size="14" class="adm-spin" />
          <Save v-else :size="14" />
          <span>{{ saving ? 'Saving…' : dirtyCount ? `Save ${dirtyCount} change${dirtyCount === 1 ? '' : 's'}` : 'Save' }}</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="adm-alert" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load">Retry</button>
    </div>
    <div v-if="saveError" class="adm-alert adm-alert-error" role="alert">
      <span>{{ saveError }}</span>
    </div>

    <div v-if="loading" class="adm-settings-grid" aria-hidden="true">
      <div v-for="n in 4" :key="n" class="adm-panel adm-panel-pad">
        <div class="adm-skeleton-row" />
        <div class="adm-skeleton-row" />
        <div class="adm-skeleton-row" />
      </div>
    </div>

    <form v-else class="adm-settings-grid" novalidate @submit.prevent="save">
      <section class="adm-panel" aria-labelledby="adm-settings-site">
        <header class="adm-panel-head">
          <div>
            <h2 id="adm-settings-site" class="adm-panel-title">Brand &amp; site copy</h2>
            <p class="adm-panel-sub">Brand name, logo, public copy and links.</p>
          </div>
        </header>
        <div class="adm-panel-body adm-form">
          <div class="field">
            <span class="label">Logo</span>
            <div class="adm-logo-row">
              <span class="adm-logo-preview">
                <img v-if="logoUrl" :src="logoUrl" alt="Current brand logo" />
                <BrandLogo v-else compact :size="40" />
              </span>
              <div class="adm-logo-actions">
                <div class="adm-logo-buttons">
                  <button type="button" class="btn btn-sm" :disabled="logoBusy || saving" @click="pickLogo">
                    <Loader2 v-if="logoBusy" :size="14" class="adm-spin" />
                    <ImagePlus v-else :size="14" />
                    <span>{{ logoBusy ? 'Uploading…' : logoUrl ? 'Replace logo' : 'Upload logo' }}</span>
                  </button>
                  <button v-if="logoUrl" type="button" class="btn btn-sm" :disabled="logoBusy || saving" @click="resetLogo">
                    <Trash2 :size="14" />
                    <span>Reset</span>
                  </button>
                </div>
                <p class="field-hint">PNG, JPEG, WebP or SVG, up to 512 KB. Square images work best. Also used as the browser favicon.</p>
                <p class="field-hint">Leave empty to use the built-in mark.</p>
                <p v-if="logoError" class="field-error">{{ logoError }}</p>
              </div>
              <input
                ref="logoInput"
                class="adm-logo-input"
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                @change="onLogoChosen"
              />
            </div>
          </div>
          <div class="field">
            <label class="label" for="adm-setting-site_name">Site name</label>
            <input
              id="adm-setting-site_name"
              class="input"
              type="text"
              maxlength="80"
              :value="str('site_name')"
              :disabled="saving"
              @input="setString('site_name', ($event.target as HTMLInputElement).value)"
            />
            <p v-if="fieldErrors.site_name" class="field-error">{{ fieldErrors.site_name }}</p>
          </div>
          <div class="field">
            <label class="label" for="adm-setting-site_tagline">Tagline</label>
            <input
              id="adm-setting-site_tagline"
              class="input"
              type="text"
              maxlength="200"
              :value="str('site_tagline')"
              :disabled="saving"
              @input="setString('site_tagline', ($event.target as HTMLInputElement).value)"
            />
            <p v-if="fieldErrors.site_tagline" class="field-error">{{ fieldErrors.site_tagline }}</p>
          </div>
          <div class="field">
            <label class="label" for="adm-setting-site_description">Description</label>
            <textarea
              id="adm-setting-site_description"
              class="textarea"
              rows="3"
              :value="str('site_description')"
              :disabled="saving"
              @input="setString('site_description', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
          <div class="field">
            <label class="label" for="adm-setting-announcement">Announcement</label>
            <textarea
              id="adm-setting-announcement"
              class="textarea"
              rows="2"
              placeholder="Optional banner shown on the public site."
              :value="str('announcement')"
              :disabled="saving"
              @input="setString('announcement', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
          <div class="adm-form-row">
            <div class="field">
              <label class="label" for="adm-setting-support_email">Support email</label>
              <input
                id="adm-setting-support_email"
                class="input"
                type="email"
                :value="str('support_email')"
                :disabled="saving"
                @input="setString('support_email', ($event.target as HTMLInputElement).value)"
              />
              <p class="field-hint">Separate from the brand name; used in public footers and docs.</p>
              <p v-if="fieldErrors.support_email" class="field-error">{{ fieldErrors.support_email }}</p>
            </div>
            <div class="field">
              <label class="label" for="adm-setting-public_base_url">Public base URL</label>
              <input
                id="adm-setting-public_base_url"
                class="input mono"
                type="url"
                placeholder="https://decisions.example.com"
                :value="str('public_base_url')"
                :disabled="saving"
                @input="setString('public_base_url', ($event.target as HTMLInputElement).value)"
              />
            </div>
          </div>
          <div class="field">
            <label class="label" for="adm-setting-docs_url">Docs URL</label>
            <input
              id="adm-setting-docs_url"
              class="input mono"
              type="url"
              :value="str('docs_url')"
              :disabled="saving"
              @input="setString('docs_url', ($event.target as HTMLInputElement).value)"
            />
          </div>
        </div>
      </section>

      <section class="adm-panel" aria-labelledby="adm-settings-registration">
        <header class="adm-panel-head">
          <div>
            <h2 id="adm-settings-registration" class="adm-panel-title">Registration</h2>
            <p class="adm-panel-sub">Control public account creation and CTAs.</p>
          </div>
        </header>
        <div class="adm-panel-body adm-form">
          <div class="adm-toggle-row">
            <div>
              <p class="adm-toggle-title">Public registration</p>
              <p class="adm-toggle-help">Allow new users to create accounts from the public site.</p>
            </div>
            <ToggleSwitch
              :model-value="bool('registration_enabled')"
              label="Public registration"
              :disabled="saving"
              @update:model-value="setBool('registration_enabled', $event)"
            />
          </div>
          <div class="adm-toggle-row">
            <div>
              <p class="adm-toggle-title">Show register CTA</p>
              <p class="adm-toggle-help">Render the registration call-to-action on public pages.</p>
            </div>
            <ToggleSwitch
              :model-value="bool('show_register_cta')"
              label="Show register CTA"
              :disabled="saving"
              @update:model-value="setBool('show_register_cta', $event)"
            />
          </div>
        </div>
      </section>

      <section class="adm-panel" aria-labelledby="adm-settings-timing">
        <header class="adm-panel-head">
          <div>
            <h2 id="adm-settings-timing" class="adm-panel-title">Timing &amp; auto-fill</h2>
            <p class="adm-panel-sub">Deadline and late-answer behaviour.</p>
          </div>
        </header>
        <div class="adm-panel-body adm-form">
          <div class="adm-form-row">
            <div class="field">
              <label class="label" for="adm-setting-request_timeout_seconds">Request timeout (seconds)</label>
              <input
                id="adm-setting-request_timeout_seconds"
                class="input mono"
                type="number"
                :min="minFor('request_timeout_seconds')"
                :max="maxFor('request_timeout_seconds')"
                step="1"
                :value="numberTextValue('request_timeout_seconds')"
                :disabled="saving"
                @input="setNumberText('request_timeout_seconds', ($event.target as HTMLInputElement).value)"
              />
              <p class="field-hint">Hard deadline for a human response. Per-request headers may shorten this.</p>
              <p v-if="fieldErrors.request_timeout_seconds" class="field-error">{{ fieldErrors.request_timeout_seconds }}</p>
            </div>
            <div class="field">
              <label class="label" for="adm-setting-timeout_fill_lead_seconds">Auto-fill lead (seconds)</label>
              <input
                id="adm-setting-timeout_fill_lead_seconds"
                class="input mono"
                type="number"
                :min="minFor('timeout_fill_lead_seconds')"
                :max="maxFor('timeout_fill_lead_seconds')"
                step="1"
                :value="numberTextValue('timeout_fill_lead_seconds')"
                :disabled="saving"
                @input="setNumberText('timeout_fill_lead_seconds', ($event.target as HTMLInputElement).value)"
              />
              <p class="field-hint">How long before the deadline the system fills missing answers.</p>
              <p v-if="fieldErrors.timeout_fill_lead_seconds" class="field-error">{{ fieldErrors.timeout_fill_lead_seconds }}</p>
            </div>
          </div>
          <div class="adm-toggle-row">
            <div>
              <p class="adm-toggle-title">Auto-fill missing answers</p>
              <p class="adm-toggle-help">When off, requests time out if no operator submits before the deadline.</p>
            </div>
            <ToggleSwitch
              :model-value="bool('timeout_fill_enabled')"
              label="Auto-fill missing answers"
              :disabled="saving"
              @update:model-value="setBool('timeout_fill_enabled', $event)"
            />
          </div>
        </div>
      </section>

      <section class="adm-panel" aria-labelledby="adm-settings-assignment">
        <header class="adm-panel-head">
          <div>
            <h2 id="adm-settings-assignment" class="adm-panel-title">Assignment &amp; sound</h2>
            <p class="adm-panel-sub">Operator routing and notification defaults.</p>
          </div>
        </header>
        <div class="adm-panel-body adm-form">
          <div class="adm-toggle-row">
            <div>
              <p class="adm-toggle-title">Administrators receive all requests</p>
              <p class="adm-toggle-help">When off, administrators only receive notifications for model assignments.</p>
            </div>
            <ToggleSwitch
              :model-value="bool('admin_receive_all')"
              label="Administrators receive all requests"
              :disabled="saving"
              @update:model-value="setBool('admin_receive_all', $event)"
            />
          </div>
          <div class="adm-toggle-row">
            <div>
              <p class="adm-toggle-title">Notification sound default</p>
              <p class="adm-toggle-help">Default for new consoles. Operators can override it in the top bar.</p>
            </div>
            <ToggleSwitch
              :model-value="bool('sound_default')"
              label="Notification sound default"
              :disabled="saving"
              @update:model-value="setBool('sound_default', $event)"
            />
          </div>
        </div>
      </section>

      <section class="adm-panel" aria-labelledby="adm-settings-safety">
        <header class="adm-panel-head">
          <div>
            <h2 id="adm-settings-safety" class="adm-panel-title">Safety &amp; rate</h2>
            <p class="adm-panel-sub">Concurrency, abuse and retention bounds.</p>
          </div>
        </header>
        <div class="adm-panel-body adm-form">
          <div class="adm-form-row adm-form-row-3">
            <div class="field">
              <label class="label" for="adm-setting-max_pending_per_user">Max pending per user</label>
              <input
                id="adm-setting-max_pending_per_user"
                class="input mono"
                type="number"
                :min="minFor('max_pending_per_user')"
                :max="maxFor('max_pending_per_user')"
                step="1"
                :value="numberTextValue('max_pending_per_user')"
                :disabled="saving"
                @input="setNumberText('max_pending_per_user', ($event.target as HTMLInputElement).value)"
              />
              <p v-if="fieldErrors.max_pending_per_user" class="field-error">{{ fieldErrors.max_pending_per_user }}</p>
            </div>
            <div class="field">
              <label class="label" for="adm-setting-rate_limit_per_minute">Rate limit / minute</label>
              <input
                id="adm-setting-rate_limit_per_minute"
                class="input mono"
                type="number"
                :min="minFor('rate_limit_per_minute')"
                :max="maxFor('rate_limit_per_minute')"
                step="1"
                :value="numberTextValue('rate_limit_per_minute')"
                :disabled="saving"
                @input="setNumberText('rate_limit_per_minute', ($event.target as HTMLInputElement).value)"
              />
              <p v-if="fieldErrors.rate_limit_per_minute" class="field-error">{{ fieldErrors.rate_limit_per_minute }}</p>
            </div>
            <div class="field">
              <label class="label" for="adm-setting-history_retention_days">History retention (days)</label>
              <input
                id="adm-setting-history_retention_days"
                class="input mono"
                type="number"
                :min="minFor('history_retention_days')"
                :max="maxFor('history_retention_days')"
                step="1"
                :value="numberTextValue('history_retention_days')"
                :disabled="saving"
                @input="setNumberText('history_retention_days', ($event.target as HTMLInputElement).value)"
              />
              <p v-if="fieldErrors.history_retention_days" class="field-error">{{ fieldErrors.history_retention_days }}</p>
            </div>
          </div>
        </div>
      </section>

      <section class="adm-note-panel" aria-labelledby="adm-settings-host">
        <span class="adm-note-icon"><Terminal :size="17" /></span>
        <div>
          <h2 id="adm-settings-host" class="adm-note-title">Host-level configuration</h2>
          <p class="adm-note-copy">
            Bind address, port, data directory, admin bootstrap credentials and the session secret are configured at
            launch and cannot be edited here. Use CLI flags or the corresponding
            <code>FAKE_DECISION_*</code> environment variables.
          </p>
          <div class="adm-code-inline">
            <code>FAKE_DECISION_HOST</code>
            <code>FAKE_DECISION_PORT</code>
            <code>FAKE_DECISION_DATA_DIR</code>
            <code>FAKE_DECISION_SECRET</code>
          </div>
          <p class="adm-note-copy">
            <strong>There is no billing configuration.</strong> This deployment has no plans, credits, invoices or
            monetization settings, and none are planned.
          </p>
        </div>
      </section>

      <div v-if="dirtyCount" class="adm-settings-dirtybar" role="status">
        <span><strong>{{ dirtyCount }}</strong> unsaved change{{ dirtyCount === 1 ? '' : 's' }}</span>
        <div class="adm-settings-dirtybar-actions">
          <button type="button" class="btn btn-sm" :disabled="saving" @click="resetChanges">Discard</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="!canSave">
            <Loader2 v-if="saving" :size="13" class="adm-spin" />
            <span>{{ saving ? 'Saving…' : 'Save changes' }}</span>
          </button>
        </div>
      </div>
    </form>
  </div>
</template>
