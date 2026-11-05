import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    alias: ['/dashboard'],
    name: 'Dashboard',
    component: () => import('./views/DashboardView.vue'),
  },
  {
    path: '/secrets',
    name: 'Secrets',
    component: () => import('./views/SecretsView.vue'),
  },
  {
    path: '/secrets/:name',
    name: 'SecretDetail',
    component: () => import('./views/SecretDetailView.vue'),
    props: true,
  },
  {
    path: '/bookmarks',
    name: 'Bookmarks',
    component: () => import('./views/BookmarksView.vue'),
  },
  {
    path: '/shared',
    name: 'SharedWithMe',
    component: () => import('./views/SharedWithMeView.vue'),
  },
  {
    path: '/shares',
    name: 'ManageShares',
    component: () => import('./views/ManageSharesView.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/shared/:token',
    name: 'SharedLink',
    component: () => import('./views/SharedLinkView.vue'),
    meta: { public: true },
  },

  {
    path: '/audit',
    name: 'AuditLog',
    component: () => import('./views/AuditLogView.vue'),
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory('/vault'),
  routes,
})

router.beforeEach((to, from, next) => {
  if (to.meta.requiresAdmin) {
    const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name || ''
    const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
    const isAdmin = user === 'Administrator' || roles.includes('Vault Admin')

    if (!isAdmin) {
      return next({ name: 'SharedWithMe' })
    }
  }
  next()
})

export default router
