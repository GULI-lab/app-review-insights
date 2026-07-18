/* ============================================================
   数据局限性报告组件
   展示数据集的已知局限和影响
   ============================================================ */
import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getLimitations } from '@/api/client'
import type { Limitation } from '@/types'

interface LimitationsViewProps {
  taskId: string
}

const categoryLabels: Record<string, string> = {
  coverage: '覆盖范围',
  timeliness: '时效性',
  language: '语言',
  sampling: '采样偏差',
  feed: '数据源限制',
}

const categoryIcons: Record<string, string> = {
  coverage: '📊',
  timeliness: '⏰',
  language: '🌐',
  sampling: '🎯',
  feed: '📡',
}

export function LimitationsView({ taskId }: LimitationsViewProps) {
  const [items, setItems] = useState<Limitation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getLimitations(taskId).then(setItems).finally(() => setLoading(false))
  }, [taskId])

  if (loading) return <div className="text-center py-8 text-gray-400">加载中...</div>

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <h4 className="text-sm font-bold mb-1">数据集局限性说明</h4>
        <p className="text-xs text-gray-400 mb-4">
          以下局限性由系统自动标注，帮助评估分析结论的可靠程度
        </p>

        {items.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">暂无局限性数据</p>
        ) : (
          <div className="space-y-3">
            {items.map((lim, idx) => (
              <div key={idx} className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-start gap-3">
                  <span className="text-lg">{categoryIcons[lim.category] || '📌'}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-gray-700">
                        {categoryLabels[lim.category] || lim.category}
                      </span>
                      {lim.is_actionable && (
                        <Badge variant="outline" className="text-blue-500 text-xs">可改善</Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-600">{lim.description}</p>
                    <p className="text-xs text-gray-400 mt-1">影响：{lim.impact}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5 bg-blue-50 border-blue-200">
        <h4 className="text-sm font-bold mb-1 text-blue-700">数据采集说明</h4>
        <p className="text-xs text-blue-600 leading-relaxed">
          评论数据通过 Apple 官方 RSS Feed API 采集（美区 App Store），
          无需爬虫或逆向工程。RSS 仅返回最近评论，内容可能被截断，
          超过 10 页后分页不稳定。系统在运行时会自动标注这些局限性。
        </p>
      </Card>
    </div>
  )
}
