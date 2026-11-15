<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Component } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  Boxes,
  ChevronRight,
  History,
  LayoutDashboard,
  ListChecks,
  Loader2,
  Lock,
  LogOut,
  Menu,
  Moon,
  ScrollText,
  Settings,
  Sun,
  UserCog,
  Users,
} from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import SoundToggle from './components/SoundToggle.vue'
import { useSession } from '@/lib/session'
import { useTheme } from '@/lib/theme'
import { toast } from '@/lib/toast'
import { useAdminSocket } from './useAdminSocket'
import { initials } from './utils'
import '@/styles/admin.css'

interface NavItem {
  name: string
  label: string
  icon: Component
}

const route = useRoute()
const router = useRouter()
const session = useSession()
const socket = useAdminSocket()
const theme = useTheme()

const drawerOpen = ref(false)
const signingOut = ref(false)

const admin = computed(() => session.state.admin)
const isAdmin = computed(() => admin.value?.role === 'admin')
const userName = computed(() => admin.value?.name || 'Operator')
const userRole = computed(() => (isAdmin.value ? 'Administrator' : 'Operator'))
const brandName = computed(() => session.state.site?.site_name || 'Noema')
const version = computed(() => session.state.site?.version || '')
const title = computed(() => String(route.meta.title || 'Admin'))
const isDark = computed(() => theme.theme.value === 'dark')
const queueCount = computed(() => socket.state.pending.length)

const operations: NavItem[] = [
  { name: 'admin-overview', label: 'Overview', icon: LayoutDashboard },
  { name: 'admin-queue', label: 'Decision queue', icon: ListChecks },
  { name: 'admin-history', label: 'History', icon: History },
]

const administration: NavItem[] = [
  { name: 'admin-users', label: 'Users', icon: Users },
  { name: 'admin-operators', label: 'Operators', icon: UserCog },
  { name: 'admin-models', label: 'Models & routing', icon: Boxes },
  { name: 'admin-settings', label: 'Settings', icon: Settings },
  { name: 'admin-audit', label: 'Audit log', icon: ScrollText },
]

const sectionLabel = computed(() => {
  const name = String(route.name || '')
  return administration.some((item) => item.name === name) ? 'Administration' : 'Operations'
})

const connectionLabel = computed(() => {
  if (socket.state.connected && socket.state.hello) return 'Live'
  if (socket.state.connected) return 'Syncing'
  if (socket.state.connecting) return 'Connecting'
  if (socket.state.attempts > 0) return 'Reconnecting'
  return 'Offline'
})
const connectionClass = computed(() => {
  if (socket.state.connected) return socket.state.hello ? 'live' : 'connecting'
  if (socket.state.connecting || socket.state.attempts > 0) return 'connecting'
  return 'offline'
})
const connectionTitle = computed(() => {
  if (socket.state.lastError) return socket.state.lastError
  if (socket.state.connected) return 'WebSocket connected'
  return 'WebSocket unavailable — the queue falls back to REST snapshots'
})
const connectionAnnouncement = computed(() => `Realtime connection: ${connectionLabel.value}`)

function isActive(name: string): boolean {
  return String(route.name || '') === name
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && drawerOpen.value) drawerOpen.value = false
}

watch(
  () => route.fullPath,
  () => {
    drawerOpen.value = false
  },
)

watch(
  () => socket.state.lastError,
  async (message) => {
    if (message !== 'Admin session expired' || !session.state.admin) return
    try {
      const refreshed = await session.refreshAdmin()
      if (refreshed) {
        socket.connect()
        return
      }
    } catch {
      return
    }
    if (!session.state.admin) {
      const next = route.fullPath
      socket.reset()
      toast('Admin session expired. Sign in again.', 'warning')
      await router.replace({ name: 'admin-login', query: { next } })
    }
  },
)

async function signOut() {
  if (signingOut.value) return
  signingOut.value = true
  try {
    socket.reset()
    try {
      await session.adminLogout()
    } catch {
      /* the cookie may already be gone */
    }
    await router.push({ name: 'admin-login' })
  } catch (error) {
    toast('Sign out failed', 'error', {
      detail: error instanceof Error ? error.message : undefined,
    })
  } finally {
    signingOut.value = false
  }
}

onMounted(() => {
  socket.connect()
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  socket.disconnect()
})
</script>

