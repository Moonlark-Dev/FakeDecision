<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ open: boolean; title?: string; width?: string }>(), {
  title: '',
  width: '520px',
})
const emit = defineEmits<{ close: [] }>()

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) emit('close')
}
watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
  },
)
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-backdrop" @mousedown.self="emit('close')">
        <div class="modal-card" :style="{ width }" role="dialog" aria-modal="true" :aria-label="title || 'Dialog'">
          <header class="modal-head">
            <h2 v-if="title" class="modal-title">{{ title }}</h2>
            <button class="btn btn-ghost btn-icon btn-sm" type="button" aria-label="Close" @click="emit('close')">
              <X :size="16" />
            </button>
          </header>
          <div class="modal-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="modal-foot">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(10, 14, 12, 0.42);
  backdrop-filter: blur(3px);
}

.modal-card {
  max-width: 100%;
  max-height: calc(100vh - 40px);
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px 0;
}

.modal-title {
  font-size: 16px;
}

.modal-body {
  padding: 18px;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 18px 18px;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 170ms ease;
}

.modal-enter-active .modal-card,
.modal-leave-active .modal-card {
  transition: transform 170ms ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-card,
.modal-leave-to .modal-card {
  transform: translateY(8px) scale(0.99);
}
</style>
