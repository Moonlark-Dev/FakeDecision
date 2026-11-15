<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Boxes, Loader2, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-vue-next'
import type { Model } from '@/types/api'
import { del, get, patch, post } from '@/lib/api'
import { formatNumber, formatTokenWindow } from '@/lib/format'
import { toast } from '@/lib/toast'
import BaseModal from '@/components/BaseModal.vue'
import EmptyState from '@/components/EmptyState.vue'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import ModelFormFields from './components/ModelFormFields.vue'
import { errorMessage, protocolLabel } from './utils'
import type { ModelForm, ModelsResponse } from './types'

const models = ref<Model[]>([])
const loading = ref(true)
const error = ref('')
const busyId = ref<string | null>(null)

const createOpen = ref(false)
const createBusy = ref(false)
const createError = ref('')
const createForm = ref<ModelForm>(emptyForm())

const editTarget = ref<Model | null>(null)
const editBusy = ref(false)
const editError = ref('')
const editForm = ref<ModelForm>(emptyForm())

const deleteTarget = ref<Model | null>(null)
const deleteBusy = ref(false)

const editing = computed(() => Boolean(editTarget.value))
const totalAssigned = computed(() => models.value.reduce((total, model) => total + (model.assigned_count ?? 0), 0))

function emptyForm(): ModelForm {
  return {
    name: '',
    display_name: '',
    protocol: 'both',
    context_window: 65536,
    description: '',
    sort_order: 100,
    enabled: true,
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await get<ModelsResponse>('/api/admin/models')
    models.value = response.models
  } catch (err) {
    error.value = errorMessage(err, 'Could not load the model catalog.')
  } finally {
    loading.value = false
  }
}

function replaceModel(updated: Model) {
  const index = models.value.findIndex((model) => model.id === updated.id)
  if (index >= 0) models.value.splice(index, 1, { ...models.value[index], ...updated })
}

function openCreate() {
  createForm.value = emptyForm()
  createError.value = ''
  createOpen.value = true
}

function validate(form: ModelForm): string {
  if (!form.name.trim()) return 'Model name is required.'
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/.test(form.name.trim())) {
    return 'Model name must start with a letter or number and may only contain letters, numbers, dots, underscores, slashes and hyphens (max 128 characters).'
  }
  if (!form.display_name.trim()) return 'Display name is required.'
  if (!Number.isFinite(form.context_window) || form.context_window < 0) return 'Context window must be zero or greater.'
  if (!Number.isFinite(form.sort_order) || form.sort_order < 0) return 'Sort order must be zero or greater.'
  return ''
}

async function submitCreate() {
  if (createBusy.value) return
  createError.value = validate(createForm.value)
  if (createError.value) return
  createBusy.value = true
  try {
    const response = await post<{ model: Model }>('/api/admin/models', {
      name: createForm.value.name.trim(),
      display_name: createForm.value.display_name.trim(),
      protocol: createForm.value.protocol,
      description: createForm.value.description.trim(),
      context_window: Number(createForm.value.context_window),
      enabled: createForm.value.enabled,
      sort_order: Number(createForm.value.sort_order),
    })
    models.value.push(response.model)
    models.value = models.value.slice().sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))
    toast('Model created', 'success', { detail: response.model.name })
    createOpen.value = false
  } catch (err) {
    createError.value = errorMessage(err, 'Could not create the model.')
  } finally {
    createBusy.value = false
  }
}

function openEdit(model: Model) {
  editTarget.value = model
  editForm.value = {
    name: model.name,
    display_name: model.display_name,
    protocol: model.protocol,
    context_window: model.context_window,
    description: model.description,
    sort_order: model.sort_order,
    enabled: model.enabled,
  }
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
  editError.value = validate(editForm.value)
  if (editError.value) return
  editBusy.value = true
  try {
    const response = await patch<{ model: Model }>(`/api/admin/models/${encodeURIComponent(target.id)}`, {
      name: editForm.value.name.trim(),
      display_name: editForm.value.display_name.trim(),
      protocol: editForm.value.protocol,
      description: editForm.value.description.trim(),
      context_window: Number(editForm.value.context_window),
      enabled: editForm.value.enabled,
      sort_order: Number(editForm.value.sort_order),
    })
    replaceModel(response.model)
    toast('Model updated', 'success', { detail: response.model.name })
    editTarget.value = null
    await load()
  } catch (err) {
    editError.value = errorMessage(err, 'Could not update the model.')
  } finally {
    editBusy.value = false
  }
}

