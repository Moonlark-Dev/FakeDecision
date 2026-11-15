import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useAdminSocket } from './useAdminSocket'

/**
 * A local clock corrected by the server offset advertised over the admin socket.
 * Components that render ages/countdowns share it instead of each starting a timer.
 */
export function useAdminClock(intervalMs = 1000) {
  const socket = useAdminSocket()
  const now = ref(socket.now())
  let timer: number | null = null

  function tick() {
    now.value = socket.now()
  }

  onMounted(() => {
    tick()
    timer = window.setInterval(tick, intervalMs)
  })

  onBeforeUnmount(() => {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  })

  return now
}
