<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Boxes,
  ChevronDown,
  FlaskConical,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Sun,
  UserRound,
  X,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import BrandLogo from '@/components/BrandLogo.vue'
import { get } from '@/lib/api'
import { useSession } from '@/lib/session'
import { useTheme } from '@/lib/theme'
import { toast } from '@/lib/toast'
import { reportError } from '@/public/support'
import '@/styles/public.css'

interface ServiceStatus {
  ok: boolean
  service: string
  version: string
  models: number
}

const route = useRoute()
const router = useRouter()
const session = useSession()
const { theme, toggle } = useTheme()

const user = computed(() => session.state.user)
const site = computed(() => session.state.site)
const initial = computed(() => (user.value?.name?.trim()?.[0] || user.value?.email?.[0] || '?').toUpperCase())
const pageTitle = computed(() => (route.meta.title as string | undefined) || 'Console')

const drawerOpen = ref(false)
const userMenuOpen = ref(false)
const userMenuRef = ref<HTMLElement | null>(null)
const status = ref<ServiceStatus | null>(null)
const statusFailed = ref(false)

interface NavItem {
  to: string
  label: string
  icon: Component
  exact?: boolean
}

const navItems: NavItem[] = [
  { to: '/console', label: 'Overview', icon: LayoutDashboard, exact: true },
  { to: '/console/playground', label: 'Playground', icon: FlaskConical },
  { to: '/console/keys', label: 'API keys', icon: KeyRound },
  { to: '/console/usage', label: 'Usage', icon: BarChart3 },
  { to: '/console/account', label: 'Account', icon: UserRound },
]

const referenceItems: NavItem[] = [
  { to: '/docs', label: 'Documentation', icon: BookOpen },
  { to: '/models', label: 'Model catalog', icon: Boxes },
]

function isActive(item: NavItem): boolean {
  if (item.exact) return route.path === item.to
  return route.path === item.to || route.path.startsWith(`${item.to}/`)
}

const statusLabel = computed(() => {
  if (statusFailed.value) return 'unreachable'
  if (!status.value) return 'checking'
  return status.value.ok ? 'operational' : 'degraded'
})

const statusTone = computed(() => {
  if (statusFailed.value) return 'danger'
  if (!status.value) return 'pending'
  return status.value.ok ? 'ok' : 'warn'
})

function closeOverlays() {
  drawerOpen.value = false
  userMenuOpen.value = false
}

async function signOut() {
  userMenuOpen.value = false
  try {
    await session.logout()
    toast('Signed out', 'success')
  } catch (error) {
    reportError(error, 'Could not sign out.')
  } finally {
    await router.replace({ name: 'login' })
  }
}

function onDocumentPointer(event: MouseEvent) {
  if (!userMenuOpen.value) return
  const target = event.target
  if (userMenuRef.value && target instanceof Node && !userMenuRef.value.contains(target)) {
    userMenuOpen.value = false
  }
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') closeOverlays()
}

watch(
  () => route.fullPath,
  () => closeOverlays(),
)

watch(drawerOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})

