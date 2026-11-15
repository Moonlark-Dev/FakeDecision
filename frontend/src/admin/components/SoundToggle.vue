<script setup lang="ts">
import { computed } from 'vue'
import { AudioLines, Volume2, VolumeX } from 'lucide-vue-next'
import { useAdminSocket } from '../useAdminSocket'

const socket = useAdminSocket()
const enabled = socket.soundEnabled
const audio = socket.audioState
const running = computed(() => audio.value === 'running')
const unsupported = computed(() => audio.value === 'unsupported')
const showUnlock = computed(() => enabled.value && !running.value && !unsupported.value)
const statusText = computed(() => {
  if (unsupported.value) return 'Audio is not supported in this browser.'
  if (!enabled.value) return 'Notification sound is off.'
  if (!running.value) return 'Notification sound is on. Enable browser audio to hear alerts.'
  return 'Notification sound is on.'
})

function toggle() {
  socket.setSound(!enabled.value)
}

async function enableAudio() {
  const ok = await socket.unlockAudio()
  if (ok && !enabled.value) socket.setSound(true)
}
</script>

<template>
  <div class="adm-sound">
    <button
      type="button"
      class="btn btn-ghost btn-sm adm-sound-toggle"
      :class="{ 'is-on': enabled }"
      :aria-pressed="enabled"
      :aria-label="enabled ? 'Turn notification sound off' : 'Turn notification sound on'"
      :title="statusText"
      @click="toggle"
    >
      <Volume2 v-if="enabled" :size="15" />
      <VolumeX v-else :size="15" />
      <span class="adm-sound-label">{{ enabled ? 'Sound on' : 'Sound off' }}</span>
    </button>
    <button
      v-if="showUnlock"
      type="button"
      class="adm-sound-hint"
      title="Browsers require a click before audio can play"
      @click="enableAudio"
    >
      <AudioLines :size="12" />
      <span>Enable audio</span>
    </button>
    <span class="sr-only" aria-live="polite">{{ statusText }}</span>
  </div>
</template>
