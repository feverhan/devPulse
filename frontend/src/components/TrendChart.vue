<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ data: Array<{ date: string; count: number }> }>()

const container = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

function render() {
  if (!container.value) return
  if (!chart) chart = echarts.init(container.value)
  const dates = props.data.map((item) => item.date.slice(5))
  const counts = props.data.map((item) => item.count)
  chart.setOption(
    {
      grid: { left: 4, right: 10, top: 16, bottom: 4, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(6, 182, 212, 0.5)',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: '#e5f2ff', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
        axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(6, 182, 212, 0.08)' } },
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: 'rgba(6, 182, 212, 0.3)' } },
        axisTick: { show: false },
        axisLabel: { color: '#93a9c4', fontSize: 10, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: 'rgba(6, 182, 212, 0.12)' } },
        axisLabel: { color: '#93a9c4', fontSize: 10 },
      },
      series: [
        {
          type: 'bar',
          data: counts,
          barMaxWidth: 16,
          itemStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: '#22d3ee' },
                { offset: 1, color: 'rgba(6, 182, 212, 0.35)' },
              ],
            },
            shadowBlur: 10,
            shadowColor: 'rgba(6, 182, 212, 0.6)',
            borderRadius: [2, 2, 0, 0],
          },
        },
      ],
    },
    true,
  )
}

onMounted(async () => {
  await nextTick()
  render()
  if (container.value) {
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(container.value)
  }
})

watch(() => props.data, render, { deep: true })

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="container" style="width: 100%; height: 100%; min-height: 150px" />
</template>