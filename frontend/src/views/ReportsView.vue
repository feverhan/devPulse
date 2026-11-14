<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { reportApi } from '@/api'
import type { PeriodType, Report } from '@/api/types'
import { PERIOD_LABEL, copyText, downloadText, formatDate, formatDateTime, todayISO } from '@/utils/format'

const loading = ref(false)
const rows = ref<Report[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const periodFilter = ref<PeriodType | ''>('')
const keyword = ref('')

const dialogOpen = ref(false)
const generating = ref(false)
const form = ref({
  period_type: 'weekly' as PeriodType,
  reference_date: todayISO(),
  start_date: '',
  end_date: '',
  focus: '',
  include_commits: true,
  include_works: true,
  use_llm: true,
})

const drawerOpen = ref(false)
const current = ref<Report | null>(null)

const PROJECT_TITLE = /^([一二三四五六七八九十]+、\S.*)$/
const NUMBERED_ITEM = /^(\d+)\.\s*(.+)$/

function normalizeMarkdown(content: string): string {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const kept: string[] = []
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const prev = kept[kept.length - 1] ?? ''
    const next = lines[index + 1] ?? ''
    const blank = line.trim() === ''
    if (blank && NUMBERED_ITEM.test(prev) && NUMBERED_ITEM.test(next)) continue
    kept.push(line)
  }
  return kept
    .map((line) => {
      const title = line.match(PROJECT_TITLE)
      if (title) return `## ${title[1]}`
      const item = line.match(NUMBERED_ITEM)
      if (item) return `${item[1]}. ${item[2]}`
      return line
    })
    .join('\n')
}

const rendered = computed(() => {
  if (!current.value?.content) return ''
  return DOMPurify.sanitize(marked.parse(normalizeMarkdown(current.value.content)) as string)
})

