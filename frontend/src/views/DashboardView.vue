<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Collection,
  Document,
  EditPen,
  FolderOpened,
  Monitor,
  Promotion,
  Tickets,
} from '@element-plus/icons-vue'
import { dashboardApi } from '@/api'
import type { Overview } from '@/api/types'
import TrendChart from '@/components/TrendChart.vue'
import { formatDateTime } from '@/utils/format'

const loading = ref(true)
const data = ref<Overview | null>(null)

const tiles = computed(() => {
  const item = data.value
  return [
    {
      key: 'repos',
      name: '仓库',
      icon: FolderOpened,
      span: 'span-3',
      value: item?.repo_count ?? 0,
      meta: `已接入 ${item?.repo_count ?? 0} 个代码仓库`,
      light: 'is-cyan',
    },
    {
      key: 'commits',
      name: '提交记录',
      icon: Tickets,
      span: 'span-3',
      value: item?.commit_total ?? 0,
      meta: `本周 ${item?.commit_week ?? 0} 次 · 今日 ${item?.commit_today ?? 0} 次`,
      light: '',
    },
    {
      key: 'projects',
      name: '项目',
      icon: Collection,
      span: 'span-3',
      value: item?.project_count ?? 0,
      meta: `仓库抽取 + 手工登记`,
      light: '',
    },
    {
      key: 'works',
      name: '工作记录',
      icon: EditPen,
      span: 'span-3',
      value: item?.work_total ?? 0,
      meta: `本周 ${item?.work_week ?? 0} 条 · ${item?.hours_week ?? 0} 小时`,
      light: '',
    },
    {
      key: 'reports',
      name: '报告',
      icon: Document,
      span: 'span-4',
      value: item?.report_count ?? 0,
      meta: item?.llm_ready ? `模型 ${item.llm_model}` : '未配置大模型',
      light: item?.llm_ready ? 'is-violet' : 'is-amber',
    },
    {
      key: 'reviews',
      name: '代码审查',
      icon: Promotion,
      span: 'span-4',
      value: item?.finding_total ?? 0,
      meta:
        (item?.review_running ?? 0) > 0
          ? `${item?.review_running} 个任务运行中`
          : `已审 ${item?.review_count ?? 0} 个提交 · 待推送 ${item?.finding_pending ?? 0} 条`,
      light: (item?.finding_pending ?? 0) > 0 ? 'is-amber' : '',
    },
    {
      key: 'monitors',
      name: '服务监控',
      icon: Monitor,
      span: 'span-4',
      value: item?.monitor_ok ?? 0,
      meta: `共 ${item?.monitor_total ?? 0} 个目标 · 异常 ${item?.monitor_fail ?? 0} 个`,
      light: (item?.monitor_fail ?? 0) > 0 ? 'is-red' : '',
    },
  ]
})

const activityKind = (kind: string) =>
  kind === 'commit' ? '提交' : kind === 'report' ? '报告' : '审查'

async function load() {
  loading.value = true
  try {
    data.value = await dashboardApi.overview()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="workspace">
    <div class="bento">
      <router-link
        v-for="tile in tiles"
        :key="tile.key"
        class="tile"
        :class="tile.span"
        :to="{ name: tile.key }"
      >
        <div class="tile-top">
          <span class="tile-icon">
            <el-icon><component :is="tile.icon" /></el-icon>
          </span>
          <span class="status-light" :class="tile.light" />
        </div>
        <div class="tile-name">{{ tile.name }}</div>
        <div class="tile-value">{{ tile.value }}</div>
        <div class="tile-meta">{{ tile.meta }}</div>
      </router-link>

      <section class="tile-panel span-8">
        <h3 class="panel-title">提交趋势 · 近 14 天</h3>
        <div class="tile-chart">
          <TrendChart :data="data?.trend ?? []" />
        </div>
      </section>

      <section class="tile-panel span-4">
        <h3 class="panel-title">最近动态</h3>
        <div class="tile-list">
          <div v-if="!data?.activity?.length" class="empty-hint">暂无数据</div>
          <div v-for="(row, index) in data?.activity ?? []" :key="index" class="activity-row">
            <span class="tag" :class="row.kind === 'commit' ? 'tag-platform' : row.kind === 'report' ? 'tag-success' : 'tag-accent'">
              {{ activityKind(row.kind) }}
            </span>
            <span class="activity-text">{{ row.text }}</span>
            <span class="activity-time num">{{ formatDateTime(row.time) }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  height: calc(100vh - 86px);
  overflow: hidden;
}

.bento {
  height: 100%;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 8px;
}

.span-3 {
  grid-column: span 3;
}

.span-4 {
  grid-column: span 4;
}

.span-8 {
  grid-column: span 8;
}

.tile {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 132px;
  padding: 14px 16px;
  text-decoration: none;
  background: var(--hud-panel);
  backdrop-filter: blur(20px);
  border: 1px solid var(--hud-border);
  border-radius: var(--hud-radius-card);
  box-shadow: var(--hud-glow);
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.tile::before {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background:
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left top / 14px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left top / 2px 14px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right bottom / 14px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right bottom / 2px 14px no-repeat;
}

.tile:hover {
  border-color: var(--hud-border-strong);
  box-shadow: var(--hud-glow-active);
  transform: translateY(-2px);
}

.tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.tile-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 2px;
  border: 1px solid var(--hud-border);
  background: rgba(6, 182, 212, 0.08);
  color: var(--hud-bright);
  font-size: 15px;
}

.tile-name {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--hud-text-dim);
}

.tile-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
  color: var(--hud-bright);
  text-shadow: var(--hud-text-glow);
}

.tile-meta {
  margin-top: auto;
  font-size: var(--hud-body-sm);
  color: var(--hud-text-mute);
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tile-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  background: var(--hud-panel);
  backdrop-filter: blur(20px);
  border: 1px solid var(--hud-border);
  border-radius: var(--hud-radius-card);
  box-shadow: var(--hud-glow);
  position: relative;
  overflow: hidden;
}

.tile-panel::before {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background:
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left top / 16px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) left top / 2px 16px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right bottom / 16px 2px no-repeat,
    linear-gradient(var(--hud-cyan), var(--hud-cyan)) right bottom / 2px 16px no-repeat;
}

.tile-chart {
  flex: 1;
  min-height: 0;
}

.tile-list {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.activity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--hud-border-faint);
  font-size: var(--hud-body-sm);
}

.activity-row:last-child {
  border-bottom: none;
}

.activity-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--hud-text);
}

.activity-time {
  color: var(--hud-text-mute);
  flex: 0 0 auto;
}

@media (max-width: 1200px) {
  .workspace {
    height: auto;
    overflow: visible;
  }

  .bento {
    grid-template-columns: repeat(6, minmax(0, 1fr));
    grid-template-rows: none;
    height: auto;
  }

  .span-3 {
    grid-column: span 3;
  }

  .span-4 {
    grid-column: span 3;
  }

  .span-8 {
    grid-column: span 6;
  }

  .tile-panel {
    min-height: 260px;
  }
}

@media (max-width: 720px) {
  .bento {
    grid-template-columns: minmax(0, 1fr);
  }

  .span-3,
  .span-4,
  .span-8 {
    grid-column: span 1;
  }
}
</style>