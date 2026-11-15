<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    width?: string
  }>(),
  {
    title: '',
    width: '580px',
  },
)

const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
let previousFocus: HTMLElement | null = null
let previousOverflow = ''

function onKeydown(event: KeyboardEvent) {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
    return
  }
  if (event.key !== 'Tab' || !panel.value) return
  const focusable = Array.from(
    panel.value.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => element.offsetParent !== null)
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
      previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      void nextTick(() => closeButton.value?.focus())
    } else {
      document.body.style.overflow = previousOverflow
      if (previousFocus && document.contains(previousFocus)) previousFocus.focus()
      previousFocus = null
    }
  },
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = previousOverflow
})
</script>

<template>
  <Teleport to="body">
    <Transition name="adm-drawer">
      <div v-if="open" class="adm-drawer-scrim" @mousedown.self="emit('close')">
        <aside
          ref="panel"
          class="adm-drawer"
          :style="{ width }"
          role="dialog"
          aria-modal="true"
          aria-labelledby="adm-drawer-title"
        >
          <header class="adm-drawer-head">
            <div class="adm-drawer-head-main">
              <h2 id="adm-drawer-title" class="adm-drawer-title">{{ title }}</h2>
              <slot name="head-extra" />
            </div>
            <button
              ref="closeButton"
              type="button"
              class="btn btn-ghost btn-icon btn-sm"
              aria-label="Close panel"
              @click="emit('close')"
            >
              <X :size="16" />
            </button>
          </header>
          <div class="adm-drawer-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="adm-drawer-foot">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>
