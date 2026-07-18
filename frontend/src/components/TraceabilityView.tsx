/* ============================================================
   溯源验证组件
   展示 Review→Finding→Requirement→TestCase 链验证结果
   ============================================================ */
import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getTraceability } from '@/api/client'
import type { TraceabilityResult } from '@/types'

interface TraceabilityViewProps {
  taskId: string
}

export function TraceabilityView({ taskId }: TraceabilityViewProps) {
  const [data, setData] = useState<TraceabilityResult | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTraceability(taskId).then(setData).finally(() => setLoading(false))
  }, [taskId])

  if (loading) return <div className="text-center py-8 text-gray-400">加载中...</div>
  if (!data) return <Card className="p-8 text-center text-gray-400">暂无溯源数据</Card>

  return (
    <div className="space-y-4">
      {/* 概览卡片 */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-blue-600">{data.checked}</div>
          <div className="text-xs text-gray-500 mt-1">已检查</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-amber-500">{data.pending}</div>
          <div className="text-xs text-gray-500 mt-1">待审核</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-green-600">{data.checked - data.pending}</div>
          <div className="text-xs text-gray-500 mt-1">验证通过</div>
        </Card>
      </div>

      {/* 验证链说明 */}
      <Card className="p-4">
        <h4 className="text-sm font-bold mb-2">验证链</h4>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Badge>用户评论</Badge>
          <span className="text-gray-300">→</span>
          <Badge>分析发现</Badge>
          <span className="text-gray-300">→</span>
          <Badge>PRD 需求</Badge>
          <span className="text-gray-300">→</span>
          <Badge>测试用例</Badge>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          每个需求必须至少关联 1 个 Finding，每个 Finding 必须至少被 2 条评论支撑
        </p>
      </Card>

      {/* 待审核项 */}
      {data.pending_items.length > 0 && (
        <div>
          <h4 className="text-sm font-bold mb-2 text-amber-600">待审核项（{data.pending_items.length}）</h4>
          <div className="space-y-2">
            {data.pending_items.map(item => (
              <Card key={item.id} className="p-4 border-amber-200 bg-amber-50">
                <div className="flex items-start justify-between">
                  <div>
                    <h5 className="text-sm font-semibold">{item.topic}</h5>
                    <p className="text-xs text-amber-700 mt-1">
                      ⚠ {item.downgrade_reason || '支撑不足'}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-amber-600">
                    {item.confidence}
                  </Badge>
                </div>
                <p className="text-xs text-gray-500 mt-1">支撑样本数: {item.sample_count}</p>
              </Card>
            ))}
          </div>
        </div>
      )}

      {data.pending === 0 && (
        <Card className="p-6 text-center text-green-600 text-sm">
          ✓ 所有 Finding 均满足溯源验证要求（每条至少 2 条评论支撑）
        </Card>
      )}
    </div>
  )
}
