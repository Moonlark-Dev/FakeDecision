<script setup lang="ts">
import { CheckCircle2, Info, TriangleAlert, X, XCircle } from 'lucide-vue-next'
import { dismissToast, toastState } from '@/lib/toast'
</script>

<template>
  <Teleport to="body">
    <div class="toast-host" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="toast">
        <div v-for="item in toastState.items" :key="item.id" class="toast-item" :class="`toast-${item.tone}`">
          <span class="toast-icon">
            <CheckCircle2 v-if="item.tone === 'success'" :size="16" />
            <TriangleAlert v-else-if="item.tone === 'warning'" :size="16" />
            <XCircle v-else-if="item.tone === 'error'" :size="16" />
            <Info v-else :size="16" />
          </span>
          <span class="toast-copy">
            <span class="toast-message">{{ item.message }}</span>
            <span v-if="item.detail" class="toast-detail">{{ item.detail }}</span>
          </span>
          <button class="toast-close" type="button" aria-label="Dismiss" @click="dismissToast(item.id)">
            <X :size="14" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-host {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(380px, calc(100vw - 32px));
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 12px 12px 13px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: var(--shadow-md);
  pointer-events: auto;
}

.toast-success { border-left-color: var(--green); }
.toast-warning { border-left-color: var(--amber); }
.toast-error { border-left-color: var(--red); }

.toast-icon {
  display: flex;
  margin-top: 1px;
  color: var(--accent);
}

.toast-success .toast-icon { color: var(--green); }
.toast-warning .toast-icon { color: var(--amber); }
.toast-error .toast-icon { color: var(--red); }

.toast-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.toast-message {
  color: var(--ink);
  font-size: 13px;
  font-weight: 540;
  line-height: 1.4;
}

.toast-detail {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}

.toast-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--muted);
}

.toast-close:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
</style>