async function toggleEnabled(model: Model) {
  if (busyId.value) return
  busyId.value = model.id
  try {
    const response = await patch<{ model: Model }>(`/api/admin/models/${encodeURIComponent(model.id)}`, {
      enabled: !model.enabled,
    })
    replaceModel(response.model)
    toast(response.model.enabled ? 'Model enabled' : 'Model disabled', 'success', { detail: response.model.name })
  } catch (err) {
    toast('Could not change model state', 'error', { detail: errorMessage(err) })
  } finally {
    busyId.value = null
  }
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return
  deleteBusy.value = true
  try {
    await del(`/api/admin/models/${encodeURIComponent(target.id)}`)
    models.value = models.value.filter((model) => model.id !== target.id)
    toast('Model deleted', 'success', { detail: target.name })
    deleteTarget.value = null
  } catch (err) {
    toast('Model not deleted', 'error', { detail: errorMessage(err) })
  } finally {
    deleteBusy.value = false
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
        <h1 class="adm-page-title">Models &amp; routing</h1>
        <p class="adm-page-sub">The model catalog exposed to the public API and to operator assignment.</p>
      </div>
      <div class="adm-page-actions">
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Refresh</span>
        </button>
        <button type="button" class="btn btn-primary btn-sm" @click="openCreate">
          <Plus :size="14" />
          <span>New model</span>
        </button>
      </div>
    </header>

    <div class="adm-chip-strip">
      <span class="badge"><Boxes :size="12" /> {{ models.length }} models</span>
      <span class="badge badge-green">{{ models.filter((model) => model.enabled).length }} enabled</span>
      <span class="badge">{{ formatNumber(totalAssigned) }} operator assignments</span>
    </div>

    <div v-if="error" class="adm-alert" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load">Retry</button>
    </div>

    <section class="adm-panel">
      <div class="table-wrap">
        <table class="table adm-table">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Protocol</th>
              <th scope="col">Context</th>
              <th scope="col">Assigned</th>
              <th scope="col">Sort</th>
              <th scope="col">Enabled</th>
              <th scope="col"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading && !models.length">
              <tr v-for="n in 4" :key="n"><td colspan="7"><div class="adm-skeleton-row" /></td></tr>
            </template>
            <tr v-else-if="!models.length">
              <td colspan="7"><EmptyState title="No models" description="Create the first model in the catalog." /></td>
            </tr>
            <template v-else>
              <tr v-for="model in models" :key="model.id">
                <td>
                  <div class="adm-model-cell-copy">
                    <span class="adm-model-display">{{ model.display_name }}</span>
                    <span class="mono muted tiny">{{ model.name }}</span>
                    <span v-if="model.description" class="adm-model-desc">{{ model.description }}</span>
                  </div>
                </td>
                <td><span class="badge">{{ protocolLabel(model.protocol) }}</span></td>
                <td class="mono">{{ formatTokenWindow(model.context_window) }}</td>
                <td class="mono">{{ formatNumber(model.assigned_count ?? 0) }}</td>
                <td class="mono">{{ model.sort_order }}</td>
                <td>
                  <span class="adm-toggle-cell">
                    <ToggleSwitch
                      :model-value="model.enabled"
                      :label="`Toggle ${model.display_name}`"
                      :disabled="busyId === model.id"
                      @update:model-value="toggleEnabled(model)"
                    />
                    <span class="muted tiny">{{ model.enabled ? 'On' : 'Off' }}</span>
                  </span>
                </td>
                <td>
                  <div class="adm-row-actions">
                    <button type="button" class="btn btn-sm btn-ghost" @click="openEdit(model)">
                      <Pencil :size="13" />
                      <span>Edit</span>
                    </button>
                    <button type="button" class="btn btn-sm btn-ghost adm-danger-text" @click="deleteTarget = model">
                      <Trash2 :size="13" />
                      <span>Delete</span>
                    </button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <BaseModal :open="createOpen" title="New model" width="600px" @close="createOpen = false">
      <form class="adm-form" @submit.prevent="submitCreate">
        <ModelFormFields v-model="createForm" :disabled="createBusy" />
        <p v-if="createError" class="field-error" role="alert">{{ createError }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-sm" :disabled="createBusy" @click="createOpen = false">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="createBusy" @click="submitCreate">
          <Loader2 v-if="createBusy" :size="13" class="adm-spin" />
          <span>{{ createBusy ? 'Creating…' : 'Create model' }}</span>
        </button>
      </template>
    </BaseModal>

    <BaseModal :open="editing" title="Edit model" width="600px" @close="closeEdit">
      <form v-if="editTarget" class="adm-form" @submit.prevent="submitEdit">
        <p class="muted small">
          Renaming a model rewrites its operator assignments. Historical requests keep the old model string.
        </p>
        <ModelFormFields v-model="editForm" :disabled="editBusy" />
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
      :open="Boolean(deleteTarget)"
      title="Delete this model?"
      message="Deletion is only permitted when the model has no historical requests. Otherwise disable the model instead."
      :detail="deleteTarget ? `${deleteTarget.display_name} · ${deleteTarget.name} · ${deleteTarget.assigned_count ?? 0} assignments` : ''"
      confirm-label="Delete model"
      :busy="deleteBusy"
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>
