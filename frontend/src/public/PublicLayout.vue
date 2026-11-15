<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { ArrowRight, Menu, Moon, Sun, X } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import { useSession } from '@/lib/session'
import { useTheme } from '@/lib/theme'
import '@/styles/public.css'

const route = useRoute()
const session = useSession()
const { theme, toggle } = useTheme()

const site = computed(() => session.state.site)
const user = computed(() => session.state.user)
const showRegister = computed(() => Boolean(site.value?.registration_enabled && site.value?.show_register_cta))
const menuOpen = ref(false)
const announcementDismissed = ref(false)
const year = new Date().getFullYear()

const nav = [
  { to: '/', label: 'Home' },
  { to: '/models', label: 'Models' },
  { to: '/docs', label: 'Docs' },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

function closeMenu() {
  menuOpen.value = false
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') menuOpen.value = false
}

watch(
  () => route.fullPath,
  () => closeMenu(),
)

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="pub-shell">
    <a class="pub-skip" href="#main">Skip to content</a>

    <div v-if="site?.announcement && !announcementDismissed" class="pub-announcement">
      <div class="container pub-announcement-inner">
        <span class="pub-announcement-tag mono">Notice</span>
        <p class="pub-announcement-text">{{ site.announcement }}</p>
        <button
          type="button"
          class="pub-announcement-close"
          aria-label="Dismiss announcement"
          @click="announcementDismissed = true"
        >
          <X :size="14" />
        </button>
      </div>
    </div>

    <header class="pub-header">
      <div class="container pub-header-inner">
        <RouterLink to="/" class="pub-brand-link" :aria-label="`${site?.site_name || 'Noema'} home`">
          <BrandLogo :name="site?.site_name || 'Noema'" />
        </RouterLink>

        <nav class="pub-nav" aria-label="Primary">
          <RouterLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="pub-nav-link"
            :class="{ 'is-active': isActive(item.to) }"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="pub-actions">
          <button
            type="button"
            class="btn btn-ghost btn-icon pub-theme-toggle"
            :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
            :title="theme === 'dark' ? 'Light theme' : 'Dark theme'"
            @click="toggle"
          >
            <Sun v-if="theme === 'dark'" :size="17" />
            <Moon v-else :size="17" />
          </button>

          <template v-if="user">
            <RouterLink to="/console" class="btn btn-sm pub-cta-btn">
              Console
              <ArrowRight :size="14" />
            </RouterLink>
          </template>
          <template v-else>
            <RouterLink to="/login" class="btn btn-ghost btn-sm pub-signin">Sign in</RouterLink>
            <RouterLink v-if="showRegister" to="/register" class="btn btn-primary btn-sm pub-cta-btn">
              Get started
            </RouterLink>
          </template>

          <button
            type="button"
            class="btn btn-ghost btn-icon pub-menu-toggle"
            :aria-label="menuOpen ? 'Close menu' : 'Open menu'"
            :aria-expanded="menuOpen"
            aria-controls="pub-mobile-menu"
            @click="menuOpen = !menuOpen"
          >
            <X v-if="menuOpen" :size="18" />
            <Menu v-else :size="18" />
          </button>
        </div>
      </div>

      <Transition name="pub-menu">
        <div v-if="menuOpen" id="pub-mobile-menu" class="pub-mobile-menu">
          <div class="container pub-mobile-inner">
            <nav class="pub-mobile-nav" aria-label="Mobile">
              <RouterLink
                v-for="item in nav"
                :key="item.to"
                :to="item.to"
                class="pub-mobile-link"
                :class="{ 'is-active': isActive(item.to) }"
              >
                <span>{{ item.label }}</span>
                <ArrowRight :size="15" />
              </RouterLink>
            </nav>
            <div class="pub-mobile-auth">
              <template v-if="user">
                <RouterLink to="/console" class="btn btn-primary" @click="closeMenu">Open console</RouterLink>
              </template>
              <template v-else>
                <RouterLink to="/login" class="btn" @click="closeMenu">Sign in</RouterLink>
                <RouterLink
                  v-if="showRegister"
                  to="/register"
                  class="btn btn-primary"
                  @click="closeMenu"
                >
                  Get started
                </RouterLink>
              </template>
            </div>
          </div>
        </div>
      </Transition>
    </header>

    <main id="main" class="pub-main">
      <RouterView v-slot="{ Component }">
        <Transition name="pub-page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

    <footer class="pub-footer">
      <div class="container">
        <div class="pub-footer-top">
          <div class="pub-footer-brand">
            <BrandLogo :name="site?.site_name || 'Noema'" :size="26" />
            <p class="pub-footer-tagline">{{ site?.tagline || 'Typed decisions for software.' }}</p>
            <p class="pub-footer-meta mono">Decision API · v{{ site?.version || '1' }}</p>
          </div>

          <div class="pub-footer-cols">
            <div class="pub-footer-col">
              <h2 class="pub-footer-heading">Product</h2>
              <RouterLink to="/models">Models</RouterLink>
              <RouterLink to="/console/playground">Playground</RouterLink>
              <RouterLink to="/console">Console</RouterLink>
              <RouterLink to="/docs">Documentation</RouterLink>
            </div>
            <div class="pub-footer-col">
              <h2 class="pub-footer-heading">Developers</h2>
              <RouterLink :to="{ path: '/docs', hash: '#quickstart' }">Quickstart</RouterLink>
              <RouterLink :to="{ path: '/docs', hash: '#system-one' }">System One</RouterLink>
              <RouterLink :to="{ path: '/docs', hash: '#gemini-decisions' }">Gemini Decisions</RouterLink>
              <RouterLink :to="{ path: '/docs', hash: '#errors' }">Errors</RouterLink>
            </div>
            <div class="pub-footer-col">
              <h2 class="pub-footer-heading">Legal</h2>
              <RouterLink :to="{ path: '/docs', hash: '#privacy' }">Privacy</RouterLink>
              <RouterLink :to="{ path: '/docs', hash: '#terms' }">Terms</RouterLink>
              <RouterLink :to="{ path: '/docs', hash: '#security' }">Security</RouterLink>
              <a :href="`mailto:${site?.support_email || 'support@noema.dev'}`">Support</a>
            </div>
          </div>
        </div>

        <div class="pub-footer-bottom">
          <p>© {{ year }} {{ site?.site_name || 'Noema' }}. All rights reserved.</p>
          <p class="mono">Typed answers · No output tokens</p>
        </div>
      </div>
    </footer>
  </div>
</template>
