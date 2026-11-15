<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Loader2, Pencil, Plus, RefreshCw, ShieldCheck, ShieldOff, UserCog } from 'lucide-vue-next'
import type { AdminUser, Model } from '@/types/api'
import { get, patch, post } from '@/lib/api'
import { timeAgo } from '@/lib/format'
import { toast } from '@/lib/toast'
import BaseModal from '@/components/BaseModal.vue'
import EmptyState from '@/components/EmptyState.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import { useAdminSocket } from './useAdminSocket'
import { useSession } from '@/lib/session'
import { errorMessage, initials } from './utils'
import type { ModelsResponse, OperatorsResponse } from './types'

const socket = useAdminSocket()
const session = useSession()

const operators = ref<AdminUser[]>([])
const models = ref<Model[]>([])
const loading = ref(true)
const error = ref('')

const createOpen = ref(false)
const createBusy = ref(false)
const createError = ref('')
const createForm = ref({ email: '', name: '', password: '', models: [] as string[] })

const editTarget = ref<AdminUser | null>(null)
const editBusy = ref(false)
const editError = ref('')
const editForm = ref({ name: '', password: '', models: [] as string[] })

const toggleTarget = ref<AdminUser | null>(null)
const toggleBusy = ref(false)

const currentAdminId = computed(() => session.state.admin?.id || '')
const presence = computed<Record<string, boolean>>(() => {
  const map: Record<string, boolean> = {}
  for (const operator of socket.state.presence) map[operator.id] = operator.online
  return map
})
const editing = computed(() => Boolean(editTarget.value))
const toggleDisabling = computed(() => Boolean(toggleTarget.value && !toggleTarget.value.disabled))
const onlineCount = computed(() => operators.value.filter((operator) => isOnline(operator)).length)

function isOnline(operator: AdminUser): boolean {
  return operator.id in presence.value ? presence.value[operator.id] : Boolean(operator.online)
}

function isAdminRow(operator: AdminUser): boolean {
  return operator.role === 'admin'
}

function isSelf(operator: AdminUser): boolean {
  return operator.id === currentAdminId.value
}

function modelLabel(name: string): string {
  const model = models.value.find((item) => item.name === name)
  return model?.display_name || name
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [operatorResponse, modelResponse] = await Promise.all([
      get<OperatorsResponse>('/api/admin/operators'),
      get<ModelsResponse>('/api/admin/models'),
    ])
    operators.value = operatorResponse.operators
    models.value = modelResponse.models
  } catch (err) {
    error.value = errorMessage(err, 'Could not load operators.')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.value = { email: '', name: '', password: '', models: [] }
  createError.value = ''
  createOpen.value = true
}

async function submitCreate() {
  if (createBusy.value) return
  createError.value = ''
  if (!createForm.value.email.trim() || !createForm.value.name.trim()) {
    createError.value = 'Email and name are required.'
    return
  }
  if (createForm.value.password.length < 10) {
    createError.value = 'Password must be at least 10 characters.'
    return
  }
  createBusy.value = true
  try {
    await post<{ operator: AdminUser }>('/api/admin/operators', {
      email: createForm.value.email.trim(),
      name: createForm.value.name.trim(),
      password: createForm.value.password,
      models: createForm.value.models,
    })
    toast('Operator created', 'success', { detail: createForm.value.email.trim() })
    createOpen.value = false
    await load()
  } catch (err) {
    createError.value = errorMessage(err, 'Could not create the operator.')
  } finally {
    createBusy.value = false
  }
}

function openEdit(operator: AdminUser) {
  if (isAdminRow(operator)) {
    toast('Admin accounts cannot be edited from this list', 'warning')
    return
  }
  editTarget.value = operator
  editForm.value = { name: operator.name, password: '', models: [...operator.models] }
  editError.value = ''
}

function closeEdit() {
  if (editBusy.value) return
  editTarget.value = null
  editError.value = ''
}

async function submitEdit() {
  const target = editTarget.value
  if (!target || editBusy.value) return
  editError.value = ''
  if (!editForm.value.name.trim()) {
    editError.value = 'Name is required.'
    return
  }
  if (editForm.value.password && editForm.value.password.length < 10) {
    editError.value = 'Password must be at least 10 characters.'
    return
  }
  editBusy.value = true
  try {
    const body: Record<string, unknown> = {
      name: editForm.value.name.trim(),
      models: editForm.value.models,
    }
    if (editForm.value.password) body.password = editForm.value.password
    await patch<{ operator: AdminUser }>(`/api/admin/operators/${encodeURIComponent(target.id)}`, body)
    toast('Operator updated', 'success', { detail: target.email })
    editTarget.value = null
    await load()
  } catch (err) {
    editError.value = errorMessage(err, 'Could not update the operator.')
  } finally {
    editBusy.value = false
  }
}

