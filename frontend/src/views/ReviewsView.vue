<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Promotion, Refresh } from '@element-plus/icons-vue'
import { repoApi, reviewApi } from '@/api'
import type { CodeReview, Repo, ReviewFinding, ReviewTask } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const running = ref(false)
const pushing = ref<number | null>(null)
const tasks = ref<ReviewTask[]>([])
const rows = ref<CodeReview[]>([])
const repos = ref<Repo[]>([])

const repoId = ref<number | null>(null)
const limit = ref(5)

const drawerOpen = ref(false)
const current = ref<CodeReview | null>(null)

let timer: number | undefined

const SEVERITY_LABEL: Record<string, string> = { high: '严重', medium: '一般', low: '轻微' }
const SEVERITY_CLASS: Record<string, string> = {
  high: 'tag-danger',
  medium: 'tag-accent',
  low: 'tag-muted',
}
const TASK_STATUS: Record<string, string> = {
  pending: '排队中',
  running: '审核中',
  done: '已完成',
  failed: '失败',
  cancelled: '已取消',
}
const TASK_STATUS_CLASS: Record<string, string> = {
  pending: 'tag-muted',
  running: 'tag-accent',
  done: 'tag-success',
  failed: 'tag-danger',
  cancelled: 'tag-muted',
}
const FINDING_STATUS: Record<string, string> = {
  pending: '待推送',
  created: '已推送',
  ignored: '已忽略',
  failed: '推送失败',
}

function taskLight(status: string): string {
  if (status === 'running') return 'is-cyan'
  if (status === 'done') return ''
  if (status === 'failed') return 'is-red'
  return 'is-violet'
}

function taskProgress(row: ReviewTask): number {
  const total = row.total || row.limit || 1
  return Math.min(100, Math.round((row.processed / total) * 100))
}

const activeTasks = computed(() =>
  tasks.value.filter((item) => item.status === 'pending' || item.status === 'running'),
)

const pendingCount = computed(() => {
  if (!current.value) return 0
  return current.value.findings.filter((item) => item.status === 'pending').length
})

async function loadTasks() {
  tasks.value = await reviewApi.listTasks()
}

async function loadReviews() {
  rows.value = await reviewApi.list({ repo_id: repoId.value })
}

async function load() {
  loading.value = true
  try {
    await Promise.all([loadTasks(), loadReviews()])
  } finally {
    loading.value = false
  }
}

