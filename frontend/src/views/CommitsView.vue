<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { commitApi, repoApi } from '@/api'
import type { Commit, Repo } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const rows = ref<Commit[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)
const repos = ref<Repo[]>([])

const repoId = ref<number | null>(null)
const keyword = ref('')
const range = ref<[string, string] | null>(null)

async function load() {
  loading.value = true
  try {
    const result = await commitApi.list({
      repo_id: repoId.value,
      keyword: keyword.value || undefined,
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
  repoId.value = null
  keyword.value = ''
  range.value = null
  search()
}

watch([page, pageSize], load)

onMounted(async () => {
  repos.value = await repoApi.list()
  await load()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <el-select v-model="repoId" placeholder="全部仓库" clearable style="width: 160px" @change="search">
          <el-option v-for="item in repos" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          placeholder="搜索提交说明或哈希"
          clearable
          style="width: 240px"
          @keyup.enter="search"
          @clear="search"
        />
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
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <section class="panel">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column label="仓库" width="140">
          <template #default="{ row }">
            <span class="tag tag-platform">{{ row.repo_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交说明" min-width="320">
          <template #default="{ row }">
            <div class="table-subject">{{ row.message.split('\n')[0] }}</div>
            <div class="table-subject is-muted mono">{{ row.short_sha }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="author_name" label="作者" width="110" />
        <el-table-column label="变更" width="140">
          <template #default="{ row }">
            <span class="delta-plus num">+{{ row.additions }}</span>
            <span class="delta-minus num">/{{ row.deletions }}</span>
          </template>
        </el-table-column>
        <el-table-column label="文件" width="80">
          <template #default="{ row }">
            <span class="num">{{ row.changed_files }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">
            <span class="num">{{ formatDateTime(row.committed_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="链接" width="80">
          <template #default="{ row }">
            <a v-if="row.url" :href="row.url" target="_blank" rel="noreferrer">打开</a>
            <span v-else class="table-subject is-muted">—</span>
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
  </div>
</template>