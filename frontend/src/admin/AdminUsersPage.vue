<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { KeyRound, Loader2, RefreshCw, Search, ShieldCheck, ShieldOff, UserRound, X } from 'lucide-vue-next'
import type { User } from '@/types/api'
import { get, patch } from '@/lib/api'
import { formatDate, formatNumber, statusLabel, timeAgo } from '@/lib/format'
import { toast } from '@/lib/toast'
import BaseModal from '@/components/BaseModal.vue'
import EmptyState from '@/components/EmptyState.vue'
import AdminDrawer from './components/AdminDrawer.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import PaginationBar from './components/PaginationBar.vue'
import type { UserDetailResponse } from './types'
import { errorMessage, initials, statusBadgeClass } from './utils'

interface UsersResponse {
  users: User[]
  total: number
}

const limit = 25
const rows = ref<User[]>([])
const total = ref(0)
const offset = ref(0)
const loading = ref(true)
const error = ref('')
const searchText = ref('')
const query = ref('')

const drawerOpen = ref(false)
const drawerUserId = ref<string | null>(null)
const detail = ref<UserDetailResponse | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const toggleTarget = ref<User | null>(null)
const toggleBusy = ref(false)

const passwordTarget = ref<User | null>(null)
const passwordOpen = ref(false)
const passwordValue = ref('')
const passwordShow = ref(false)
const passwordError = ref('')
const passwordBusy = ref(false)

let searchTimer: number | null = null

const toggleDisabling = computed(() => Boolean(toggleTarget.value && !toggleTarget.value.disabled))
const hasSearch = computed(() => Boolean(query.value))

async function load() {
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset.value) })
  if (query.value.trim()) params.set('q', query.value.trim())
  try {
    const response = await get<UsersResponse>(`/api/admin/users?${params.toString()}`)
    rows.value = response.users
    total.value = response.total
  } catch (err) {
    error.value = errorMessage(err, 'Could not load users.')
  } finally {
    loading.value = false
  }
}

function scheduleSearch() {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    searchTimer = null
    query.value = searchText.value
    offset.value = 0
    void load()
  }, 320)
}

function submitSearch() {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  query.value = searchText.value
  offset.value = 0
  void load()
}

function clearSearch() {
  searchText.value = ''
  query.value = ''
  offset.value = 0
  void load()
}

function onOffset(next: number) {
  offset.value = next
  void load()
}

async function loadUserDetail(id: string) {
  detailError.value = ''
  detailLoading.value = true
  try {
    const response = await get<UserDetailResponse>(`/api/admin/users/${encodeURIComponent(id)}`)
    if (drawerUserId.value !== id) return
    detail.value = response
  } catch (err) {
    if (drawerUserId.value === id) detailError.value = errorMessage(err, 'Could not load this user.')
  } finally {
    if (drawerUserId.value === id) detailLoading.value = false
  }
}

async function openDrawer(user: User) {
  drawerOpen.value = true
  drawerUserId.value = user.id
  detail.value = null
  await loadUserDetail(user.id)
}

function retryDrawer() {
  if (drawerUserId.value) void loadUserDetail(drawerUserId.value)
}

function closeDrawer() {
  drawerOpen.value = false
  drawerUserId.value = null
  detail.value = null
  detailError.value = ''
}

function replaceRow(updated: User) {
  const index = rows.value.findIndex((row) => row.id === updated.id)
  if (index >= 0) rows.value.splice(index, 1, { ...rows.value[index], ...updated })
  if (detail.value && detail.value.user.id === updated.id) {
    detail.value = { ...detail.value, user: { ...detail.value.user, ...updated } }
  }
}

function askToggle(user: User) {
  toggleTarget.value = user
}

async function confirmToggle() {
  const target = toggleTarget.value
  if (!target) return
  toggleBusy.value = true
  try {
    const response = await patch<{ user: User }>(`/api/admin/users/${encodeURIComponent(target.id)}`, {
      disabled: !target.disabled,
    })
    replaceRow(response.user)
    toast(target.disabled ? 'User enabled' : 'User disabled', 'success', {
      detail: response.user.email,
    })
    toggleTarget.value = null
  } catch (err) {
    toast('Could not update user', 'error', { detail: errorMessage(err) })
  } finally {
    toggleBusy.value = false
  }
}

function openPassword(user: User) {
  passwordTarget.value = user
  passwordValue.value = ''
  passwordError.value = ''
  passwordShow.value = false
  passwordOpen.value = true
}

function closePassword() {
  if (passwordBusy.value) return
  passwordOpen.value = false
  passwordTarget.value = null
  passwordValue.value = ''
  passwordError.value = ''
}

