<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { projectApi } from '@/api'
import type { Project } from '@/api/types'

const loading = ref(false)
const rows = ref<Project[]>([])
const keyword = ref('')

const dialogOpen = ref(false)
const submitting = ref(false)
const form = ref({ name: '', note: '' })

const filtered = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  if (!key) return rows.value
  return rows.value.filter((item) => item.name.toLowerCase().includes(key))
})

function sourceTag(item: Project) {
  return item.source === 'manual'
    ? { text: '手工登记', cls: 'tag-accent' }
    : { text: '来自仓库', cls: 'tag-muted' }
}

async function load() {
  loading.value = true
  try {
    rows.value = await projectApi.list()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { name: '', note: '' }
  dialogOpen.value = true
}

async function submit() {
  const name = form.value.name.trim()
  if (!name) {
    ElMessage.warning('请填写项目名称')
    return
  }
  submitting.value = true
  try {
    await projectApi.create({ name, note: form.value.note.trim() })
    ElMessage.success('已创建')
    dialogOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function remove(row: Project) {
  await ElMessageBox.confirm(
    `确认删除项目「${row.name}」？该项目下的工作记录会一并删除。`,
    '删除项目',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  const result = await projectApi.remove(row.id as number)
  ElMessage.success(`已删除，同时清理 ${result.removed_works} 条工作记录`)
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          placeholder="搜索项目"
          clearable
          style="width: 220px"
        />
      </div>
      <div class="toolbar-actions">
        <el-button type="primary" :icon="Plus" @click="openCreate">新建项目</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table v-loading="loading" :data="filtered" style="width: 100%">
        <el-table-column label="项目" min-width="220">
          <template #default="{ row }">
            <div class="table-subject">{{ row.name }}</div>
            <div v-if="row.note" class="table-subject is-muted">{{ row.note }}</div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="120">
          <template #default="{ row }">
            <span class="tag" :class="sourceTag(row).cls">{{ sourceTag(row).text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="仓库" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.repos }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交" width="90">
          <template #default="{ row }">
            <span class="num">{{ row.commits }}</span>
          </template>
        </el-table-column>
        <el-table-column label="工作记录" width="110">
          <template #default="{ row }">
            <span class="num">{{ row.works }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.id" link type="danger" @click="remove(row)">删除</el-button>
            <span v-else class="table-subject is-muted">—</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>
    </section>

    <el-dialog v-model="dialogOpen" title="新建项目" width="420px">
      <el-form label-position="top">
        <el-form-item label="项目名称">
          <el-input v-model="form.name" placeholder="如：集团访客系统" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>