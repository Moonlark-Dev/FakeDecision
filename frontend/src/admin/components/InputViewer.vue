<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { File, FileAudio, FileText, FileVideo, Image as ImageIcon, ImageOff, Type } from 'lucide-vue-next'
import CopyButton from '@/components/CopyButton.vue'
import JsonTree from './JsonTree.vue'
import {
  blockMime,
  blockName,
  blockText,
  isHttpOrDataUrl,
  isPlainObject,
  mediaUri,
  rawJson,
} from '../utils'

const props = withDefaults(
  defineProps<{
    value: unknown
    inputText?: string
    kind?: string
    label?: string
  }>(),
  {
    inputText: '',
    kind: '',
    label: 'Input',
  },
)

type BlockKind = 'text' | 'image' | 'audio' | 'video' | 'file' | 'other'

interface BlockView {
  index: number
  type: string
  kind: BlockKind
  text: string | null
  uri: string | null
  mime: string
  name: string
  raw: Record<string, unknown>
}

function blockKind(type: string): BlockKind {
  if (type === 'text' || type === 'input_text') return 'text'
  if (type.includes('image')) return 'image'
  if (type.includes('audio')) return 'audio'
  if (type.includes('video')) return 'video'
  if (type.includes('file') || type === 'document' || type === 'pdf') return 'file'
  return 'other'
}

const stringValue = computed<string | null>(() => {
  if (typeof props.value === 'string') return props.value
  if ((props.value === null || props.value === undefined) && props.inputText) return props.inputText
  return null
})

const contentBlocks = computed<BlockView[]>(() => {
  if (!Array.isArray(props.value)) return []
  const result: BlockView[] = []
  for (let index = 0; index < props.value.length; index += 1) {
    const item = props.value[index]
    if (typeof item === 'string') {
      result.push({
        index,
        type: 'text',
        kind: 'text',
        text: item,
        uri: null,
        mime: '',
        name: '',
        raw: { type: 'text', text: item },
      })
      continue
    }
    if (!isPlainObject(item)) return []
    const type = typeof item['type'] === 'string' ? String(item['type']) : ''
    if (!type) return []
    result.push({
      index,
      type,
      kind: blockKind(type),
      text: blockText(item),
      uri: mediaUri(item),
      mime: blockMime(item),
      name: blockName(item),
      raw: item,
    })
  }
  return result
})

const isContentArray = computed(() => {
  if (!Array.isArray(props.value) || props.value.length === 0) return false
  if (contentBlocks.value.length !== props.value.length) return false
  return contentBlocks.value.every((block) => block.kind !== 'other' || block.text !== null)
})

const isString = computed(() => stringValue.value !== null)
const isComplex = computed(() => isPlainObject(props.value) || Array.isArray(props.value))
const displayKind = computed(() => {
  if (props.kind) return props.kind
  if (isString.value) return 'text'
  if (isContentArray.value) return 'multimodal'
  if (isComplex.value) return 'structured'
  return 'empty'
})
const copyValue = computed(() => stringValue.value ?? rawJson(props.value))

const broken = reactive<Record<number, boolean>>({})
watch(
  () => props.value,
  () => {
    for (const key of Object.keys(broken)) delete broken[Number(key)]
  },
)
</script>

<template>
  <section class="adm-input-viewer" aria-label="Request input">
    <header class="adm-input-head">
      <div class="adm-input-head-main">
        <span class="adm-input-label">{{ label }}</span>
        <span class="badge">{{ displayKind }}</span>
      </div>
      <CopyButton :text="copyValue" label="Copy JSON" />
    </header>

    <div v-if="isString" class="adm-input-text-shell">
      <pre class="adm-input-text">{{ stringValue }}</pre>
    </div>

    <div v-else-if="isContentArray" class="adm-input-blocks">
      <article v-for="block in contentBlocks" :key="block.index" class="adm-input-block">
        <header class="adm-block-label">
          <Type v-if="block.kind === 'text'" :size="13" />
          <ImageIcon v-else-if="block.kind === 'image'" :size="13" />
          <FileAudio v-else-if="block.kind === 'audio'" :size="13" />
          <FileVideo v-else-if="block.kind === 'video'" :size="13" />
          <FileText v-else-if="block.kind === 'file'" :size="13" />
          <File v-else :size="13" />
          <span>{{ block.type }}</span>
          <span v-if="block.mime" class="mono adm-block-mime">{{ block.mime }}</span>
          <span v-if="block.name" class="adm-block-name">{{ block.name }}</span>
        </header>

        <template v-if="block.kind === 'text' && block.text !== null">
          <pre class="adm-input-text">{{ block.text }}</pre>
        </template>

        <template v-else-if="block.kind === 'image'">
          <div class="adm-media-frame">
            <img
              v-if="block.uri && isHttpOrDataUrl(block.uri) && !broken[block.index]"
              :src="block.uri"
              alt="Image attachment"
              loading="lazy"
              referrerpolicy="no-referrer"
              @error="broken[block.index] = true"
            />
            <div v-else class="adm-media-placeholder">
              <ImageOff :size="16" />
              <span>{{ block.uri ? 'Image reference (not inline)' : 'Inline image data unavailable' }}</span>
            </div>
          </div>
          <div class="adm-media-meta">
            <code v-if="block.uri" class="adm-media-uri">{{ block.uri }}</code>
            <CopyButton v-if="block.uri" :text="block.uri" label="Copy URI" />
          </div>
        </template>

        <template v-else-if="block.kind === 'audio'">
          <audio v-if="block.uri && isHttpOrDataUrl(block.uri)" class="adm-media-player" controls preload="none" :src="block.uri" />
          <div class="adm-media-meta">
            <span class="muted tiny">Audio attachment</span>
            <code v-if="block.uri" class="adm-media-uri">{{ block.uri }}</code>
            <CopyButton v-if="block.uri" :text="block.uri" label="Copy URI" />
          </div>
        </template>

        <template v-else-if="block.kind === 'video'">
          <video v-if="block.uri && isHttpOrDataUrl(block.uri)" class="adm-media-player" controls preload="none" :src="block.uri" />
          <div class="adm-media-meta">
            <span class="muted tiny">Video attachment</span>
            <code v-if="block.uri" class="adm-media-uri">{{ block.uri }}</code>
            <CopyButton v-if="block.uri" :text="block.uri" label="Copy URI" />
          </div>
        </template>

        <template v-else-if="block.kind === 'file'">
          <div class="adm-media-file">
            <FileText :size="16" />
            <span>{{ block.name || 'File attachment' }}</span>
            <span v-if="block.mime" class="mono muted tiny">{{ block.mime }}</span>
          </div>
          <div class="adm-media-meta">
            <code v-if="block.uri" class="adm-media-uri">{{ block.uri }}</code>
            <a
              v-if="block.uri && isHttpOrDataUrl(block.uri)"
              class="btn btn-sm"
              :href="block.uri"
              target="_blank"
              rel="noopener noreferrer"
              >Open</a
            >
            <CopyButton v-if="block.uri" :text="block.uri" label="Copy URI" />
          </div>
        </template>

        <template v-else>
          <p v-if="block.text" class="adm-input-text adm-input-text-plain">{{ block.text }}</p>
          <div v-else class="adm-json-wrap"><JsonTree :value="block.raw" /></div>
        </template>
      </article>
    </div>

    <div v-else-if="isComplex" class="adm-json-wrap">
      <JsonTree :value="value" />
    </div>

    <p v-else class="adm-input-empty">No input captured for this request.</p>
  </section>
</template>
