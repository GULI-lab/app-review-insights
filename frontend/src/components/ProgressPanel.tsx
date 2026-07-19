/* ============================================================
   进度面板：实时显示分析流水线各阶段状态
   包含：进度条、7 阶段卡片、采集实时评分分布
   ============================================================ */
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { StageCard } from './StageCard'
import { StageResult } from './StageResult'
import ReactECharts from 'echarts-for-react'
import type { AnalysisTask, SSEEvent } from '@/types'

interface ProgressPanelProps {
  task: AnalysisTask
  events: SSEEvent[]
  connected: boolean
}

export function ProgressPanel({ task, events, connected }: ProgressPanelProps) {
  const stages = ['scoping', 'collecting', 'cleaning', 'analyzing', 'planning', 'testgen', 'done']

  // 从 events 推断每个阶段的状态
  const stageStatus: Record<string, 'pending' | 'running' | 'completed' | 'failed'> = {}
  for (const s of stages) stageStatus[s] = 'pending'

  for (const s of stages) {
    const hasStart = events.some(e => e.event === 'stage_start' && e.stage === s)
    const hasComplete = events.some(e => e.event === 'stage_complete' && e.stage === s)
    const hasError = events.some(e => e.event === 'stage_error' && e.stage === s)
    if (hasError) {
      stageStatus[s] = 'failed'
    } else if (hasComplete) {
      stageStatus[s] = 'completed'
    } else if (hasStart) {
      stageStatus[s] = 'running'
    }
  }

  // 任务最终完成 → 所有没状态的阶段补 completed
  if (task.status === 'completed') {
    for (const s of stages) {
      if (stageStatus[s] === 'pending') stageStatus[s] = 'completed'
    }
  }

  // ---- 采集阶段实时数据 ----
  const collectEvents = events.filter(e => e.stage === 'collecting' && e.data?.rating_distribution)
  const latestCollect = collectEvents[collectEvents.length - 1]
  const ratingDist = latestCollect?.data?.rating_distribution || []
  const currentCount = latestCollect?.data?.count || 0

  // 每阶段完成后的产出数据
  const stageResults = {
    cleaning: events.find(e => e.event === 'stage_complete' && e.stage === 'cleaning')?.data || null,
    analyzing: events.find(e => e.event === 'stage_complete' && e.stage === 'analyzing')?.data || null,
    planning: events.find(e => e.event === 'stage_complete' && e.stage === 'planning')?.data || null,
    collecting: events.find(e => e.event === 'stage_complete' && e.stage === 'collecting')?.data || null,
  }

  // 实时评分分布柱状图
  const ratingOption = {
    tooltip: { trigger: 'axis' as const, formatter: (params: any) => `${params[0].name}: ${params[0].value} 条` },
    grid: { left: 40, right: 10, top: 10, bottom: 25 },
    xAxis: { type: 'category' as const, data: ['1星', '2星', '3星', '4星', '5星'], axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' as const, minInterval: 1 },
    series: [{
      type: 'bar' as const,
      data: [1, 2, 3, 4, 5].map(r => {
        const d = ratingDist.find((x: any) => x.rating === r)
        return d?.count || 0
      }),
      itemStyle: {
        color: (p: any) => ['#ef4444', '#f97316', '#eab308', '#86efac', '#22c55e'][p.dataIndex],
        borderRadius: [4, 4, 0, 0],
      },
      label: { show: true, position: 'top', fontSize: 11, fontWeight: 'bold' },
    }],
  }

  // ---- 采集阶段实时趋势（每页数据变化） ----
  const trendData = collectEvents.map((e, i) => ({
    page: e.data?.page || i + 1,
    count: e.data?.count || 0,
  }))
  const trendOption = trendData.length > 1 ? {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 40, right: 10, top: 10, bottom: 25 },
    xAxis: { type: 'category' as const, data: trendData.map(d => `第${d.page}页`), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'line' as const,
      data: trendData.map(d => d.count),
      smooth: true,
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: { color: 'rgba(59,130,246,0.1)' },
      symbol: 'circle',
      symbolSize: 6,
    }],
  } : null

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold">分析进度</h3>
        <div className="flex items-center gap-3">
          {currentCount > 0 && (
            <span className="text-sm text-gray-500">已采集 {currentCount} 条评论</span>
          )}
          <span className={`text-xs ${connected ? 'text-green-500' : 'text-red-500'}`}>
            {connected ? '● 实时连接' : '○ 重连中...'}
          </span>
        </div>
      </div>
      <p className="text-xs text-gray-400 mb-3">数据来源：Apple RSS Feed（美区 App Store）</p>

      {/* 进度条 */}
      <Progress value={task.progress_pct} className="mb-4 h-2" />

      {/* 错误提示 */}
      {task.status === 'failed' && task.error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          ⚠ 分析失败：{task.error}
        </div>
      )}

      {/* 阶段卡片 */}
      <div className="space-y-2 mb-4">
        {stages.map(s => (
          <StageCard key={s} name={s} status={stageStatus[s]} />
        ))}
      </div>

      {/* 各阶段产出摘要 */}
      {stageStatus.cleaning === 'completed' && stageResults.cleaning && (
        <StageResult stage="cleaning" data={stageResults.cleaning} />
      )}
      {stageStatus.analyzing === 'completed' && stageResults.analyzing && (
        <StageResult stage="analyzing" data={stageResults.analyzing} />
      )}
      {stageStatus.planning === 'completed' && stageResults.planning && (
        <StageResult stage="planning" data={stageResults.planning} />
      )}

      {/* 采集阶段实时图表 */}
      {(stageStatus.collecting === 'running' || stageStatus.collecting === 'completed') && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="text-sm font-medium mb-2 text-gray-600">评分分布</h4>
            {ratingDist.length > 0 ? (
              <ReactECharts option={ratingOption} style={{ height: 220 }} />
            ) : (
              <p className="text-sm text-gray-400 text-center py-8">等待采集数据...</p>
            )}
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <h4 className="text-sm font-medium mb-2 text-gray-600">采集趋势</h4>
            {trendOption ? (
              <ReactECharts option={trendOption} style={{ height: 220 }} />
            ) : (
              <p className="text-sm text-gray-400 text-center py-8">等待更多数据...</p>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
