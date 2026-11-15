import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from '@/lib/session'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, _from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      component: () => import('@/public/PublicLayout.vue'),
      children: [
        { path: '', name: 'home', component: () => import('@/public/HomePage.vue'), meta: { title: 'Decisions, not tokens' } },
        { path: 'models', name: 'models', component: () => import('@/public/ModelsPage.vue'), meta: { title: 'Models' } },
        { path: 'docs', name: 'docs', component: () => import('@/public/DocsPage.vue'), meta: { title: 'Documentation' } },
        { path: 'login', name: 'login', component: () => import('@/public/LoginPage.vue'), meta: { title: 'Sign in' } },
        { path: 'register', name: 'register', component: () => import('@/public/RegisterPage.vue'), meta: { title: 'Create account' } },
        { path: ':pathMatch(.*)*', name: 'not-found', component: () => import('@/public/NotFoundPage.vue'), meta: { title: 'Not found' } },
      ],
    },
    {
      path: '/console',
      component: () => import('@/console/ConsoleLayout.vue'),
      meta: { requiresUser: true },
      children: [
        { path: '', name: 'console', component: () => import('@/console/ConsoleOverview.vue'), meta: { title: 'Console' } },
        { path: 'playground', name: 'playground', component: () => import('@/console/PlaygroundPage.vue'), meta: { title: 'Playground' } },
        { path: 'keys', name: 'keys', component: () => import('@/console/KeysPage.vue'), meta: { title: 'API keys' } },
        { path: 'usage', name: 'usage', component: () => import('@/console/UsagePage.vue'), meta: { title: 'Usage' } },
        { path: 'account', name: 'account', component: () => import('@/console/AccountPage.vue'), meta: { title: 'Account' } },
      ],
    },
    {
      path: '/admin/login',
      name: 'admin-login',
      component: () => import('@/admin/AdminLoginPage.vue'),
      meta: { title: 'Operator sign in' },
    },
    {
      path: '/admin',
      component: () => import('@/admin/AdminLayout.vue'),
      meta: { requiresAdmin: true },
      children: [
        { path: '', name: 'admin-overview', component: () => import('@/admin/AdminOverviewPage.vue'), meta: { title: 'Overview' } },
        { path: 'queue/:id?', name: 'admin-queue', component: () => import('@/admin/AdminQueuePage.vue'), meta: { title: 'Decision queue' } },
        { path: 'history', name: 'admin-history', component: () => import('@/admin/AdminHistoryPage.vue'), meta: { title: 'History' } },
        { path: 'users', name: 'admin-users', component: () => import('@/admin/AdminUsersPage.vue'), meta: { title: 'Users', role: 'admin' } },
        { path: 'operators', name: 'admin-operators', component: () => import('@/admin/AdminOperatorsPage.vue'), meta: { title: 'Operators', role: 'admin' } },
        { path: 'models', name: 'admin-models', component: () => import('@/admin/AdminModelsPage.vue'), meta: { title: 'Models & routing', role: 'admin' } },
        { path: 'settings', name: 'admin-settings', component: () => import('@/admin/AdminSettingsPage.vue'), meta: { title: 'Settings', role: 'admin' } },
        { path: 'audit', name: 'admin-audit', component: () => import('@/admin/AdminAuditPage.vue'), meta: { title: 'Audit log', role: 'admin' } },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const session = useSession()
  await session.ensure()
  const { user, admin, site } = session.state
  if (to.meta.requiresUser && !user) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !admin) {
    return { name: 'admin-login', query: { next: to.fullPath } }
  }
  if (to.meta.role === 'admin' && admin?.role !== 'admin') {
    return { name: 'admin-overview' }
  }
  if (to.name === 'login' && user) return { name: 'console' }
  if (to.name === 'admin-login' && admin) return { name: 'admin-overview' }
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · ${site?.site_name || 'Noema'}` : site?.site_name || 'Noema'
  return true
})

export default router
