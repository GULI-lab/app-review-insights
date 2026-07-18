/* ============================================================
   AI 分析发现展示组件
   展示每个 finding 的：置信度、描述、支撑评论ID、引文、矛盾证据
   ============================================================ */
import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getFindings } from '@/api/client'
import type { Finding } from '@/types'

interface FindingsViewProps {
  taskId: string
}

export function FindingsView({ taskId }: FindingsViewProps) {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFindings(taskId).then(setFindings).finally(() => setLoading(false))
  }, [taskId])

  if (loading) return <div className="text-center py-8 text-gray-400">加载中...</div>

  if (findings.length === 0) {
    return (
      <Card className="p-8 text-center text-gray-400">
        暂无分析发现，请先配置 DeepSeek API Key 后重新运行分析
      </Card>
    )
  }

  const badgeVariant: Record<string, 'default' | 'secondary' | 'outline'> = {
    high: 'default',
    medium: 'secondary',
    low: 'outline',
  }

  const confidenceLabel: Record<string, string> = {
    high: '高置信度',
    medium: '中置信度',
    low: '低置信度',
  }

  return (
    <div className="space-y-4">
      {findings.map(f => (
        <Card key={f.id} className="p-5">
          {/* 头部：主题 + 置信度 */}
          <div className="flex items-start gap-3 mb-2">
            <div className="flex-1">
              <h4 className="font-semibold">{f.topic}</h4>
              <p className="text-sm text-gray-600 mt-1">{f.description}</p>
            </div>
            <Badge variant={badgeVariant[f.confidence] || 'outline'}>
              {confidenceLabel[f.confidence] || f.confidence}
            </Badge>
          </div>

          {/* 元信息 */}
          <div className="flex flex-wrap gap-3 text-xs text-gray-400 mt-3">
            <span>支撑样本: <strong>{f.sample_count}</strong> 条评论</span>
            <span>来源: {f.is_model_generated ? 'AI 分析' : '统计'}</span>
            {f.is_statistical && <span className="text-blue-500">统计结论</span>}
            {f.was_downgraded && <span className="text-amber-500">⚠ 已降级: {f.downgrade_reason}</span>}
            {f.status === 'pending_review' && <Badge variant="outline" className="text-amber-500">待审核</Badge>}
          </div>

          {/* 支撑评论 ID */}
          {f.supporting_review_ids.length > 0 && (
            <div className="mt-3 text-xs text-gray-400">
              <span className="font-medium text-gray-500">支撑评论 ID: </span>
              {f.supporting_review_ids.slice(0, 10).join(', ')}
              {f.supporting_review_ids.length > 10 && ` 等 ${f.supporting_review_ids.length} 条`}
            </div>
          )}

          {/* 用户引文 */}
          {f.representative_excerpts.length > 0 && (
            <div className="mt-3 p-3 bg-gray-50 rounded text-sm text-gray-500">
              <span className="text-xs text-gray-400 font-medium">用户原声：</span>
              {f.representative_excerpts.slice(0, 4).map((ex, i) => (
                <p key={i} className="mt-1 italic">"{ex}"</p>
              ))}
            </div>
          )}

          {/* 矛盾证据 */}
          {f.contradicting_evidence.length > 0 && (
            <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded">
              <span className="text-xs font-medium text-amber-600">⚠ 存在 {f.contradicting_evidence.length} 条矛盾证据：</span>
              {f.contradicting_evidence.slice(0, 3).map((ev, i) => (
                <p key={i} className="text-xs text-amber-700 mt-1">• {typeof ev === 'string' ? ev : JSON.stringify(ev)}</p>
              ))}
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}
