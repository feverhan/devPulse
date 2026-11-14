<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const pageTitle = computed(() => (route.meta.title as string) ?? '概览')
const isWorkspace = computed(() => route.name === 'dashboard')

async function handleLogout() {
  await auth.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <router-link class="topbar-brand" :to="{ name: 'dashboard' }">
        <span class="brand-mark">DP</span>
        <span class="brand-text">
          研发脉冲
          <em class="brand-sub">DEV PULSE</em>
        </span>
      </router-link>

      <div class="topbar-crumb">
        <router-link v-if="!isWorkspace" class="crumb-back" :to="{ name: 'dashboard' }">
          工作台
        </router-link>
        <span v-if="!isWorkspace" class="crumb-sep">/</span>
        <span class="crumb-current">{{ isWorkspace ? '工作台' : pageTitle }}</span>
      </div>

      <div class="topbar-right">
        <span class="status-light" />
        <span class="topbar-state">ONLINE</span>
        <el-button
          text
          :icon="Setting"
          aria-label="设置"
          :class="{ 'is-current': route.name === 'settings' }"
          @click="router.push({ name: 'settings' })"
        />
        <button v-if="auth.passwordRequired" class="sidebar-logout" type="button" @click="handleLogout">
          退出
        </button>
      </div>
    </header>

    <div class="app-main">
      <main class="app-body">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 54px;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 0 18px;
  background: rgba(2, 6, 23, 0.88);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--hud-border-faint);
}

.topbar::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--hud-cyan), transparent);
  opacity: 0.35;
}

.topbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  flex: 0 0 auto;
}

.topbar-crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  letter-spacing: 0.1em;
  min-width: 0;
}

.crumb-back {
  color: var(--hud-text-mute);
  text-decoration: none;
  transition: color 0.15s ease;
}

.crumb-back:hover {
  color: var(--hud-bright);
  text-shadow: var(--hud-text-glow);
}

.crumb-sep {
  color: var(--hud-text-mute);
}

.crumb-current {
  color: var(--hud-bright);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  text-shadow: var(--hud-text-glow);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.topbar-state {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--hud-text-dim);
}

.sidebar-logout {
  background: none;
  border: none;
  color: var(--hud-text-mute);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  font-family: var(--hud-font);
  padding: 0;
}

.sidebar-logout:hover {
  color: var(--hud-bright);
}

.app-main {
  flex: 1;
  min-width: 0;
}

.app-body {
  padding: 16px;
  max-width: var(--hud-page-max);
  width: 100%;
  margin: 0 auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.14s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .topbar {
    gap: 10px;
    padding: 0 12px;
  }

  .topbar-state {
    display: none;
  }
}
</style>