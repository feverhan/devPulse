<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { setupApi } from '@/api'
import { useSetup } from '@/stores/setup'

const router = useRouter()
const setupStore = useSetup()

const loading = ref(true)
const saving = ref('')
const showMysql = ref(false)
const databaseUrl = ref('')
const llm = ref({ base_url: '', api_key: '', model: '', temperature: 0.3 })
const password = ref('')

const status = computed(() => setupStore.status)
const stepMap = computed(() => {
  const map: Record<string, { done: boolean; detail: string }> = {}
  for (const step of status.value?.steps ?? []) {
    map[step.key] = { done: step.done, detail: step.detail }
  }
  return map
})

async function load() {
  loading.value = true
  try {
    await setupStore.refresh()
    const current = setupStore.status
    if (current) {
      llm.value.base_url = current.database.driver === 'sqlite' ? '' : ''
      showMysql.value = current.database.driver === 'mysql'
      databaseUrl.value = current.database.driver === 'mysql' ? current.database.target : ''
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
  } catch (error) {
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
  } catch (error) {
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
  } catch (error) {
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
      </div>

      <section class="setup-step">
        <div class="setup-step-head">
          <span class="status-light" :class="stepMap.database?.done ? '' : 'is-amber'" />
          <span class="setup-step-title">数据库</span>
          <span class="setup-step-detail">{{ stepMap.database?.detail }}</span>
        </div>
        <div class="setup-step-body">
          <div class="mono setup-target">{{ status?.database.target }}</div>
          <div class="setup-row">
            <el-button size="small" @click="showMysql = !showMysql">
              {{ showMysql ? '使用本地 SQLite' : '改用 MySQL' }}
            </el-button>
            <el-button
              v-if="status?.database.driver === 'mysql'"
              size="small"
              type="primary"
              :loading="saving === 'migrate'"
              @click="migrateToSqlite"
            >
              把数据迁移到 SQLite
            </el-button>
            <el-button
              v-if="status?.database.source === 'file'"
              size="small"
              :loading="saving === 'reset-source'"
              @click="resetSource"
            >
              改回环境变量配置
            </el-button>
          </div>
          <div v-if="showMysql" class="setup-row">
            <el-input
              v-model="databaseUrl"
              placeholder="mysql+pymysql://user:password@host:3306/daylife?charset=utf8mb4"
              style="flex: 1"
            />
            <el-button
              type="primary"
              :loading="saving === 'database'"
              @click="saveDatabase"
            >
              连接并切换
            </el-button>
          </div>
        </div>
      </section>

      <section class="setup-step">
        <div class="setup-step-head">
          <span class="status-light" :class="stepMap.llm?.done ? '' : 'is-amber'" />
          <span class="setup-step-title">大模型</span>
          <span class="setup-step-detail">{{ stepMap.llm?.detail }}</span>
        </div>
        <div class="setup-step-body">
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
        </div>
      </section>

      <section class="setup-step">
        <div class="setup-step-head">
          <span class="status-light" :class="stepMap.password?.done ? '' : 'is-amber'" />
          <span class="setup-step-title">访问密码</span>
          <span class="setup-step-detail">{{ stepMap.password?.detail }}</span>
        </div>
        <div class="setup-step-body">
          <div class="setup-row">
            <el-input v-model="password" type="password" show-password placeholder="设置后访问需要输入该密码" />
            <el-button :loading="saving === 'password'" @click="savePassword">设置</el-button>
          </div>
        </div>
      </section>

      <section class="setup-step">
        <div class="setup-step-head">
          <span class="status-light" :class="stepMap.repo?.done ? '' : 'is-amber'" />
          <span class="setup-step-title">代码仓库</span>
          <span class="setup-step-detail">{{ stepMap.repo?.detail }}</span>
        </div>
      </section>

      <div class="setup-foot">
        <el-button @click="finish">跳过并进入工作台</el-button>
        <el-button type="primary" :loading="saving === 'complete'" @click="finish">
          完成并进入工作台
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
  max-width: 760px;
  background: var(--hud-panel);
  backdrop-filter: blur(20px);
  border: 1px solid var(--hud-border);
  border-radius: var(--hud-radius-card);
  box-shadow: var(--hud-glow-active);
  padding: 24px 26px;
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
  margin-bottom: 20px;
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

.setup-step {
  border-top: 1px solid var(--hud-border-faint);
  padding: 14px 0;
}

.setup-step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.setup-step-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--hud-bright);
}

.setup-step-detail {
  margin-left: auto;
  font-size: var(--hud-body-sm);
  color: var(--hud-text-dim);
}

.setup-step-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.setup-target {
  color: var(--hud-text-mute);
  word-break: break-all;
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
  border-top: 1px solid var(--hud-border-faint);
}
</style>