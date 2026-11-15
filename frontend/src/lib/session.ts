import { reactive } from 'vue'
import { get, post } from '@/lib/api'
import type { AdminUser, ApiKey, SessionResponse, SiteConfig, User } from '@/types/api'

const state = reactive<{
  user: User | null
  admin: (AdminUser & { role: 'admin' | 'operator' }) | null
  site: SiteConfig | null
  loaded: boolean
}>({
  user: null,
  admin: null,
  site: null,
  loaded: false,
})

let loading: Promise<void> | null = null

const fallbackSite: SiteConfig = {
  site_name: 'Noema',
  tagline: 'Typed decisions for software that needs an answer.',
  description:
    'Calibrated yes/no probabilities, bounded choices and rubric scores over one shared context. One endpoint, no output tokens.',
  announcement: '',
  registration_enabled: true,
  support_email: 'support@noema.dev',
  sound_default: true,
  show_register_cta: true,
  version: '0.1.0',
}

async function fetchSite(): Promise<SiteConfig> {
  try {
    const site = await get<SiteConfig>('/api/site')
    state.site = site
    return site
  } catch {
    state.site = fallbackSite
    return fallbackSite
  }
}

async function fetchSession(): Promise<void> {
  try {
    const session = await get<SessionResponse>('/api/auth/session')
    state.user = session.user
    state.admin = session.admin as (AdminUser & { role: 'admin' | 'operator' }) | null
  } catch {
    state.user = null
    state.admin = null
  }
}

export function useSession() {
  return {
    state,
    async ensure(force = false): Promise<void> {
      if (state.loaded && !force) return
      if (loading) return loading
      loading = (async () => {
        await Promise.all([fetchSite(), fetchSession()])
        state.loaded = true
      })()
      try {
        await loading
      } finally {
        loading = null
      }
    },
    async refreshSite(): Promise<void> {
      await fetchSite()
    },
    async login(email: string, password: string): Promise<User> {
      const result = await post<{ user: User }>('/api/auth/login', { email, password })
      state.user = result.user
      return result.user
    },
    async register(email: string, name: string, password: string): Promise<User> {
      const result = await post<{ user: User }>('/api/auth/register', { email, name, password })
      state.user = result.user
      return result.user
    },
    async logout(): Promise<void> {
      try {
        await post('/api/auth/logout')
      } finally {
        state.user = null
      }
    },
    async adminLogin(email: string, password: string): Promise<AdminUser> {
      const result = await post<{ admin: AdminUser }>('/api/admin/auth/login', { email, password })
      state.admin = result.admin as AdminUser & { role: 'admin' | 'operator' }
      return result.admin
    },
    async adminLogout(): Promise<void> {
      try {
        await post('/api/admin/auth/logout')
      } finally {
        state.admin = null
      }
    },
    async refreshAdmin(): Promise<AdminUser | null> {
      const result = await get<{ admin: AdminUser | null }>('/api/admin/auth/session')
      state.admin = result.admin as (AdminUser & { role: 'admin' | 'operator' }) | null
      return state.admin
    },
    async refreshUser(): Promise<User | null> {
      try {
        const result = await get<{ user: User }>('/api/account')
        state.user = result.user
      } catch {
        state.user = null
      }
      return state.user
    },
    async reloadKeys(): Promise<ApiKey[]> {
      const result = await get<{ keys: ApiKey[] }>('/api/keys')
      return result.keys
    },
  }
}
