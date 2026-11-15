<script setup lang="ts">
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import type { ModelForm } from '../types'

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

const model = defineModel<ModelForm>({ required: true })
</script>

<template>
  <div class="adm-form">
    <div class="adm-form-row">
      <div class="field">
        <label class="label" for="adm-model-name">Model name</label>
        <input
          id="adm-model-name"
          v-model="model.name"
          class="input mono"
          type="text"
          placeholder="jev-latest"
          :disabled="disabled"
        />
        <p class="field-hint">Letters, numbers, dots, underscores, slashes and hyphens.</p>
      </div>
      <div class="field">
        <label class="label" for="adm-model-display">Display name</label>
        <input
          id="adm-model-display"
          v-model="model.display_name"
          class="input"
          type="text"
          placeholder="Jev 1.4"
          :disabled="disabled"
        />
      </div>
    </div>

    <div class="adm-form-row adm-form-row-3">
      <div class="field">
        <label class="label" for="adm-model-protocol">Protocol</label>
        <select id="adm-model-protocol" v-model="model.protocol" class="select" :disabled="disabled">
          <option value="both">Both protocols</option>
          <option value="systemone">System One only</option>
          <option value="google">Gemini Decisions only</option>
        </select>
      </div>
      <div class="field">
        <label class="label" for="adm-model-context">Context window</label>
        <input
          id="adm-model-context"
          v-model.number="model.context_window"
          class="input mono"
          type="number"
          min="0"
          step="1024"
          :disabled="disabled"
        />
      </div>
      <div class="field">
        <label class="label" for="adm-model-sort">Sort order</label>
        <input
          id="adm-model-sort"
          v-model.number="model.sort_order"
          class="input mono"
          type="number"
          min="0"
          :disabled="disabled"
        />
      </div>
    </div>

    <div class="field">
      <label class="label" for="adm-model-description">Description</label>
      <textarea
        id="adm-model-description"
        v-model="model.description"
        class="textarea"
        rows="3"
        placeholder="Shown on the public model comparison page."
        :disabled="disabled"
      />
    </div>

    <div class="adm-toggle-row">
      <ToggleSwitch v-model="model.enabled" label="Model enabled" :disabled="disabled" />
      <span class="small">Enabled in the public model catalog</span>
    </div>
  </div>
</template>
