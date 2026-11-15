<script setup lang="ts">
import { watch } from 'vue'
import { RouterView } from 'vue-router'
import ToastHost from '@/components/ToastHost.vue'
import { useSession } from '@/lib/session'

const session = useSession()

watch(
  () => session.state.site?.logo_url,
  (url) => {
    const link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]')
    if (link) link.href = url || '/favicon.svg'
  },
  { immediate: true },
)
</script>

<template>
  <RouterView />
  <ToastHost />
</template>