async function submitPassword() {
  const target = passwordTarget.value
  if (!target || passwordBusy.value) return
  passwordError.value = ''
  if (passwordValue.value.length < 10) {
    passwordError.value = 'Password must be at least 10 characters.'
    return
  }
  if (passwordValue.value.trim() !== passwordValue.value) {
    passwordError.value = 'Password must not begin or end with whitespace.'
    return
  }
  passwordBusy.value = true
  try {
    await patch(`/api/admin/users/${encodeURIComponent(target.id)}`, { password: passwordValue.value })
    toast('Password reset', 'success', {
      detail: `Sessions for ${target.email} were revoked.`,
    })
    passwordOpen.value = false
    passwordTarget.value = null
    passwordValue.value = ''
  } catch (err) {
    passwordError.value = errorMessage(err, 'Could not reset the password.')
  } finally {
    passwordBusy.value = false
  }
}

onMounted(() => {
  void load()
})

onBeforeUnmount(() => {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="adm-page">
    <header class="adm-page-head">
      <div>
        <p class="eyebrow adm-page-eyebrow">Administration</p>
        <h1 class="adm-page-title">Users</h1>
        <p class="adm-page-sub">Customer accounts, API keys usage and recent decisions. Administrators only.</p>
      </div>
      <div class="adm-page-actions">
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Refresh</span>
        </button>
      </div>
    </header>

    <section class="adm-panel">
      <header class="adm-panel-head">
        <form class="adm-filter-row" @submit.prevent="submitSearch">
          <div class="adm-search">
            <Search :size="14" class="adm-search-icon" aria-hidden="true" />
            <input
              v-model="searchText"
              class="input adm-search-input"
              type="search"
              placeholder="Search by email or name…"
              aria-label="Search users"
              @input="scheduleSearch"
            />
          </div>
          <button type="submit" class="btn btn-sm">Search</button>
          <button v-if="hasSearch" type="button" class="btn btn-sm btn-ghost" @click="clearSearch">
            <X :size="13" />
            <span>Clear</span>
          </button>
        </form>
        <span class="badge">{{ formatNumber(total) }} users</span>
      </header>

      <div v-if="error" class="adm-alert" role="alert">
        <span>{{ error }}</span>
        <button type="button" class="btn btn-sm" @click="load">Retry</button>
      </div>

      <div class="table-wrap">
        <table class="table adm-table">
          <thead>
            <tr>
              <th scope="col">User</th>
              <th scope="col">Email</th>
              <th scope="col">Created</th>
              <th scope="col">Last login</th>
              <th scope="col">Requests</th>
              <th scope="col">Status</th>
              <th scope="col"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading && !rows.length">
              <tr v-for="n in 6" :key="n"><td colspan="7"><div class="adm-skeleton-row" /></td></tr>
            </template>
            <tr v-else-if="!rows.length">
              <td colspan="7">
                <EmptyState title="No users found" description="Try a different search term." />
              </td>
            </tr>
            <template v-else>
              <tr v-for="user in rows" :key="user.id">
                <td>
                  <button type="button" class="adm-user-cell" @click="openDrawer(user)">
                    <span class="adm-avatar adm-avatar-sm">{{ initials(user.name) }}</span>
                    <span class="adm-user-cell-copy">
                      <span class="adm-user-name">{{ user.name }}</span>
                      <span class="mono muted tiny">{{ user.id }}</span>
                    </span>
                  </button>
                </td>
                <td class="mono adm-email-cell">{{ user.email }}</td>
                <td class="nowrap muted">{{ formatDate(user.created_at, false) }}</td>
                <td class="nowrap muted">{{ user.last_login_at ? timeAgo(user.last_login_at) : 'never' }}</td>
                <td class="mono">{{ formatNumber(user.request_count ?? 0) }}</td>
                <td>
                  <span class="badge" :class="user.disabled ? 'badge-red' : 'badge-green'">
                    {{ user.disabled ? 'Disabled' : 'Active' }}
                  </span>
                </td>
                <td>
                  <div class="adm-row-actions">
                    <button type="button" class="btn btn-sm btn-ghost" @click="openDrawer(user)">
                      <UserRound :size="13" />
                      <span>View</span>
                    </button>
                    <button type="button" class="btn btn-sm btn-ghost" @click="openPassword(user)">
                      <KeyRound :size="13" />
                      <span>Reset password</span>
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-ghost"
                      :class="{ 'adm-danger-text': !user.disabled }"
                      @click="askToggle(user)"
                    >
                      <ShieldOff v-if="!user.disabled" :size="13" />
                      <ShieldCheck v-else :size="13" />
                      <span>{{ user.disabled ? 'Enable' : 'Disable' }}</span>
                    </button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <footer class="adm-panel-foot adm-panel-foot-pagination">
        <PaginationBar :total="total" :limit="limit" :offset="offset" :loading="loading" @update:offset="onOffset" />
      </footer>
    </section>

    <AdminDrawer :open="drawerOpen" title="User detail" width="640px" @close="closeDrawer">
      <div v-if="detailLoading" class="adm-skeleton-list" aria-hidden="true">
        <div class="adm-skeleton-row" />
        <div class="adm-skeleton-row" />
        <div class="adm-skeleton-row adm-skeleton-row-tall" />
      </div>
      <div v-else-if="detailError" class="adm-alert" role="alert">
        <span>{{ detailError }}</span>
        <button type="button" class="btn btn-sm" @click="retryDrawer">Retry</button>
      </div>
      <template v-else-if="detail">
        <div class="adm-drawer-user">
          <span class="adm-avatar">{{ initials(detail.user.name) }}</span>
          <div>
            <p class="adm-drawer-user-name">{{ detail.user.name }}</p>
            <p class="mono muted">{{ detail.user.email }}</p>
          </div>
          <span class="badge" :class="detail.user.disabled ? 'badge-red' : 'badge-green'">
            {{ detail.user.disabled ? 'Disabled' : 'Active' }}
          </span>
        </div>

        <div class="adm-summary-grid">
          <div><span class="adm-summary-label">User id</span><span class="mono">{{ detail.user.id }}</span></div>
          <div><span class="adm-summary-label">Created</span><span>{{ formatDate(detail.user.created_at) }}</span></div>
          <div><span class="adm-summary-label">Last login</span><span>{{ detail.user.last_login_at ? formatDate(detail.user.last_login_at) : 'never' }}</span></div>
        </div>

        <section class="adm-detail-section">
          <h3 class="adm-section-title">Usage by model</h3>
          <ul v-if="detail.usage.length" class="adm-simple-list">
            <li v-for="row in detail.usage" :key="row.model">
              <span class="mono">{{ row.model }}</span>
              <span class="mono muted">{{ formatNumber(row.n) }} requests</span>
            </li>
          </ul>
          <p v-else class="adm-answer-empty">No requests recorded.</p>
        </section>

        <section class="adm-detail-section">
          <h3 class="adm-section-title">API keys</h3>
          <ul v-if="detail.keys.length" class="adm-simple-list">
            <li v-for="key in detail.keys" :key="key.id">
              <span>
                <span>{{ key.name }}</span>
                <span class="mono muted tiny">{{ key.prefix }}…{{ key.last_four }}</span>
              </span>
              <span class="muted tiny">
                {{ key.revoked_at ? `revoked ${formatDate(key.revoked_at, false)}` : `last used ${key.last_used_at ? timeAgo(key.last_used_at) : 'never'}` }}
              </span>
            </li>
          </ul>
          <p v-else class="adm-answer-empty">No API keys.</p>
        </section>

        <section class="adm-detail-section">
          <h3 class="adm-section-title">Recent requests</h3>
          <div v-if="detail.recent.length" class="table-wrap">
            <table class="table adm-table adm-table-compact">
              <thead><tr><th scope="col">Created</th><th scope="col">Model</th><th scope="col">Status</th><th scope="col">Duration</th></tr></thead>
              <tbody>
                <tr v-for="request in detail.recent" :key="request.id">
                  <td class="nowrap muted">{{ formatDate(request.created_at) }}</td>
                  <td class="mono">{{ request.model }}</td>
                  <td><span class="badge" :class="statusBadgeClass(request.status)">{{ statusLabel(request.status) }}</span></td>
                  <td class="mono">{{ request.duration_ms === null ? '—' : `${request.duration_ms} ms` }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="adm-answer-empty">No recent requests.</p>
        </section>
      </template>
    </AdminDrawer>

    <ConfirmDialog
      :open="Boolean(toggleTarget)"
      :title="toggleDisabling ? 'Disable this user?' : 'Enable this user?'"
      :message="toggleDisabling ? 'The user will be signed out and their API keys stop working until re-enabled.' : 'The user will be able to sign in and use their API keys again.'"
      :detail="toggleTarget ? `${toggleTarget.name} · ${toggleTarget.email}` : ''"
      :confirm-label="toggleDisabling ? 'Disable user' : 'Enable user'"
      :tone="toggleDisabling ? 'danger' : 'primary'"
      :busy="toggleBusy"
      @close="toggleTarget = null"
      @confirm="confirmToggle"
    />

    <BaseModal :open="passwordOpen" title="Reset password" width="460px" @close="closePassword">
      <form class="adm-form" @submit.prevent="submitPassword">
        <p class="muted small">
          Set a new password for <strong>{{ passwordTarget?.email }}</strong>. Existing sessions are revoked by the
          server; API keys remain valid.
        </p>
        <div class="field">
          <label class="label" for="adm-user-password">New password</label>
          <div class="adm-password-wrap">
            <input
              id="adm-user-password"
              v-model="passwordValue"
              class="input"
              :type="passwordShow ? 'text' : 'password'"
              autocomplete="new-password"
              minlength="10"
              placeholder="At least 10 characters"
              :disabled="passwordBusy"
            />
            <button
              type="button"
              class="adm-password-toggle"
              :aria-label="passwordShow ? 'Hide password' : 'Show password'"
              @click="passwordShow = !passwordShow"
            >
              <KeyRound :size="15" />
            </button>
          </div>
        </div>
        <p v-if="passwordError" class="field-error" role="alert">{{ passwordError }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-sm" :disabled="passwordBusy" @click="closePassword">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="passwordBusy" @click="submitPassword">
          <Loader2 v-if="passwordBusy" :size="13" class="adm-spin" />
          <span>{{ passwordBusy ? 'Resetting…' : 'Reset password' }}</span>
        </button>
      </template>
    </BaseModal>
  </div>
</template>
