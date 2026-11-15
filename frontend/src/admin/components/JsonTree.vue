<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { isPlainObject } from '../utils'

const props = withDefaults(
  defineProps<{
    value: unknown
    name?: string
    depth?: number
    isLast?: boolean
  }>(),
  {
    name: '',
    depth: 0,
    isLast: true,
  },
)

interface JsonEntry {
  key: string
  value: unknown
}

const isArray = computed(() => Array.isArray(props.value))
const isObject = computed(() => isPlainObject(props.value))
const isComplex = computed(() => isArray.value || isObject.value)
const entries = computed<JsonEntry[]>(() => {
  if (Array.isArray(props.value)) {
    return props.value.map((value, index) => ({ key: String(index), value }))
  }
  if (isPlainObject(props.value)) {
    return Object.keys(props.value).map((key) => ({
      key,
      value: (props.value as Record<string, unknown>)[key],
    }))
  }
  return []
})

const autoCollapse = computed(() => entries.value.length > 8 || props.depth >= 3)
const open = ref(!autoCollapse.value)
watch(
  autoCollapse,
  (collapse) => {
    open.value = !collapse
  },
  { immediate: true },
)

const openBrace = computed(() => (isArray.value ? '[' : '{'))
const closeBrace = computed(() => (isArray.value ? ']' : '}'))
const summary = computed(() => (isArray.value ? `${entries.value.length} items` : `${entries.value.length} keys`))

function primitiveClass(value: unknown): string {
  if (value === null) return 'adm-json-null'
  if (value === undefined) return 'adm-json-undefined'
  if (typeof value === 'string') return 'adm-json-string'
  if (typeof value === 'number') return 'adm-json-number'
  if (typeof value === 'boolean') return 'adm-json-boolean'
  return 'adm-json-other'
}

function primitiveText(value: unknown): string {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  if (typeof value === 'string') {
    try {
      return JSON.stringify(value)
    } catch {
      return value
    }
  }
  if (typeof value === 'number' && !Number.isFinite(value)) return String(value)
  if (typeof value === 'bigint') return `${value.toString()}n`
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  try {
    return JSON.stringify(value) ?? String(value)
  } catch {
    return String(value)
  }
}
</script>

<template>
  <div class="adm-json-node">
    <div class="adm-json-line">
      <button
        v-if="isComplex"
        type="button"
        class="adm-json-toggle"
        :aria-expanded="open"
        :aria-label="open ? 'Collapse value' : 'Expand value'"
        @click="open = !open"
      >
        <ChevronRight :size="11" :class="{ 'adm-json-chevron-open': open }" />
      </button>
      <span v-else class="adm-json-spacer" aria-hidden="true" />
      <span v-if="name" class="adm-json-key">{{ name }}</span>
      <span v-if="name" class="adm-json-colon" aria-hidden="true">:</span>
      <template v-if="isComplex">
        <template v-if="open">
          <span class="adm-json-brace">{{ openBrace }}</span>
          <span class="adm-json-summary">{{ summary }}</span>
        </template>
        <template v-else>
          <span class="adm-json-brace">{{ openBrace }}…{{ closeBrace }}</span>
          <span class="adm-json-summary">{{ summary }}</span>
          <span v-if="!isLast" class="adm-json-comma">,</span>
        </template>
      </template>
      <template v-else>
        <span class="adm-json-value" :class="primitiveClass(value)">{{ primitiveText(value) }}</span>
        <span v-if="!isLast" class="adm-json-comma">,</span>
      </template>
    </div>

    <div v-if="isComplex && open" class="adm-json-children">
      <JsonTree
        v-for="(entry, index) in entries"
        :key="entry.key"
        :value="entry.value"
        :name="isArray ? `[${entry.key}]` : entry.key"
        :depth="depth + 1"
        :is-last="index === entries.length - 1"
      />
    </div>

    <div v-if="isComplex && open" class="adm-json-line adm-json-close">
      <span class="adm-json-spacer" aria-hidden="true" />
      <span class="adm-json-brace">{{ closeBrace }}</span>
      <span v-if="!isLast" class="adm-json-comma">,</span>
    </div>
  </div>
</template>
