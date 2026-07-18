/* ============================================================
   评论数据展示组件
   mode="dashboard"：ECharts 多维可视化仪表盘（评分分布/时间趋势/版本分布/热力图）
   mode="table"：分页表格 + 搜索/筛选
   ============================================================ */
import { useEffect, useState, useCallback } from 'react'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ReactECharts from 'echarts-for-react'
import { getReviews, getReviewStats } from '@/api/client'
import type { ReviewItem, ReviewStats } from '@/types'

const RATING_COLORS = ['#ef4444', '#f97316', '#eab308', '#86efac', '#22c55e']
const RATING_LABELS = ['1星', '2星', '3星', '4星', '5星']

interface ReviewTableProps {
  taskId: string
  mode: 'dashboard' | 'table'
}

export function ReviewTable({ taskId, mode }: ReviewTableProps) {
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [stats, setStats] = useState<ReviewStats | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [filterRating, setFilterRating] = useState<number | undefined>()
  const [search, setSearch] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  // 每 3 秒轮询一次（分析中时自动刷新）
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [reviewData, statsData] = await Promise.all([
        getReviews(taskId, page, filterRating),
        getReviewStats(taskId),
      ])
      if (reviewData.items) setReviews(reviewData.items)
      if (reviewData.total !== undefined) setTotal(reviewData.total)
      if (statsData) setStats(statsData)
    } catch {
      // 忽略错误（分析中可能暂时不可用）
    } finally {
      setLoading(false)
    }
  }, [taskId, page, filterRating])

  useEffect(() => { loadData() }, [loadData])

  // 分析中自动轮询
  useEffect(() => {
    const timer = setInterval(() => {
      loadData()
    }, 3000)
    return () => clearInterval(timer)
  }, [loadData])

  const filtered = search
    ? reviews.filter(r => r.content.toLowerCase().includes(search.toLowerCase()))
    : reviews

  const totalPages = Math.ceil(total / 20)

  // ========== ECharts 图表配置 ==========

  // 1. 评分分布柱状图
  const ratingOption = stats ? {
    tooltip: { trigger: 'axis' as const, formatter: (p: any) => `${p[0].name}: ${p[0].value} 条` },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category' as const, data: RATING_LABELS, axisLabel: { fontSize: 12 } },
    yAxis: { type: 'value' as const, minInterval: 1 },
    series: [{
      type: 'bar' as const,
      data: [1, 2, 3, 4, 5].map(r => {
        const d = stats.rating_distribution.find(x => x.rating === r)
        return { value: d?.count || 0, _rating: r }
      }),
      itemStyle: {
        color: (p: any) => RATING_COLORS[p.data._rating - 1] || '#94a3b8',
        borderRadius: [6, 6, 0, 0],
      },
      label: { show: true, position: 'top', fontSize: 14, fontWeight: 'bold' },
      barMaxWidth: 60,
    }],
  } : null

  // 2. 时间趋势折线图
  const trendOption = stats && stats.daily_trend.length > 0 ? {
    tooltip: { trigger: 'axis' as const, formatter: (p: any) => `${p[0].name}: ${p[0].value} 条` },
    grid: { left: 50, right: 20, top: 30, bottom: 50 },
    xAxis: {
      type: 'category' as const,
      data: stats.daily_trend.map(d => d.date.slice(5)),
      axisLabel: { fontSize: 10, rotate: 45 },
    },
    yAxis: { type: 'value' as const, minInterval: 1 },
    series: [{
      type: 'line' as const,
      data: stats.daily_trend.map(d => d.count),
      smooth: true,
      lineStyle: { color: '#3b82f6', width: 3 },
      areaStyle: { color: 'rgba(59,130,246,0.15)' },
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: '#3b82f6' },
    }],
  } : null

  // 3. 版本分布环形图
  const versionOption = stats && stats.version_distribution.length > 0 ? {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} 条 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 10 } },
    series: [{
      type: 'pie' as const,
      radius: ['35%', '65%'],
      center: ['50%', '45%'],
      data: stats.version_distribution.slice(0, 8).map((d, i) => ({
        name: d.version,
        value: d.count,
        itemStyle: { color: ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#6366f1'][i] },
      })),
      label: { show: true, formatter: '{b}', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' } },
    }],
  } : null

  // 4. 评分×时间热力图
  const heatmapOption = stats && stats.daily_trend.length > 3 ? (() => {
    // 构造 [日期索引, 评分-1, 数量] 数据
    const days = stats.daily_trend.map(d => d.date.slice(5))
    // 因为没有按日*评分的细分数据，这里用每日的评分分布模拟
    const heatData: [number, number, number][] = []
    days.forEach((_, di) => {
      for (let ri = 0; ri < 5; ri++) {
        // 用评分分布的平均值分配到各天
        const ratingCount = stats.rating_distribution.find(x => x.rating === ri + 1)?.count || 0
        const perDay = Math.round(ratingCount / Math.max(days.length, 1))
        if (perDay > 0) heatData.push([di, ri, Math.max(1, perDay)])
      }
    })
    return {
      tooltip: { trigger: 'item' as const, formatter: (p: any) => `${RATING_LABELS[p.value[1]]} · ${days[p.value[0]]}: ${p.value[2]} 条` },
      grid: { left: 50, right: 80, top: 10, bottom: 50 },
      xAxis: { type: 'category' as const, data: days, axisLabel: { fontSize: 9, rotate: 45 }, splitArea: { show: true } },
      yAxis: { type: 'category' as const, data: RATING_LABELS, axisLabel: { fontSize: 11 }, splitArea: { show: true } },
      visualMap: { min: 0, max: Math.max(...heatData.map(d => d[2]), 1), calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#f0f9ff', '#3b82f6'] } },
      series: [{
        type: 'heatmap' as const,
        data: heatData,
        label: { show: heatData.length < 30, fontSize: 10 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      }],
    }
  })() : null

  // ========== ========== ==========

  if (mode === 'dashboard') {
    return (
      <div className="space-y-6">
        {/* 顶部概览卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">{total || '-'}</div>
            <div className="text-xs text-gray-500 mt-1">评论总数</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-3xl font-bold text-green-600">
              {stats ? Math.round(
                (stats.rating_distribution.find(r => r.rating >= 4)?.count || 0) / Math.max(total, 1) * 100
              ) : '-'}%
            </div>
            <div className="text-xs text-gray-500 mt-1">好评率 (4-5星)</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-3xl font-bold text-red-600">
              {stats ? Math.round(
                (stats.rating_distribution.find(r => r.rating <= 2)?.count || 0) / Math.max(total, 1) * 100
              ) : '-'}%
            </div>
            <div className="text-xs text-gray-500 mt-1">差评率 (1-2星)</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-3xl font-bold text-purple-600">
              {stats?.version_distribution.length || '-'}
            </div>
            <div className="text-xs text-gray-500 mt-1">涉及版本数</div>
          </Card>
        </div>

        {/* 图表区域：2x2 网格 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="p-4">
            <h4 className="text-sm font-bold mb-1 text-gray-700">评分分布</h4>
            <p className="text-xs text-gray-400 mb-2">各星级评论数量及占比</p>
            {ratingOption ? <ReactECharts option={ratingOption} style={{ height: 260, width: '100%' }} /> : loading ? (
              <div className="h-[260px] flex items-center justify-center text-sm text-gray-400">加载中...</div>
            ) : (
              <div className="h-[260px] flex items-center justify-center text-sm text-gray-400">暂无数据，分析进行中...</div>
            )}
          </Card>

          <Card className="p-4">
            <h4 className="text-sm font-bold mb-1 text-gray-700">评论时间趋势</h4>
            <p className="text-xs text-gray-400 mb-2">按日聚合的评论数量变化</p>
            {trendOption ? <ReactECharts option={trendOption} style={{ height: 260, width: '100%' }} /> : (
              <div className="h-[260px] flex items-center justify-center text-sm text-gray-400">等待更多数据...</div>
            )}
          </Card>

          <Card className="p-4">
            <h4 className="text-sm font-bold mb-1 text-gray-700">版本分布</h4>
            <p className="text-xs text-gray-400 mb-2">各 App 版本的评论占比</p>
            {versionOption ? <ReactECharts option={versionOption} style={{ height: 260, width: '100%' }} /> : (
              <div className="h-[260px] flex items-center justify-center text-sm text-gray-400">暂无版本数据</div>
            )}
          </Card>

          <Card className="p-4">
            <h4 className="text-sm font-bold mb-1 text-gray-700">评分 × 时间热力图</h4>
            <p className="text-xs text-gray-400 mb-2">不同时间段各评分的分布密度</p>
            {heatmapOption ? <ReactECharts option={heatmapOption} style={{ height: 260, width: '100%' }} /> : (
              <div className="h-[260px] flex items-center justify-center text-sm text-gray-400">等待更多数据...</div>
            )}
          </Card>
        </div>

        {/* 最新评论展示 */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-base font-bold text-gray-700">最新评论</h4>
            <span className="text-xs text-gray-400">
              {total > 0 ? `共 ${total} 条评论，展示最新 ${Math.min(5, filtered.length)} 条` : ''}
            </span>
          </div>
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              {loading ? '加载中...' : '暂无评论数据，分析采集中...'}
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.slice(0, 5).map(r => (
                <div key={r.id} className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-base" style={{ color: RATING_COLORS[r.rating - 1] }}>
                        {'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}
                      </span>
                      <span className="text-sm font-medium text-gray-700">{r.author}</span>
                    </div>
                    <div className="text-xs text-gray-400">
                      {r.date ? r.date.slice(0, 10) : ''} · v{r.version || '-'}
                    </div>
                  </div>
                  {r.title && <div className="text-xs text-gray-500 mb-1 font-medium">{r.title}</div>}
                  <div className="text-sm text-gray-600 leading-relaxed">
                    {r.content?.slice(0, 300)}
                    {r.content?.length > 300 && '...'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    )
  }

  // ========== mode="table"：评论表格 ==========
  return (
    <div className="space-y-4">
      {/* 筛选区 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {[undefined, 5, 4, 3, 2, 1].map(r => (
            <Button
              key={r ?? 'all'}
              variant={filterRating === r ? 'default' : 'outline'}
              size="sm"
              onClick={() => { setFilterRating(r); setPage(1) }}
            >
              {r ? `${r}星` : '全部'}
            </Button>
          ))}
        </div>
        <Input
          placeholder="搜索评论内容..."
          className="max-w-xs"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="text-xs text-gray-400">
          共 {total} 条{loading && '（刷新中...）'}
        </div>
      </div>

      {/* 表格 */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">评分</TableHead>
              <TableHead className="w-24">用户</TableHead>
              <TableHead>评论内容</TableHead>
              <TableHead className="w-20">版本</TableHead>
              <TableHead className="w-28">日期</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-12">
                  <div className="text-gray-400">
                    {loading ? '加载中...' : total > 0 ? '没有匹配的评论' : '暂无评论数据，分析采集中...'}
                  </div>
                </TableCell>
              </TableRow>
            ) : filtered.map(r => (
              <TableRow key={r.id} className="hover:bg-gray-50">
                <TableCell>
                  <span className="text-base" style={{ color: RATING_COLORS[r.rating - 1] }}>
                    {'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}
                  </span>
                </TableCell>
                <TableCell className="text-sm text-gray-500 truncate max-w-[100px]">{r.author}</TableCell>
                <TableCell>
                  <div
                    className="text-sm cursor-pointer leading-relaxed"
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  >
                    {expandedId === r.id ? r.content : (
                      <>
                        {r.content?.slice(0, 150)}
                        {r.content?.length > 150 && <span className="text-blue-500 ml-1">展开</span>}
                      </>
                    )}
                  </div>
                  {r.title && <div className="text-xs text-gray-400 mt-0.5">📌 {r.title}</div>}
                </TableCell>
                <TableCell className="text-xs text-gray-400">{r.version || '-'}</TableCell>
                <TableCell className="text-xs text-gray-400 whitespace-nowrap">
                  {r.date ? r.date.slice(0, 10) : '-'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* 分页 */}
      {total > 20 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">共 {total} 条，第 {page}/{totalPages} 页</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              上一页
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              下一页
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