<template>
  <a class="adm-skip" href="#adm-content">Skip to content</a>
  <div class="adm-shell">
    <div v-if="drawerOpen" class="adm-scrim" aria-hidden="true" @click="drawerOpen = false" />

    <aside id="adm-sidebar" class="adm-sidebar" :class="{ 'is-open': drawerOpen }" aria-label="Admin navigation">
      <div class="adm-side-head">
        <RouterLink :to="{ name: 'admin-overview' }" class="adm-brand" aria-label="Admin overview">
          <BrandLogo :name="brandName" :size="24" />
        </RouterLink>
        <span class="adm-env-badge">Internal</span>
        <button
          type="button"
          class="btn btn-ghost btn-icon btn-sm adm-side-close"
          aria-label="Close navigation"
          @click="drawerOpen = false"
        >
          <ChevronRight :size="16" />
        </button>
      </div>

      <nav class="adm-nav">
        <p class="adm-nav-label">Operations</p>
        <RouterLink
          v-for="item in operations"
          :key="item.name"
          :to="{ name: item.name }"
          class="adm-nav-link"
          :class="{ 'is-active': isActive(item.name) }"
          :aria-current="isActive(item.name) ? 'page' : undefined"
          @click="drawerOpen = false"
        >
          <component :is="item.icon" :size="15" />
          <span class="adm-nav-text">{{ item.label }}</span>
          <span v-if="item.name === 'admin-queue' && queueCount > 0" class="adm-nav-count">{{ queueCount }}</span>
        </RouterLink>

        <template v-if="isAdmin">
          <p class="adm-nav-label">Administration</p>
          <RouterLink
            v-for="item in administration"
            :key="item.name"
            :to="{ name: item.name }"
            class="adm-nav-link"
            :class="{ 'is-active': isActive(item.name) }"
            :aria-current="isActive(item.name) ? 'page' : undefined"
            @click="drawerOpen = false"
          >
            <component :is="item.icon" :size="15" />
            <span class="adm-nav-text">{{ item.label }}</span>
          </RouterLink>
        </template>
      </nav>

      <div class="adm-side-foot">
        <p class="adm-side-note"><Lock :size="11" /> Private deployment</p>
        <p v-if="version" class="mono adm-side-version">v{{ version }}</p>
      </div>
    </aside>

    <header class="adm-topbar">
      <div class="adm-topbar-left">
        <button
          type="button"
          class="btn btn-ghost btn-icon btn-sm adm-menu-btn"
          aria-label="Open navigation"
          @click="drawerOpen = true"
        >
          <Menu :size="18" />
        </button>
        <nav class="adm-crumb" aria-label="Breadcrumb">
          <span class="adm-crumb-section">{{ sectionLabel }}</span>
          <ChevronRight :size="12" class="adm-crumb-sep" />
          <strong class="adm-crumb-title">{{ title }}</strong>
        </nav>
      </div>

      <div class="adm-topbar-right">
        <span class="adm-conn" :class="`is-${connectionClass}`" :title="connectionTitle" role="status">
          <span class="adm-conn-dot" aria-hidden="true" />
          <span class="adm-conn-label">{{ connectionLabel }}</span>
        </span>
        <span class="adm-topbar-sep" aria-hidden="true" />
        <SoundToggle />
        <button
          type="button"
          class="btn btn-ghost btn-icon btn-sm"
          :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
          :title="isDark ? 'Light theme' : 'Dark theme'"
          @click="theme.toggle()"
        >
          <Sun v-if="isDark" :size="15" />
          <Moon v-else :size="15" />
        </button>
        <span class="adm-topbar-sep" aria-hidden="true" />
        <div class="adm-user" :title="`${userName} · ${userRole}`">
          <span class="adm-user-avatar" aria-hidden="true">{{ initials(userName) }}</span>
          <span class="adm-user-copy">
            <span class="adm-user-name">{{ userName }}</span>
            <span class="adm-user-role">{{ userRole }}</span>
          </span>
        </div>
        <button
          type="button"
          class="btn btn-ghost btn-icon btn-sm"
          aria-label="Sign out"
          title="Sign out"
          :disabled="signingOut"
          @click="signOut"
        >
          <Loader2 v-if="signingOut" :size="15" class="adm-spin" />
          <LogOut v-else :size="15" />
        </button>
      </div>
    </header>

    <main id="adm-content" class="adm-main" tabindex="-1">
      <RouterView />
    </main>

    <span class="sr-only" aria-live="polite">{{ connectionAnnouncement }}</span>
  </div>
</template>