onMounted(async () => {
  document.addEventListener('mousedown', onDocumentPointer)
  window.addEventListener('keydown', onKey)
  try {
    status.value = await get<ServiceStatus>('/api/status')
  } catch {
    // The sidebar indicator is ambient; it reports unreachable instead of a toast.
    statusFailed.value = true
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentPointer)
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="console-shell">
    <aside class="console-sidebar" :class="{ 'is-open': drawerOpen }" aria-label="Console navigation">
      <div class="console-sidebar-head">
        <RouterLink to="/" class="console-brand">
          <BrandLogo :name="site?.site_name || 'Noema'" :size="26" />
        </RouterLink>
        <span class="badge">Console</span>
        <button
          type="button"
          class="btn btn-ghost btn-icon btn-sm console-drawer-close"
          aria-label="Close navigation"
          @click="drawerOpen = false"
        >
          <X :size="17" />
        </button>
      </div>

      <nav class="console-nav">
        <p class="console-nav-label mono">Workspace</p>
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="console-nav-link"
          :class="{ 'is-active': isActive(item) }"
          :aria-current="isActive(item) ? 'page' : undefined"
        >
          <component :is="item.icon" :size="16" />
          <span>{{ item.label }}</span>
        </RouterLink>

        <p class="console-nav-label console-nav-label-spaced mono">Reference</p>
        <RouterLink
          v-for="item in referenceItems"
          :key="item.to"
          :to="item.to"
          class="console-nav-link console-nav-link-quiet"
        >
          <component :is="item.icon" :size="16" />
          <span>{{ item.label }}</span>
          <ArrowUpRight :size="13" class="console-nav-ext" />
        </RouterLink>
      </nav>

      <div class="console-sidebar-foot">
        <div class="console-service" :class="`console-service-${statusTone}`">
          <span class="console-service-dot" aria-hidden="true" />
          <span class="console-service-label">API</span>
          <span class="console-service-value mono">{{ statusLabel }}</span>
        </div>
        <p v-if="status" class="console-sidebar-meta mono">
          {{ status.models }} model{{ status.models === 1 ? '' : 's' }} · v{{ status.version }}
        </p>
        <p v-else class="console-sidebar-meta mono">Decision API · v{{ site?.version || '1' }}</p>
      </div>
    </aside>

    <div v-if="drawerOpen" class="console-scrim" aria-hidden="true" @click="drawerOpen = false" />

    <div class="console-main">
      <header class="console-topbar">
        <div class="console-topbar-left">
          <button
            type="button"
            class="btn btn-ghost btn-icon console-menu-btn"
            aria-label="Open navigation"
            @click="drawerOpen = true"
          >
            <Menu :size="18" />
          </button>
          <div class="console-crumb">
            <span class="console-crumb-root mono">Console</span>
            <span class="console-crumb-sep" aria-hidden="true">/</span>
            <h1 class="console-crumb-title">{{ pageTitle }}</h1>
          </div>
        </div>

        <div class="console-topbar-right">
          <RouterLink to="/docs" class="btn btn-ghost btn-sm console-docs-link">
            <BookOpen :size="15" />
            <span>Docs</span>
          </RouterLink>

          <button
            type="button"
            class="btn btn-ghost btn-icon"
            :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
            :title="theme === 'dark' ? 'Light theme' : 'Dark theme'"
            @click="toggle"
          >
            <Sun v-if="theme === 'dark'" :size="17" />
            <Moon v-else :size="17" />
          </button>

          <div ref="userMenuRef" class="console-user">
            <button
              type="button"
              class="console-user-trigger"
              :aria-expanded="userMenuOpen"
              aria-haspopup="menu"
              @click="userMenuOpen = !userMenuOpen"
            >
              <span class="console-avatar" aria-hidden="true">{{ initial }}</span>
              <span class="console-user-name">{{ user?.name || user?.email }}</span>
              <ChevronDown :size="14" class="console-user-chevron" :class="{ 'is-open': userMenuOpen }" />
            </button>

            <Transition name="console-menu">
              <div v-if="userMenuOpen" class="console-user-menu" role="menu">
                <div class="console-user-meta">
                  <p class="console-user-meta-name">{{ user?.name }}</p>
                  <p class="console-user-meta-email mono">{{ user?.email }}</p>
                </div>
                <RouterLink to="/console/account" class="console-user-item" role="menuitem">
                  <UserRound :size="15" />
                  Account settings
                </RouterLink>
                <RouterLink to="/console/keys" class="console-user-item" role="menuitem">
                  <KeyRound :size="15" />
                  API keys
                </RouterLink>
                <div class="console-user-divider" />
                <button type="button" class="console-user-item console-user-signout" role="menuitem" @click="signOut">
                  <LogOut :size="15" />
                  Sign out
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </header>

      <main class="console-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>