async function load() {
  loading.value = true
  try {
    const result = await reportApi.list({
      period_type: periodFilter.value || undefined,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function openGenerate() {
  form.value = {
    period_type: 'weekly',
    reference_date: todayISO(),
    start_date: '',
    end_date: '',
    focus: '',
    include_commits: true,
    include_works: true,
    use_llm: true,
  }
  dialogOpen.value = true
}

async function generate() {
  generating.value = true
  try {
    const payload = {
      period_type: form.value.period_type,
      reference_date: form.value.period_type === 'custom' ? null : form.value.reference_date,
      start_date: form.value.period_type === 'custom' ? form.value.start_date : null,
      end_date: form.value.period_type === 'custom' ? form.value.end_date : null,
      focus: form.value.focus,
      include_commits: form.value.include_commits,
      include_works: form.value.include_works,
      use_llm: form.value.use_llm,
    }
    const report = await reportApi.generate(payload)
    ElMessage.success('报告已生成')
    dialogOpen.value = false
    await load()
    current.value = report
    drawerOpen.value = true
  } finally {
    generating.value = false
  }
}

async function openDetail(row: Report) {
  current.value = await reportApi.get(row.id)
  drawerOpen.value = true
}

async function copyReport(row: Report) {
  const ok = await copyText(row.content)
  ElMessage[ok ? 'success' : 'warning'](ok ? '已复制到剪贴板' : '复制失败')
}

function downloadReport(row: Report) {
  downloadText(`${row.title}.md`, row.content)
  ElMessage.success('已下载')
}

async function remove(row: Report) {
  await ElMessageBox.confirm(`确认删除报告「${row.title}」？`, '删除报告', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await reportApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

watch([page, pageSize], load)

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <el-select v-model="periodFilter" placeholder="全部周期" clearable style="width: 130px" @change="search">
          <el-option label="周报" value="weekly" />
          <el-option label="月报" value="monthly" />
          <el-option label="季报" value="quarterly" />
          <el-option label="年报" value="yearly" />
          <el-option label="自定义" value="custom" />
        </el-select>
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          placeholder="搜索标题"
          clearable
          style="width: 220px"
          @keyup.enter="search"
          @clear="search"
        />
      </div>
      <div class="toolbar-actions">
        <el-button type="primary" :icon="Plus" @click="openGenerate">生成报告</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column label="标题" min-width="260">
          <template #default="{ row }">
            <div class="table-subject">{{ row.title }}</div>
            <div v-if="row.summary" class="table-subject is-muted">{{ row.summary }}</div>
          </template>
        </el-table-column>
        <el-table-column label="周期" width="90">
          <template #default="{ row }">
            <span class="tag tag-platform">{{ PERIOD_LABEL[row.period_type] ?? row.period_type }}</span>
          </template>
        </el-table-column>
        <el-table-column label="统计区间" width="200">
          <template #default="{ row }">
            <span class="num">{{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="项目" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.stats?.project_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交" width="80">
          <template #default="{ row }">
            <span class="num">{{ row.stats?.commit_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="生成时间" width="160">
          <template #default="{ row }">
            <span class="num">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看</el-button>
            <el-button link type="primary" @click="copyReport(row)">复制</el-button>
            <el-button link type="primary" @click="downloadReport(row)">下载</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>

      <div style="display: flex; justify-content: flex-end; padding: 12px 16px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </section>

    <el-dialog v-model="dialogOpen" title="生成报告" width="460px">
      <el-form label-position="top">
        <el-form-item label="周期">
          <el-radio-group v-model="form.period_type">
            <el-radio-button value="weekly">周报</el-radio-button>
            <el-radio-button value="monthly">月报</el-radio-button>
            <el-radio-button value="quarterly">季报</el-radio-button>
            <el-radio-button value="yearly">年报</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.period_type === 'custom'" label="统计区间">
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="开始日期"
            style="width: 100%"
          />
          <el-date-picker
            v-model="form.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="结束日期"
            style="margin-top: 8px; width: 100%"
          />
        </el-form-item>
        <el-form-item v-else label="基准日期">
          <el-date-picker
            v-model="form.reference_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="侧重">
          <el-input
            v-model="form.focus"
            type="textarea"
            :rows="3"
            placeholder="例如：突出数据平台的性能优化成果"
          />
        </el-form-item>

        <el-form-item label="数据来源">
          <el-checkbox v-model="form.include_commits">代码提交</el-checkbox>
          <el-checkbox v-model="form.include_works">工作记录</el-checkbox>
        </el-form-item>

        <el-form-item label="生成方式">
          <el-checkbox v-model="form.use_llm">使用大模型撰写</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="generate">生成</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawerOpen" :title="current?.title ?? '报告'" size="720px">
      <div v-if="current" class="report-layout">
        <div class="stat-grid">
          <div class="stat-tile">
            <div class="stat-head">
              <span class="status-light is-cyan" />
              <span class="stat-label">涉及项目</span>
            </div>
            <div class="stat-value">{{ current.stats?.project_count ?? 0 }}</div>
          </div>
          <div class="stat-tile">
            <div class="stat-head">
              <span class="status-light" />
              <span class="stat-label">代码提交</span>
            </div>
            <div class="stat-value">{{ current.stats?.commit_count ?? 0 }}</div>
            <div class="stat-meta">
              <span class="delta-plus">+{{ current.stats?.additions ?? 0 }}</span>
              <span class="delta-minus">/{{ current.stats?.deletions ?? 0 }}</span>
            </div>
          </div>
          <div class="stat-tile">
            <div class="stat-head">
              <span class="status-light" />
              <span class="stat-label">工作记录</span>
            </div>
            <div class="stat-value">{{ current.stats?.work_count ?? 0 }}</div>
            <div class="stat-meta">登记工时 {{ current.stats?.hours ?? 0 }} 小时</div>
          </div>
          <div class="stat-tile">
            <div class="stat-head">
              <span class="status-light is-violet" />
              <span class="stat-label">统计区间</span>
            </div>
            <div class="stat-value stat-range">
              {{ formatDate(current.start_date) }} ~ {{ formatDate(current.end_date) }}
            </div>
            <div class="stat-meta">{{ current.model || '—' }}</div>
          </div>
        </div>

        <section v-if="current.stats?.by_project?.length" class="panel panel-pad">
          <h3 class="panel-title">项目分布</h3>
          <div v-for="item in current.stats.by_project" :key="item.name" class="spark-row">
            <span class="spark-name">{{ item.name }}</span>
            <span class="spark-count num">{{ item.works }} 条记录 / {{ item.commits }} 次提交</span>
          </div>
        </section>

        <section class="panel panel-pad">
          <h3 class="panel-title">报告正文</h3>
          <div class="markdown-body" v-html="rendered" />
        </section>
      </div>
      <template #footer>
        <el-button @click="current && copyReport(current)">复制</el-button>
        <el-button type="primary" @click="current && downloadReport(current)">下载 Markdown</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.report-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.stat-range {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
}
</style>