<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { monitorApi } from '@/api'
import type { Monitor, MonitorCheck, MonitorPayload, ProbeResult } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const rows = ref<Monitor[]>([])
const overview = ref({ total: 0, ok: 0, fail: 0, pending: 0, avg_latency_ms: 0 })

const drawerOpen = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const probing = ref(false)
const probeResults = ref<ProbeResult[]>([])
const probeSuggested = ref<string[]>([])

const historyOpen = ref(false)
const historyRows = ref<MonitorCheck[]>([])
const historyTitle = ref('')

const blank = (): MonitorPayload => ({
  name: '',
  url: '',
  health_path: '/',
  method: 'GET',
  expect_status: 200,
  keyword: '',
  interval_minutes: 5,
  timeout: 10,
  enabled: true,
  alert_enabled: true,
})
const form = reactive<MonitorPayload>(blank())

const kpis = computed(() => [
  { label: '监控目标', value: overview.value.total, meta: '独立巡检周期', light: 'is-cyan' },
  { label: '运行正常', value: overview.value.ok, meta: '最近一次检查通过', light: '' },
  { label: '服务异常', value: overview.value.fail, meta: '已触发企业微信告警', light: overview.value.fail ? 'is-red' : '' },
  {
    label: '平均响应',
    value: overview.value.avg_latency_ms,
    unit: 'ms',
    meta: `待首次检查 ${overview.value.pending} 个`,
    light: 'is-violet',
  },
])

function statusOf(item: Monitor) {
  if (item.last_status === 'ok') return { text: '正常', cls: '', light: '' }
  if (item.last_status === 'fail') return { text: '异常', cls: 'tag-danger', light: 'is-red' }
  return { text: '待检查', cls: 'tag-muted', light: 'is-amber' }
}

async function load() {
  loading.value = true
  try {
    const data = await monitorApi.overview()
    overview.value = {
      total: data.total,
      ok: data.ok,
      fail: data.fail,
      pending: data.pending,
      avg_latency_ms: data.avg_latency_ms,
    }
    rows.value = data.monitors
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, blank())
  probeResults.value = []
  probeSuggested.value = []
  drawerOpen.value = true
}

function openEdit(row: Monitor) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    url: row.url,
    health_path: row.health_path,
    method: row.method,
    expect_status: row.expect_status,
    keyword: row.keyword,
    interval_minutes: row.interval_minutes,
    timeout: row.timeout,
    enabled: row.enabled,
    alert_enabled: row.alert_enabled,
  })
  probeResults.value = []
  probeSuggested.value = []
  drawerOpen.value = true
}

async function probe() {
  if (!form.url.trim()) {
    ElMessage.warning('请先填写服务地址')
    return
  }
  probing.value = true
  try {
    const result = await monitorApi.probe({ url: form.url.trim(), use_llm: true })
    probeResults.value = result.results
    probeSuggested.value = result.suggested
    if (result.available.length) {
      ElMessage.success(`找到 ${result.available.length} 个可用路径`)
    } else {
      ElMessage.warning('未找到可用的健康检查路径')
    }
  } catch (error) {
    ElMessage.error('探测失败')
  } finally {
    probing.value = false
  }
}

function pickPath(item: ProbeResult) {
  form.health_path = item.path
}

