<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { repoApi } from '@/api'
import type { Platform, Repo, RepoPayload } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const syncing = ref<number | null>(null)
const rows = ref<Repo[]>([])
const keyword = ref('')
const platformFilter = ref<Platform | ''>('')

const drawerOpen = ref(false)
const editingId = ref<number | null>(null)
const repoUrl = ref('')
const advancedOpen = ref<string[]>([])
const formRef = ref<FormInstance>()
const submitting = ref(false)
const probing = ref(false)

const blank = (): RepoPayload => ({
  name: '',
  project: '',
  platform: 'gitea',
  owner: '',
  repo: '',
  base_url: '',
  token: '',
  enabled: true,
  include_keywords: '',
  exclude_keywords: '',
})
const form = reactive<RepoPayload>(blank())

const rules: FormRules = {
  repoUrl: [{ required: true, message: '请粘贴仓库地址', trigger: 'blur' }],
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  owner: [{ required: true, message: '请填写拥有者', trigger: 'blur' }],
  repo: [{ required: true, message: '请填写仓库名', trigger: 'blur' }],
}

const filtered = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  return rows.value.filter((item) => {
    if (platformFilter.value && item.platform !== platformFilter.value) return false
    if (!key) return true
    return [item.name, item.owner, item.repo].some((field) => field.toLowerCase().includes(key))
  })
})

function statusTag(item: Repo) {
  if (item.last_sync_status === 'success')
    return { text: '已同步', cls: 'tag-success', light: '' }
  if (item.last_sync_status === 'failed')
    return { text: '同步失败', cls: 'tag-danger', light: 'is-red' }
  return { text: '未同步', cls: 'tag-muted', light: 'is-amber' }
}

async function load() {
  loading.value = true
  try {
    rows.value = await repoApi.list()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, blank())
  repoUrl.value = ''
  advancedOpen.value = []
  formRef.value?.clearValidate()
  drawerOpen.value = true
}

function openEdit(row: Repo) {
  editingId.value = row.id
  repoUrl.value = ''
  advancedOpen.value = ['advanced']
  Object.assign(form, {
    name: row.name,
    project: row.project || row.name,
    platform: row.platform,
    owner: row.owner,
    repo: row.repo,
    base_url: row.base_url,
    token: '',
    enabled: row.enabled,
    include_keywords: row.include_keywords,
    exclude_keywords: row.exclude_keywords,
  })
  formRef.value?.clearValidate()
  drawerOpen.value = true
}

async function parseUrl() {
  const url = repoUrl.value.trim()
  if (!url) return
  try {
    const result = await repoApi.parse({ url, token: form.token })
    if (!result.ok) {
      ElMessage.error(result.message)
      return
    }
    form.platform = (result.platform || form.platform) as Platform
    form.owner = result.owner || form.owner
    form.repo = result.repo || form.repo
    form.base_url = result.base_url || form.base_url
    if (!form.name) form.name = result.repo || ''
    if (!form.project) form.project = result.repo || ''
    ElMessage.success(result.message)
  } catch (error) {
    ElMessage.error('地址解析失败')
  }
}

async function probeConnection() {
  if (!form.base_url) {
    ElMessage.warning('请先填写服务地址')
    return
  }
  probing.value = true
  try {
    const result = await repoApi.probe({ ...form })
    if (result.detected_platform && result.detected_platform !== form.platform) {
      form.platform = result.detected_platform as Platform
      ElMessage.warning(`服务地址是 ${result.detected_platform} 实例，已切换平台`)
      return
    }
    if (result.ok) {
      ElMessage.success(result.message)
    } else {
      ElMessage.error(result.message)
    }
  } finally {
    probing.value = false
  }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    advancedOpen.value = ['advanced']
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      const payload: Partial<RepoPayload> = { ...form }
      if (!form.token.trim()) {
        delete payload.token
      }
      await repoApi.update(editingId.value, payload)
      ElMessage.success('已保存')
    } else {
      await repoApi.create({ ...form })
      ElMessage.success('已创建')
    }
    drawerOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function syncOne(row: Repo) {
  syncing.value = row.id
  try {
    const result = await repoApi.sync(row.id)
    ElMessage.success(`同步完成，新增 ${result.created} 条提交`)
    await load()
  } catch {
    await load()
  } finally {
    syncing.value = null
  }
}

async function syncAll() {
  syncing.value = -1
  try {
    const result = await repoApi.syncAll()
    const failed = (result.results ?? []).filter((item: { ok: boolean }) => !item.ok)
    if (failed.length) {
      ElMessage.warning(`同步完成，${failed.length} 个仓库失败`)
    } else {
      ElMessage.success('同步完成')
    }
    await load()
  } finally {
    syncing.value = null
  }
}

