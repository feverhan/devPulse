<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { projectApi, workApi } from '@/api'
import type { Project, WorkEntry, WorkPayload } from '@/api/types'
import { CATEGORY_OPTIONS, formatDate } from '@/utils/format'

const loading = ref(false)
const rows = ref<WorkEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)

const keyword = ref('')
const category = ref('')
const project = ref('')
const range = ref<[string, string] | null>(null)
const projects = ref<Project[]>([])

const drawerOpen = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const blank = (): WorkPayload => ({
  work_date: new Date().toISOString().slice(0, 10),
  title: '',
  content: '',
  category: '研发',
  project: '',
  tags: '',
  hours: null,
})
const form = reactive<WorkPayload>(blank())

const rules: FormRules = {
  work_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
}

async function load() {
  loading.value = true
  try {
    const result = await workApi.list({
      keyword: keyword.value || undefined,
      category: category.value || undefined,
      project: project.value || undefined,
      start_date: range.value?.[0] ?? null,
      end_date: range.value?.[1] ?? null,
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

function reset() {
  keyword.value = ''
  category.value = ''
  project.value = ''
  range.value = null
  search()
}

function openCreate() {
  editingId.value = null
  Object.assign(form, blank())
  if (project.value) {
    form.project = project.value
  } else if (projects.value.length === 1) {
    form.project = projects.value[0].name
  }
  formRef.value?.clearValidate()
  drawerOpen.value = true
}

function openEdit(row: WorkEntry) {
  editingId.value = row.id
  Object.assign(form, {
    work_date: row.work_date,
    title: row.title,
    content: row.content,
    category: row.category,
    project: row.project,
    tags: row.tags,
    hours: row.hours,
  })
  formRef.value?.clearValidate()
  drawerOpen.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editingId.value) {
      await workApi.update(editingId.value, { ...form })
      ElMessage.success('已保存')
    } else {
      await workApi.create({ ...form })
      ElMessage.success('已创建')
    }
    drawerOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function remove(row: WorkEntry) {
  await ElMessageBox.confirm(`确认删除「${row.title}」？`, '删除记录', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await workApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

watch([page, pageSize], load)

async function loadProjects() {
  projects.value = await projectApi.list()
}

onMounted(async () => {
  await loadProjects()
  await load()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          placeholder="搜索标题或内容"
          clearable
          style="width: 230px"
          @keyup.enter="search"
          @clear="search"
        />
        <el-select v-model="category" placeholder="全部类别" clearable style="width: 120px" @change="search">
          <el-option v-for="item in CATEGORY_OPTIONS" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="project" placeholder="全部项目" clearable style="width: 170px" @change="search">
          <el-option v-for="item in projects" :key="item.name" :label="item.name" :value="item.name" />
        </el-select>
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 250px"
          @change="search"
        />
        <el-button @click="reset">重置</el-button>
      </div>
      <div class="toolbar-actions">
        <el-button type="primary" :icon="Plus" @click="openCreate">新建记录</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column label="日期" width="120">
          <template #default="{ row }">
            <span class="num">{{ formatDate(row.work_date) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="工作内容" min-width="320">
          <template #default="{ row }">
            <div class="table-subject">{{ row.title }}</div>
            <div v-if="row.content" class="table-subject is-muted">{{ row.content }}</div>
          </template>
        </el-table-column>
        <el-table-column label="项目" width="140">
          <template #default="{ row }">
            <span class="tag tag-muted">{{ row.project || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类别" width="100">
          <template #default="{ row }">
            <span class="tag tag-accent">{{ row.category }}</span>
          </template>
        </el-table-column>
        <el-table-column label="工时" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.hours ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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
          :page-sizes="[20, 30, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </section>

    <el-drawer v-model="drawerOpen" :title="editingId ? '编辑记录' : '新建记录'" size="440px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="日期" prop="work_date">
          <el-date-picker
            v-model="form.work_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="完成报告生成接口联调" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="5" placeholder="具体做了什么、结果如何" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" prop="project">
            <el-select
              v-model="form.project"
              filterable
              allow-create
              default-first-option
              placeholder="选择项目"
              style="width: 100%"
            >
              <el-option v-for="item in projects" :key="item.name" :label="item.name" :value="item.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="类别">
            <el-select v-model="form.category" style="width: 100%">
              <el-option v-for="item in CATEGORY_OPTIONS" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="工时（小时）">
            <el-input-number v-model="form.hours" :min="0" :max="24" :step="0.5" style="width: 100%" />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="form.tags" placeholder="逗号分隔" />
          </el-form-item>
        </div>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="drawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-drawer>
  </div>
</template>