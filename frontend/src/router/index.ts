import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import { pinia } from '@/stores'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/setup',
      name: 'setup',
      component: () => import('@/views/SetupView.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/DefaultLayout.vue'),
      children: [
        { path: '', redirect: { name: 'dashboard' } },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '概览' },
        },
        {
          path: 'repos',
          name: 'repos',
          component: () => import('@/views/ReposView.vue'),
          meta: { title: '仓库' },
        },
        {
          path: 'commits',
          name: 'commits',
          component: () => import('@/views/CommitsView.vue'),
          meta: { title: '提交记录' },
        },
        {
          path: 'projects',
          name: 'projects',
          component: () => import('@/views/ProjectsView.vue'),
          meta: { title: '项目' },
        },
        {
          path: 'works',
          name: 'works',
          component: () => import('@/views/WorksView.vue'),
          meta: { title: '工作记录' },
        },
        {
          path: 'monitors',
          name: 'monitors',
          component: () => import('@/views/MonitorsView.vue'),
          meta: { title: '服务监控' },
        },
        {
          path: 'reviews',
          name: 'reviews',
          component: () => import('@/views/ReviewsView.vue'),
          meta: { title: '代码审查' },
        },
        {
          path: 'reports',
          name: 'reports',
          component: () => import('@/views/ReportsView.vue'),
          meta: { title: '报告' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { title: '设置' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: { name: 'dashboard' } },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  if (!auth.checked) {
    await auth.check()
  }
  if (to.meta.public) {
    return true
  }
  if (auth.passwordRequired && !auth.authenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  const setup = useSetupStore(pinia)
  const state = await setup.load()
  if (state) {
    if (!state.initialized && to.name !== 'setup') {
      return { name: 'setup' }
    }
    if (state.initialized && to.name === 'setup') {
      return { name: 'dashboard' }
    }
  }
  return true
})

export default router