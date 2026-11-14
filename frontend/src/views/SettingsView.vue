<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { commitApi, repoApi, settingsApi } from '@/api'
import type { AppSettings } from '@/api/types'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const settings = ref<AppSettings | null>(null)

const llm = reactive({
  base_url: '',
  api_key: '',
  model: '',
  temperature: 0.3,
})
const sync = reactive({
  sync_interval_minutes: 30,
  max_pages_per_sync: 20,
  fetch_commit_files: true,
})
const password = ref('')
const wechatWebhook = ref('')
const myAuthors = ref<string[]>([])
const authorOptions = ref<Array<{ label: string; value: string; count: number }>>([])

async function load() {
  loading.value = true
  try {
    const data = await settingsApi.get()
    settings.value = data
    llm.base_url = data.llm.base_url
    llm.api_key = ''
    llm.model = data.llm.model
    llm.temperature = data.llm.temperature
    sync.sync_interval_minutes = data.sync_interval_minutes
    sync.max_pages_per_sync = data.max_pages_per_sync
    sync.fetch_commit_files = data.fetch_commit_files
    myAuthors.value = data.my_authors ?? []
    wechatWebhook.value = data.wechat_webhook ?? ''
    await loadAuthors()
  } finally {
    loading.value = false
  }
}

async function loadAuthors() {
  const list = await commitApi.authors()
  const seen = new Set<string>()
  authorOptions.value = list
    .map((item) => {
      const value = item.author_login || item.author_name || item.author_email
      const detail = [item.author_name, item.author_login, item.author_email].filter(Boolean)
      const unique = [...new Set(detail)]
      return { label: unique.join(' · '), value, count: item.count }
    })
    .filter((item) => {
      if (!item.value || seen.has(item.value)) return false
      seen.add(item.value)
      return true
    })
}

async function saveLlm() {
  saving.value = true
  try {
    const data = await settingsApi.save({
      llm: {
        base_url: llm.base_url,
        api_key: llm.api_key,
        model: llm.model,
        temperature: llm.temperature,
      },
    })
    settings.value = data
    llm.api_key = ''
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

async function testLlm() {
  testing.value = true
  try {
    const result = await settingsApi.testLlm()
    ElMessage.success(`连接成功：${result.reply}`)
  } finally {
    testing.value = false
  }
}

async function saveSync(resync = false) {
  saving.value = true
  try {
    const data = await settingsApi.save({
      sync_interval_minutes: sync.sync_interval_minutes,
      max_pages_per_sync: sync.max_pages_per_sync,
      fetch_commit_files: sync.fetch_commit_files,
      my_authors: myAuthors.value,
    })
    settings.value = data
    if (resync) {
      const result = await repoApi.syncAll()
      const failed = (result.results ?? []).filter((item: { ok: boolean }) => !item.ok)
      if (failed.length) {
        ElMessage.warning(`已保存，同步完成，${failed.length} 个仓库失败`)
      } else {
        ElMessage.success('已保存并重新同步')
      }
    } else {
      ElMessage.success('已保存')
    }
  } finally {
    saving.value = false
  }
}

async function saveWebhook() {
  saving.value = true
  try {
    const data = await settingsApi.save({ wechat_webhook: wechatWebhook.value })
    settings.value = data
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  if (!password.value) {
    ElMessage.warning('请输入新密码')
    return
  }
  saving.value = true
  try {
    const data = await settingsApi.save({ app_password: password.value })
    settings.value = data
    password.value = ''
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="settings-wrap">
    <section class="panel panel-pad">
      <h3 class="panel-title">大模型</h3>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="接口地址" class="span-2">
            <el-input v-model="llm.base_url" placeholder="http://127.0.0.1:8000/v1" />
          </el-form-item>
          <el-form-item label="API Key" class="span-2">
            <el-input
              v-model="llm.api_key"
              type="password"
              show-password
              :placeholder="settings?.llm.api_key_set ? '已配置，留空表示不修改' : '本地部署可留空'"
            />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="llm.model" placeholder="qwen2.5:7b" />
          </el-form-item>
          <el-form-item label="温度">
            <el-input-number
              v-model="llm.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              style="width: 100%"
            />
          </el-form-item>
        </div>
      </el-form>
      <div class="drawer-footer">
        <el-button :icon="Connection" :loading="testing" @click="testLlm">测试连接</el-button>
        <el-button type="primary" :loading="saving" @click="saveLlm">保存</el-button>
      </div>
    </section>

    <section class="panel panel-pad">
      <h3 class="panel-title">同步</h3>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="定时同步间隔（分钟）">
            <el-input-number
              v-model="sync.sync_interval_minutes"
              :min="5"
              :max="1440"
              :step="5"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="单次拉取最大页数">
            <el-input-number
              v-model="sync.max_pages_per_sync"
              :min="1"
              :max="100"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="拉取文件变更明细" class="span-2">
            <el-switch v-model="sync.fetch_commit_files" />
          </el-form-item>
          <el-form-item label="我的作者标识" class="span-2">
            <el-select
              v-model="myAuthors"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="留空则汇总全部作者的提交"
              style="width: 100%"
            >
              <el-option
                v-for="item in authorOptions"
                :key="item.value"
                :label="`${item.label}（${item.count}）`"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <div class="drawer-footer">
        <el-button :loading="saving" @click="saveSync(true)">保存并重新同步</el-button>
        <el-button type="primary" :loading="saving" @click="saveSync(false)">保存</el-button>
      </div>
    </section>

    <section class="panel panel-pad">
      <h3 class="panel-title">告警</h3>
      <el-form label-position="top">
        <el-form-item label="企业微信群机器人 Webhook">
          <el-input
            v-model="wechatWebhook"
            placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
            style="max-width: 560px"
          />
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button type="primary" :loading="saving" @click="saveWebhook">保存</el-button>
      </div>
    </section>

    <section class="panel panel-pad">
      <h3 class="panel-title">访问控制</h3>
      <el-form label-position="top">
        <el-form-item label="访问密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            placeholder="设置后访问本系统需要输入该密码"
            style="max-width: 360px"
          />
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button type="primary" :loading="saving" @click="savePassword">保存</el-button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 860px;
}
</style>