async function submit() {
  if (!form.name.trim() || !form.url.trim()) {
    ElMessage.warning('名称与地址为必填项')
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      await monitorApi.update(editingId.value, { ...form })
      ElMessage.success('已保存')
    } else {
      await monitorApi.create({ ...form })
      ElMessage.success('已创建')
    }
    drawerOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function openHistory(row: Monitor) {
  historyTitle.value = row.name
  historyRows.value = await monitorApi.history(row.id)
  historyOpen.value = true
}

async function remove(row: Monitor) {
  await ElMessageBox.confirm(`确认删除监控目标「${row.name}」？`, '删除监控', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await monitorApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

let timer: number | undefined

function startAutoRefresh() {
  if (timer) return
  timer = window.setInterval(() => {
    load()
  }, 10000)
}

function stopAutoRefresh() {
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
}

onMounted(async () => {
  await load()
  startAutoRefresh()
})

onBeforeUnmount(stopAutoRefresh)
</script>

<template>
  <div>
    <div class="stat-grid">
      <div v-for="item in kpis" :key="item.label" class="stat-tile">
        <div class="stat-head">
          <span class="status-light" :class="item.light" />
          <span class="stat-label">{{ item.label }}</span>
        </div>
        <div class="stat-value">
          {{ item.value }}<span v-if="item.unit" class="stat-unit">{{ item.unit }}</span>
        </div>
        <div class="stat-meta">{{ item.meta }}</div>
      </div>
    </div>

    <div class="toolbar">
      <div class="toolbar-filters" />
      <div class="toolbar-actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建监控</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column label="名称" min-width="170">
          <template #default="{ row }">
            <div class="table-subject">{{ row.name }}</div>
            <div class="table-subject is-muted mono">
              {{ row.url }}{{ row.health_path && row.health_path !== '/' ? row.health_path : '' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <span class="tag" :class="statusOf(row).cls">
              <span class="status-light" :class="statusOf(row).light" />
              {{ statusOf(row).text }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态码" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.last_status ? (row.last_status === 'ok' ? row.expect_status : '异常') : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="响应" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.last_latency_ms ? `${row.last_latency_ms} ms` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="可用率" width="100">
          <template #default="{ row }">
            <span class="num">{{ row.total_checks ? `${row.uptime}%` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近检查" width="160">
          <template #default="{ row }">
            <div class="num">{{ formatDateTime(row.last_check_at) }}</div>
            <div v-if="row.last_error" class="table-subject is-muted">{{ row.last_error }}</div>
          </template>
        </el-table-column>
        <el-table-column label="下次检查" width="150">
          <template #default="{ row }">
            <span class="num">{{ row.next_check_at ? formatDateTime(row.next_check_at) : '已停用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="告警" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.alert_enabled" type="success" effect="plain" size="small">开</el-tag>
            <el-tag v-else type="info" effect="plain" size="small">关</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openHistory(row)">历史</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>
    </section>

    <el-drawer v-model="drawerOpen" :title="editingId ? '编辑监控' : '新建监控'" size="560px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="名称" class="span-2">
            <el-input v-model="form.name" placeholder="如：短临预警系统" />
          </el-form-item>
          <el-form-item label="服务地址" class="span-2">
            <el-input v-model="form.url" placeholder="http://10.88.192.10:3000 或 https://domain.com" />
          </el-form-item>
          <el-form-item label="健康检查路径" class="span-2">
            <div style="display: flex; gap: 8px">
              <el-input v-model="form.health_path" placeholder="/health" />
              <el-button :loading="probing" @click="probe">自动探测</el-button>
            </div>
          </el-form-item>
          <el-form-item v-if="probeResults.length" label="探测结果" class="span-2">
            <div class="probe-list">
              <div v-if="probeSuggested.length" class="probe-suggest">
                模型推测：<span v-for="item in probeSuggested" :key="item" class="probe-chip">{{ item }}</span>
              </div>
              <div
                v-for="item in probeResults.slice(0, 12)"
                :key="item.path"
                class="probe-item"
                :class="{ 'is-ok': item.ok }"
                @click="pickPath(item)"
              >
                <span class="status-light" :class="item.ok ? '' : 'is-red'" />
                <span class="probe-path mono">{{ item.path }}</span>
                <span class="probe-meta num">{{ item.status ?? '连接失败' }} · {{ item.latency_ms }}ms</span>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="请求方法">
            <el-select v-model="form.method" style="width: 100%">
              <el-option label="GET" value="GET" />
              <el-option label="HEAD" value="HEAD" />
            </el-select>
          </el-form-item>
          <el-form-item label="期望状态码">
            <el-input-number v-model="form.expect_status" :min="100" :max="599" style="width: 100%" />
          </el-form-item>
          <el-form-item label="响应关键词" class="span-2">
            <el-input v-model="form.keyword" placeholder="选填，响应需包含该关键词才算正常" />
          </el-form-item>
          <el-form-item label="检查间隔（分钟）">
            <el-input-number v-model="form.interval_minutes" :min="1" :max="1440" style="width: 100%" />
          </el-form-item>
          <el-form-item label="超时（秒）">
            <el-input-number v-model="form.timeout" :min="1" :max="120" style="width: 100%" />
          </el-form-item>
          <el-form-item label="异常时通知企业微信">
            <el-switch v-model="form.alert_enabled" />
          </el-form-item>
          <el-form-item label="启用巡检">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </div>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="drawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-drawer>

    <el-dialog v-model="historyOpen" :title="`检查历史 · ${historyTitle}`" width="640px">
      <el-table :data="historyRows" style="width: 100%" max-height="420">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            <span class="num">{{ formatDateTime(row.checked_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <span class="tag" :class="row.status === 'ok' ? 'tag-success' : 'tag-danger'">
              {{ row.status === 'ok' ? '正常' : '异常' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态码" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.status_code || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="响应" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.latency_ms }} ms</span>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="200">
          <template #default="{ row }">
            <span class="table-subject is-muted">{{ row.error || '—' }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped>
.probe-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--hud-border-faint);
  border-radius: 2px;
  padding: 8px;
}

.probe-suggest {
  font-size: var(--hud-body-sm);
  color: var(--hud-text-dim);
  margin-bottom: 6px;
}

.probe-chip {
  display: inline-block;
  margin-right: 6px;
  color: var(--hud-violet);
  font-family: var(--hud-font);
}

.probe-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 2px;
  cursor: pointer;
  font-size: var(--hud-body-sm);
}

.probe-item:hover {
  background: rgba(6, 182, 212, 0.1);
}

.probe-item.is-ok {
  color: var(--hud-text);
}

.probe-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.probe-meta {
  color: var(--hud-text-mute);
}
</style>