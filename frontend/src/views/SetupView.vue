<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Connection, CircleCheckFilled, WarningFilled, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { setupApi } from '@/api'
import { useSetup } from '@/stores/setup'

const router = useRouter()
const setupStore = useSetup()

const loading = ref(true)
const saving = ref('')
const expanded = ref<Set<string>>(new Set())
const databaseUrl = ref('')
const llm = ref({ base_url: '', api_key: '', model: '', temperature: 0.3 })
const password = ref('')

const status = computed(() => setupStore.status)
const stepMap = computed(() => {
  const map: Record<string, { title: string; done: boolean; detail: string }> = {}
  for (const step of status.value?.steps ?? []) {
    map[step.key] = { title: step.title, done: step.done, detail: step.detail }
  }
  return map
})

const stepOrder = ['database', 'llm', 'password'] as const
const doneCount = computed(() => stepOrder.filter((key) => stepMap.value[key]?.done).length)
const progressPercent = computed(() => Math.round((doneCount.value / stepOrder.length) * 100))

function toggle(key: string) {
  const next = new Set(expanded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}

async function load() {
  loading.value = true
  try {
    await setupStore.refresh()
    const current = setupStore.status
    if (current) {
      if (current.llm) {
        llm.value.base_url = current.llm.base_url || ''
        llm.value.model = current.llm.model || ''
      }
      databaseUrl.value = current.database.driver === 'mysql' && current.database.source === 'file' ? current.database.target : ''
    }
  } finally {
    loading.value = false
  }
}

async function saveDatabase() {
  saving.value = 'database'
  try {
    await setupApi.setDatabase(databaseUrl.value.trim())
    ElMessage.success('数据库已切换')
    await setupStore.refresh()
  } catch {
    ElMessage.error('切换失败')
  } finally {
    saving.value = ''
  }
}

async function migrateToSqlite() {
  saving.value = 'migrate'
  try {
    const result = await setupApi.migrate({ from_url: '', to_url: '' })
    const total = Object.values(result.migrated ?? {}).reduce((sum, value) => sum + value, 0)
    ElMessage.success(`已迁移 ${total} 条记录到本地 SQLite`)
    await setupStore.refresh()
  } catch {
    ElMessage.error('迁移失败')
  } finally {
    saving.value = ''
  }
}

async function saveLlm() {
  saving.value = 'llm'
  try {
    await setupApi.setLlm({ ...llm.value })
    ElMessage.success('大模型已配置')
    await setupStore.refresh()
  } catch {
    ElMessage.error('连接失败，请检查地址与模型名')
  } finally {
    saving.value = ''
  }
}

async function savePassword() {
  saving.value = 'password'
  try {
    await setupApi.setPassword(password.value)
    ElMessage.success('访问密码已设置')
    password.value = ''
    await setupStore.refresh()
  } catch {
    ElMessage.error('设置失败')
  } finally {
    saving.value = ''
  }
}

async function resetSource() {
  saving.value = 'reset-source'
  try {
    await setupApi.resetDatabaseSource()
    ElMessage.success('已改回环境变量配置')
    await setupStore.refresh()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    saving.value = ''
  }
}

async function finish() {
  saving.value = 'complete'
  try {
    await setupApi.complete()
    await setupStore.refresh()
    router.push({ name: 'dashboard' })
  } catch {
    ElMessage.error('操作失败')
  } finally {
    saving.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="setup-wrap" v-loading="loading">
    <div class="setup-card">
      <div class="setup-head">
        <span class="brand-mark">DP</span>
        <div class="setup-title">
          <span class="setup-name">研发脉冲</span>
          <span class="setup-sub">DEV PULSE · 初始化</span>
        </div>
        <div class="setup-progress">
          <div class="setup-progress-bar">
            <div class="setup-progress-fill" :style="{ width: progressPercent + '%' }" />
          </div>
          <span class="setup-progress-text">{{ doneCount }}/{{ stepOrder.length }}</span>
        </div>
      </div>

      <section
        v-for="key in stepOrder"
        :key="key"
        class="setup-step"
        :class="{ 'is-done': stepMap[key]?.done }"
      >
        <div class="setup-step-head" @click="toggle(key)">
          <span class="setup-step-icon">
            <el-icon v-if="stepMap[key]?.done" color="var(--hud-green)"><CircleCheckFilled /></el-icon>
            <el-icon v-else color="var(--hud-amber)"><WarningFilled /></el-icon>
          </span>
          <span class="setup-step-title">{{ stepMap[key]?.title ?? key }}</span>
          <span class="setup-step-detail">{{ stepMap[key]?.detail }}</span>
          <el-icon
            v-if="['database', 'llm', 'password'].includes(key)"
            class="setup-step-chevron"
            :class="{ 'is-open': expanded.has(key) }"
          >
            <ArrowDown />
          </el-icon>
        </div>

        <div v-if="expanded.has(key)" class="setup-step-body">
          <!-- 数据库 -->
          <template v-if="key === 'database'">
            <div class="mono setup-target">{{ status?.database.target }}</div>
            <div class="setup-row">
              <el-input
                v-model="databaseUrl"
                placeholder="留空使用本地 SQLite，或填写 mysql+pymysql://user:password@host:3306/daylife"
                style="flex: 1"
              />
              <el-button type="primary" :loading="saving === 'database'" @click="saveDatabase">
                连接
              </el-button>
            </div>
            <div v-if="status?.database.driver === 'mysql'" class="setup-row">
              <el-button size="small" :loading="saving === 'migrate'" @click="migrateToSqlite">
                迁移数据到本地 SQLite
              </el-button>
            </div>
            <el-button
              v-if="status?.database.source === 'file'"
              size="small"
              text
              :loading="saving === 'reset-source'"
              @click="resetSource"
            >
              恢复环境变量配置
            </el-button>
          </template>

          <!-- 大模型 -->
          <template v-if="key === 'llm'">
            <el-input v-model="llm.base_url" placeholder="接口地址，如 http://127.0.0.1:8000/v1" />
            <div class="setup-row">
              <el-input
                v-model="llm.api_key"
                type="password"
                show-password
                placeholder="令牌（可留空）"
                style="flex: 1 1 0; min-width: 0"
              />
              <el-input
                v-model="llm.model"
                placeholder="模型名称，如 qwen2.5:7b"
                style="flex: 1 1 0; min-width: 0"
              />
              <el-button type="primary" :icon="Connection" :loading="saving === 'llm'" @click="saveLlm">
                保存并测试
              </el-button>
            </div>
          </template>

          <!-- 访问密码 -->
          <template v-if="key === 'password'">
            <div class="setup-row">
              <el-input
                v-model="password"
                type="password"
                show-password
                placeholder="设置访问密码（留空则清除密码）"
                style="flex: 1"
              />
              <el-button :loading="saving === 'password'" @click="savePassword">设置</el-button>
            </div>
          </template>
        </div>
      </section>

      <div class="setup-foot">
        <el-button text @click="finish">跳过</el-button>
        <el-button type="primary" :loading="saving === 'complete'" @click="finish">
          完成并进入
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.setup-wrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background-color: var(--hud-deep);
  background-image:
    linear-gradient(rgba(6, 182, 212, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(6, 182, 212, 0.05) 1px, transparent 1px),
    radial-gradient(900px 520px at 50% 30%, rgba(6, 182, 212, 0.14), transparent 65%);
  background-size: 32px 32px, 32px 32px, 100% 100%;
}

.setup-card {
  width: 100%;
  max-width: 680px;
  background: var(--hud-panel);
  backdrop-filter: blur(20px);
  border: 1px solid var(--hud-border);
  border-radius: var(--hud-radius-card);
  box-shadow: var(--hud-glow-active);
  padding: 28px 30px;
  position: relative;
}

.setup-card::before {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background:
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left top / 20px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left top / 2px 20px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right top / 20px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right top / 2px 20px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left bottom / 20px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left bottom / 2px 20px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right bottom / 20px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right bottom / 2px 20px no-repeat;
}

.setup-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.setup-title {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.setup-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--hud-text);
}

.setup-sub {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.22em;
  color: var(--hud-text-mute);
}

.setup-progress {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.setup-progress-bar {
  width: 80px;
  height: 3px;
  background: var(--hud-border-faint);
  border-radius: 2px;
  overflow: hidden;
}

.setup-progress-fill {
  height: 100%;
  background: var(--hud-cyan);
  transition: width 0.4s ease;
}

.setup-progress-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--hud-text-mute);
  font-variant-numeric: tabular-nums;
}

.setup-step {
  border: 1px solid var(--hud-border-faint);
  border-radius: var(--hud-radius-btn);
  margin-bottom: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.setup-step.is-done {
  border-color: rgba(34, 197, 94, 0.2);
}

.setup-step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}

.setup-step-head:hover {
  background: rgba(6, 182, 212, 0.04);
}

.setup-step-icon {
  display: flex;
  align-items: center;
  font-size: 18px;
  flex-shrink: 0;
}

.setup-step-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--hud-text);
}

.setup-step-detail {
  margin-left: auto;
  font-size: var(--hud-body-sm);
  color: var(--hud-text-mute);
  text-align: right;
}

.setup-step-chevron {
  margin-left: 8px;
  font-size: 12px;
  color: var(--hud-text-mute);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.setup-step-chevron.is-open {
  transform: rotate(180deg);
}

.setup-step-body {
  padding: 0 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.setup-target {
  font-size: 11px;
  color: var(--hud-text-mute);
  word-break: break-all;
  padding: 6px 10px;
  background: var(--hud-panel-sunken);
  border-radius: 3px;
}

.setup-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.setup-row :deep(.el-input) {
  min-width: 0;
}

.setup-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  margin-top: 8px;
  border-top: 1px solid var(--hud-border-faint);
}
</style>
