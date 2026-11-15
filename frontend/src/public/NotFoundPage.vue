<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowLeft, ArrowRight } from 'lucide-vue-next'
import { useSession } from '@/lib/session'

const session = useSession()
const user = computed(() => session.state.user)
</script>

<template>
  <main class="pub-notfound">
    <div class="pub-notfound-grid" aria-hidden="true" />
    <div class="container pub-notfound-inner">
      <p class="pub-notfound-code mono" aria-hidden="true">404</p>
      <p class="eyebrow">Not found</p>
      <h1 class="pub-notfound-title">This page isn't part of the API.</h1>
      <p class="pub-notfound-lede">
        The address may be mistyped, or the page may have moved. Every decision request lives behind
        <code>/v1/systemone</code> and <code>/v1beta/decisions</code>.
      </p>
      <div class="pub-notfound-actions">
        <RouterLink to="/" class="btn btn-primary">
          <ArrowLeft :size="15" />
          Back home
        </RouterLink>
        <RouterLink to="/docs" class="btn">Documentation</RouterLink>
        <RouterLink :to="user ? '/console' : '/login'" class="btn">
          {{ user ? 'Open console' : 'Sign in' }}
          <ArrowRight :size="15" />
        </RouterLink>
      </div>

      <div class="pub-notfound-links">
        <span class="mono">Common pages</span>
        <RouterLink to="/models">Models</RouterLink>
        <RouterLink :to="{ path: '/docs', hash: '#quickstart' }">Quickstart</RouterLink>
        <RouterLink to="/console/keys">API keys</RouterLink>
      </div>
    </div>
  </main>
</template>