function askToggle(operator: AdminUser) {
  if (isAdminRow(operator)) {
    toast('Admin accounts cannot be enabled or disabled here', 'warning')
    return
  }
  if (isSelf(operator)) {
    toast('You cannot disable your own account', 'warning')
    return
  }
  toggleTarget.value = operator
}

async function confirmToggle() {
  const target = toggleTarget.value
  if (!target) return
  toggleBusy.value = true
  try {
    await patch<{ operator: AdminUser }>(`/api/admin/operators/${encodeURIComponent(target.id)}`, {
      disabled: !target.disabled,
    })
    toast(target.disabled ? 'Operator enabled' : 'Operator disabled', 'success', { detail: target.email })
    toggleTarget.value = null
    await load()
  } catch (err) {
    toast('Could not update the operator', 'error', { detail: errorMessage(err) })
  } finally {
    toggleBusy.value = false
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
        <h1 class="adm-page-title">Operators</h1>
        <p class="adm-page-sub">Backoffice accounts, model assignments and live presence.</p>
      </div>
      <div class="adm-page-actions">
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Refresh</span>
        </button>
        <button type="button" class="btn btn-primary btn-sm" @click="openCreate">
          <Plus :size="14" />
          <span>New operator</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="adm-alert" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load">Retry</button>
    </div>

    <section class="adm-panel">
      <header class="adm-panel-head">
        <div>
          <h2 class="adm-panel-title">Backoffice accounts</h2>
          <p class="adm-panel-sub">{{ operators.length }} accounts · {{ onlineCount }} online</p>
        </div>
        <span class="badge">{{ operators.filter((operator) => !operator.disabled).length }} active</span>
      </header>

      <div class="table-wrap">
        <table class="table adm-table">
          <thead>
            <tr>
              <th scope="col">Operator</th>
              <th scope="col">Models</th>
              <th scope="col">Presence</th>
              <th scope="col">Active</th>
              <th scope="col">Last login</th>
              <th scope="col">Status</th>
              <th scope="col"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading && !operators.length">
              <tr v-for="n in 4" :key="n"><td colspan="7"><div class="adm-skeleton-row" /></td></tr>
            </template>
            <tr v-else-if="!operators.length">
              <td colspan="7"><EmptyState title="No operators" description="Create the first operator account." /></td>
            </tr>
            <template v-else>
              <tr v-for="operator in operators" :key="operator.id">
                <td>
                  <div class="adm-user-cell as-static">
                    <span class="adm-avatar adm-avatar-sm">{{ initials(operator.name) }}</span>
                    <span class="adm-user-cell-copy">
                      <span class="adm-user-name">
                        {{ operator.name }}
                        <span v-if="isAdminRow(operator)" class="badge badge-blue">admin</span>
                        <span v-else-if="isSelf(operator)" class="badge">you</span>
                      </span>
                      <span class="mono muted tiny">{{ operator.email }}</span>
                    </span>
                  </div>
                </td>
                <td>
                  <div class="adm-chip-row">
                    <span v-for="model in operator.models" :key="model" class="badge">{{ modelLabel(model) }}</span>
                    <span v-if="!operator.models.length" class="muted tiny">No model assigned</span>
                  </div>
                </td>
                <td>
                  <span class="adm-presence" :class="{ 'is-online': isOnline(operator) }">
                    <span class="dot" :class="{ 'dot-live': isOnline(operator) }" />
                    {{ isOnline(operator) ? 'Online' : 'Offline' }}
                  </span>
                </td>
                <td class="mono">{{ operator.active_requests ?? 0 }}</td>
                <td class="nowrap muted">{{ operator.last_login_at ? timeAgo(operator.last_login_at) : 'never' }}</td>
                <td>
                  <span class="badge" :class="operator.disabled ? 'badge-red' : 'badge-green'">
                    {{ operator.disabled ? 'Disabled' : 'Active' }}
                  </span>
                </td>
                <td>
                  <div class="adm-row-actions">
                    <button
                      type="button"
                      class="btn btn-sm btn-ghost"
                      :disabled="isAdminRow(operator)"
                      :title="isAdminRow(operator) ? 'Admin accounts are managed outside this list' : 'Edit operator'"
                      @click="openEdit(operator)"
                    >
                      <Pencil :size="13" />
                      <span>Edit</span>
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-ghost"
                      :disabled="isAdminRow(operator) || isSelf(operator)"
                      :title="isAdminRow(operator) ? 'Admin accounts are managed outside this list' : isSelf(operator) ? 'You cannot disable your own account' : ''"
                      @click="askToggle(operator)"
                    >
                      <ShieldOff v-if="!operator.disabled" :size="13" />
                      <ShieldCheck v-else :size="13" />
                      <span>{{ operator.disabled ? 'Enable' : 'Disable' }}</span>
                    </button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <BaseModal :open="createOpen" title="New operator" width="560px" @close="createOpen = false">
      <form class="adm-form" @submit.prevent="submitCreate">
        <div class="adm-form-row">
          <div class="field">
            <label class="label" for="adm-operator-email">Email</label>
            <input id="adm-operator-email" v-model="createForm.email" class="input" type="email" autocomplete="off" :disabled="createBusy" />
          </div>
          <div class="field">
            <label class="label" for="adm-operator-name">Display name</label>
            <input id="adm-operator-name" v-model="createForm.name" class="input" type="text" autocomplete="off" :disabled="createBusy" />
          </div>
        </div>
        <div class="field">
          <label class="label" for="adm-operator-password">Password</label>
          <input
            id="adm-operator-password"
            v-model="createForm.password"
            class="input"
            type="password"
            autocomplete="new-password"
            minlength="10"
            placeholder="At least 10 characters"
            :disabled="createBusy"
          />
        </div>
        <div class="field">
          <span class="label">Model assignments</span>
          <p class="field-hint">Operators only see requests for the models assigned here.</p>
          <div class="adm-model-picker">
            <label v-for="model in models" :key="model.id" class="adm-model-check">
              <input v-model="createForm.models" type="checkbox" :value="model.name" :disabled="createBusy" />
              <span class="adm-model-check-copy">
                <span>{{ model.display_name }}</span>
                <span class="mono muted tiny">{{ model.name }}</span>
              </span>
            </label>
          </div>
        </div>
        <p v-if="createError" class="field-error" role="alert">{{ createError }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-sm" :disabled="createBusy" @click="createOpen = false">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="createBusy" @click="submitCreate">
          <Loader2 v-if="createBusy" :size="13" class="adm-spin" />
          <span>{{ createBusy ? 'Creating…' : 'Create operator' }}</span>
        </button>
      </template>
    </BaseModal>

    <BaseModal :open="editing" title="Edit operator" width="560px" @close="closeEdit">
      <form v-if="editTarget" class="adm-form" @submit.prevent="submitEdit">
        <div class="adm-modal-identity">
          <span class="adm-avatar">{{ initials(editTarget.name) }}</span>
          <span>
            <span class="adm-user-name">{{ editTarget.name }}</span>
            <span class="mono muted tiny">{{ editTarget.email }}</span>
          </span>
        </div>
        <div class="field">
          <label class="label" for="adm-edit-name">Display name</label>
          <input id="adm-edit-name" v-model="editForm.name" class="input" type="text" :disabled="editBusy" />
        </div>
        <div class="field">
          <label class="label" for="adm-edit-password">New password <span class="muted">(optional)</span></label>
          <input
            id="adm-edit-password"
            v-model="editForm.password"
            class="input"
            type="password"
            autocomplete="new-password"
            placeholder="Leave blank to keep the current password"
            :disabled="editBusy"
          />
        </div>
        <div class="field">
          <span class="label">Model assignments</span>
          <div class="adm-model-picker">
            <label v-for="model in models" :key="model.id" class="adm-model-check">
              <input v-model="editForm.models" type="checkbox" :value="model.name" :disabled="editBusy" />
              <span class="adm-model-check-copy">
                <span>{{ model.display_name }}</span>
                <span class="mono muted tiny">{{ model.name }}</span>
              </span>
            </label>
          </div>
        </div>
        <p v-if="editError" class="field-error" role="alert">{{ editError }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-sm" :disabled="editBusy" @click="closeEdit">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="editBusy" @click="submitEdit">
          <Loader2 v-if="editBusy" :size="13" class="adm-spin" />
          <span>{{ editBusy ? 'Saving…' : 'Save changes' }}</span>
        </button>
      </template>
    </BaseModal>

    <ConfirmDialog
      :open="Boolean(toggleTarget)"
      :title="toggleDisabling ? 'Disable this operator?' : 'Enable this operator?'"
      :message="toggleDisabling ? 'Active requests assigned to this operator return to the queue. Their sessions are revoked immediately.' : 'The operator can sign in again and receive model-matched requests.'"
      :detail="toggleTarget ? `${toggleTarget.name} · ${toggleTarget.email}` : ''"
      :confirm-label="toggleDisabling ? 'Disable operator' : 'Enable operator'"
      :tone="toggleDisabling ? 'danger' : 'primary'"
      :busy="toggleBusy"
      @close="toggleTarget = null"
      @confirm="confirmToggle"
    />

    <div class="adm-inline-note">
      <UserCog :size="13" />
      Admin accounts are not editable here; the backend rejects changes to the administrator row. Presence updates live
      over the operations socket.
    </div>
  </div>
</template>