function ensurePolling() {
  if (timer) return
  timer = window.setInterval(async () => {
    await loadTasks()
    if (!activeTasks.value.length) {
      await loadReviews()
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
}

async function run() {
  if (!repoId.value) {
    ElMessage.warning('请选择仓库')
    return
  }
  running.value = true
  try {
    await reviewApi.createTask({
      repo_id: repoId.value,
      limit: limit.value,
      only_new: true,
    })
    ElMessage.success('任务已创建，正在后台审核')
    await loadTasks()
    ensurePolling()
  } finally {
    running.value = false
  }
}

async function cancel(task: ReviewTask) {
  await reviewApi.cancelTask(task.id)
  ElMessage.success('已取消')
  await loadTasks()
}

async function openDetail(row: CodeReview) {
  current.value = await reviewApi.get(row.id)
  drawerOpen.value = true
}

async function pushAll() {
  if (!current.value) return
  pushing.value = current.value.id
  try {
    const result = await reviewApi.pushIssues(current.value.id)
    if (result.created) {
      ElMessage.success(`已推送 ${result.created} 个 Issue`)
    } else if (result.failed) {
      ElMessage.warning(`${result.failed} 个 Issue 推送失败`)
    } else {
      ElMessage.info('没有待推送的问题')
    }
    current.value = await reviewApi.get(current.value.id)
    await loadReviews()
  } finally {
    pushing.value = null
  }
}

async function pushOne(finding: ReviewFinding) {
  pushing.value = finding.review_id
  try {
    await reviewApi.pushIssues(finding.review_id)
    current.value = await reviewApi.get(finding.review_id)
    await loadReviews()
  } finally {
    pushing.value = null
  }
}

async function ignore(finding: ReviewFinding) {
  await reviewApi.ignoreFinding(finding.id)
  if (current.value) {
    current.value = await reviewApi.get(current.value.id)
  }
  await loadReviews()
}

async function remove(row: CodeReview) {
  await ElMessageBox.confirm(`确认删除对提交 ${row.short_sha} 的审查记录？`, '删除审查记录', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await reviewApi.remove(row.id)
  ElMessage.success('已删除')
  await loadReviews()
}

onMounted(async () => {
  repos.value = await repoApi.list()
  await load()
  if (activeTasks.value.length) ensurePolling()
})

onBeforeUnmount(stopPolling)
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <el-select v-model="repoId" placeholder="选择仓库" style="width: 200px">
          <el-option v-for="item in repos" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-input-number
          v-model="limit"
          :min="1"
          :max="50"
          controls-position="right"
          style="width: 120px"
        />
      </div>
      <div class="toolbar-actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Promotion" :loading="running" @click="run">创建审查任务</el-button>
      </div>
    </div>

    <section class="panel panel-pad" style="margin-bottom: 14px">
      <h3 class="panel-title">审查任务</h3>
      <el-table v-loading="loading" :data="tasks" style="width: 100%">
        <el-table-column label="仓库" width="160">
          <template #default="{ row }">
            <span class="tag tag-platform">{{ row.repo_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <span class="tag" :class="TASK_STATUS_CLASS[row.status] ?? 'tag-muted'">
              <span class="status-light" :class="taskLight(row.status)" />
              {{ TASK_STATUS[row.status] ?? row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="170">
          <template #default="{ row }">
            <div class="scan-bar">
              <div class="scan-bar__fill" :style="{ width: `${taskProgress(row)}%` }" />
            </div>
            <div class="scan-readout" style="margin-top: 6px">
              {{ row.processed }} / {{ row.total || row.limit }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="问题" width="80">
          <template #default="{ row }">
            <span class="num" :class="{ 'delta-plus': row.finding_count > 0 }">{{ row.finding_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="table-subject is-muted">{{ row.message || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            <span class="num">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending' || row.status === 'running'"
              link
              type="danger"
              @click="cancel(row)"
            >
              取消
            </el-button>
            <span v-else class="table-subject is-muted">—</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>
    </section>

    <section class="panel">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column label="仓库" width="150">
          <template #default="{ row }">
            <span class="tag tag-platform">{{ row.repo_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交" min-width="280">
          <template #default="{ row }">
            <div class="table-subject">{{ row.commit_subject || '—' }}</div>
            <div class="table-subject is-muted mono">{{ row.short_sha }}</div>
          </template>
        </el-table-column>
        <el-table-column label="问题" width="80">
          <template #default="{ row }">
            <span class="num" :class="{ 'delta-plus': row.finding_count > 0 }">{{ row.finding_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span
              class="tag"
              :class="row.status === 'completed' ? 'tag-success' : row.status === 'failed' ? 'tag-danger' : 'tag-muted'"
            >
              {{ row.status === 'completed' ? '已审查' : row.status === 'failed' ? '失败' : '已跳过' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="模型" width="130">
          <template #default="{ row }">
            <span class="table-subject is-muted">{{ row.model || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="审查时间" width="160">
          <template #default="{ row }">
            <span class="num">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看</el-button>
            <el-button
              link
              type="primary"
              :disabled="row.finding_count === 0"
              @click="openDetail(row)"
            >
              推送 Issue
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>
    </section>

    <el-drawer v-model="drawerOpen" :title="current?.commit_subject || '审查详情'" size="680px">
      <div v-if="current" class="review-detail">
        <div class="review-meta">
          <span class="tag tag-platform">{{ current.repo_name }}</span>
          <span class="mono">{{ current.short_sha }}</span>
          <span v-if="current.commit_url" class="table-subject is-muted">
            <a :href="current.commit_url" target="_blank" rel="noreferrer">打开提交</a>
          </span>
          <span class="table-subject is-muted">{{ current.model }}</span>
        </div>

        <div v-if="!current.findings.length" class="empty-hint">
          {{ current.message || '未发现明显质量问题' }}
        </div>

        <section
          v-for="item in current.findings"
          :key="item.id"
          class="panel panel-pad finding-card"
        >
          <div class="finding-head">
            <span class="tag" :class="SEVERITY_CLASS[item.severity] ?? 'tag-muted'">
              {{ SEVERITY_LABEL[item.severity] ?? item.severity }}
            </span>
            <span v-if="item.category" class="tag tag-muted">{{ item.category }}</span>
            <span class="finding-title">{{ item.title }}</span>
          </div>
          <div v-if="item.file_path" class="finding-path mono">
            {{ item.file_path }}<span v-if="item.line">:{{ item.line }}</span>
          </div>
          <p v-if="item.detail" class="finding-detail">{{ item.detail }}</p>
          <div class="finding-foot">
            <span class="tag" :class="item.status === 'created' ? 'tag-success' : 'tag-muted'">
              {{ FINDING_STATUS[item.status] ?? item.status }}
            </span>
            <a v-if="item.issue_url" :href="item.issue_url" target="_blank" rel="noreferrer">
              #{{ item.issue_number }}
            </a>
            <span class="finding-actions">
              <el-button
                v-if="item.status === 'pending'"
                size="small"
                type="primary"
                :loading="pushing === item.review_id"
                @click="pushOne(item)"
              >
                推送 Issue
              </el-button>
              <el-button v-if="item.status === 'pending'" size="small" @click="ignore(item)">
                忽略
              </el-button>
            </span>
          </div>
        </section>
      </div>

      <template #footer>
        <el-button
          type="primary"
          :disabled="!current || pendingCount === 0"
          :loading="pushing === current?.id"
          @click="pushAll"
        >
          推送全部 Issue
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.review-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
}

.finding-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.finding-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.finding-title {
  font-weight: 600;
  font-size: 14px;
}

.finding-path {
  color: var(--text-muted);
}

.finding-detail {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
  white-space: pre-wrap;
}

.finding-foot {
  display: flex;
  align-items: center;
  gap: 10px;
}

.finding-actions {
  margin-left: auto;
}
</style>