async function remove(row: Repo) {
  await ElMessageBox.confirm(`确认删除仓库「${row.name}」及其提交记录？`, '删除仓库', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await repoApi.remove(row.id)
  ElMessage.success('已删除')
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
          placeholder="搜索名称或仓库"
          clearable
          style="width: 230px"
        />
        <el-select v-model="platformFilter" placeholder="全部平台" clearable style="width: 130px">
          <el-option label="Gitea" value="gitea" />
          <el-option label="Gitee" value="gitee" />
        </el-select>
      </div>
      <div class="toolbar-actions">
        <el-button :icon="Refresh" :loading="syncing === -1" @click="syncAll">同步全部</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建仓库</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table v-loading="loading" :data="filtered" style="width: 100%">
        <el-table-column label="仓库" min-width="200">
          <template #default="{ row }">
            <div class="table-subject">{{ row.name }}</div>
            <div class="table-subject is-muted mono">{{ row.owner }}/{{ row.repo }}</div>
          </template>
        </el-table-column>
        <el-table-column label="项目" width="140">
          <template #default="{ row }">
            <span class="tag tag-platform">{{ row.project || row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="平台" width="110">
          <template #default="{ row }">
            <span class="tag tag-platform">{{ row.platform }}</span>
          </template>
        </el-table-column>
        <el-table-column label="服务地址" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.base_url || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <span class="tag" :class="statusTag(row).cls">
              <span class="status-light" :class="statusTag(row).light" />
              {{ statusTag(row).text }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近同步" width="180">
          <template #default="{ row }">
            <div class="num">{{ formatDateTime(row.last_sync_at) }}</div>
            <div v-if="row.last_sync_message" class="table-subject is-muted">
              {{ row.last_sync_message }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.enabled" type="success" effect="plain" size="small">是</el-tag>
            <el-tag v-else type="info" effect="plain" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :loading="syncing === row.id" @click="syncOne(row)">
              同步
            </el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint">暂无数据</div>
        </template>
      </el-table>
    </section>

    <el-drawer v-model="drawerOpen" :title="editingId ? '编辑仓库' : '新建仓库'" size="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item v-if="!editingId" label="仓库地址" prop="repoUrl" class="span-2">
            <el-input
              v-model="repoUrl"
              placeholder="https://gitee.com/owner/repo"
              @blur="parseUrl"
              @keyup.enter="parseUrl"
            />
          </el-form-item>
          <el-form-item label="访问令牌" class="span-2">
            <el-input
              v-model="form.token"
              type="password"
              show-password
              :placeholder="editingId ? '留空表示不修改' : 'Gitea / Gitee 私人令牌'"
              @blur="parseUrl"
            />
          </el-form-item>
          <el-form-item label="名称" prop="name" class="span-2">
            <el-input v-model="form.name" placeholder="如：短临预警系统" />
          </el-form-item>
          <el-form-item label="项目" class="span-2">
            <el-input v-model="form.project" placeholder="留空则与名称一致，周报按此分组" />
          </el-form-item>
          <el-form-item label="包含关键字">
            <el-input v-model="form.include_keywords" placeholder="逗号分隔，留空表示全部" />
          </el-form-item>
          <el-form-item label="排除关键字">
            <el-input v-model="form.exclude_keywords" placeholder="merge, wip" />
          </el-form-item>
          <el-form-item label="参与定时同步" class="span-2">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </div>
        <el-collapse v-model="advancedOpen">
          <el-collapse-item title="平台与路径" name="advanced">
            <div class="form-grid">
              <el-form-item label="平台" prop="platform">
                <el-select v-model="form.platform" style="width: 100%">
                  <el-option label="Gitea" value="gitea" />
                  <el-option label="Gitee" value="gitee" />
                </el-select>
              </el-form-item>
              <el-form-item label="拥有者" prop="owner">
                <el-input v-model="form.owner" placeholder="group" />
              </el-form-item>
              <el-form-item label="仓库名" prop="repo">
                <el-input v-model="form.repo" placeholder="project" />
              </el-form-item>
              <el-form-item label="服务地址">
                <el-input v-model="form.base_url" placeholder="https://gitea.com" />
              </el-form-item>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <div class="drawer-footer">
        <el-button :loading="probing" @click="probeConnection">测试连接</el-button>
        <el-button @click="drawerOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-drawer>
  </div>
</template>