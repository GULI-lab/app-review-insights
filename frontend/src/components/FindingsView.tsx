/* ============================================================
   AI 分析发现展示组件
   展示每个 finding 的：置信度、描述、支撑评论ID、引文、矛盾证据
   ============================================================ */
import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getFindings, getReviewById } from '@/api/client'
import type { Finding, ReviewItem } from '@/types'

interface FindingsViewProps {
  taskId: string
}

export function FindingsView({ taskId }: FindingsViewProps) {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)
  const [detailReview, setDetailReview] = useState<ReviewItem | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    getFindings(taskId).then(setFindings).finally(() => setLoading(false))
  }, [taskId])

  const openDetail = async (reviewId: string) => {
    setDetailLoading(true)
    setDetailReview(null)
    try {
      const data = await getReviewById(taskId, reviewId)
      setDetailReview(data)
    } catch {
      setDetailReview(null)
    } finally {
      setDetailLoading(false)
    }
  }

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
            {f.affected_versions && f.affected_versions.length > 0 && (
              <span>涉及版本: <strong>{f.affected_versions.join(', ')}</strong></span>
            )}
            <span>来源: {f.is_model_generated ? 'AI 分析' : '统计'}</span>
            {f.is_statistical && <span className="text-blue-500">统计结论</span>}
            {f.was_downgraded && <span className="text-amber-500">⚠ 已降级: {f.downgrade_reason}</span>}
            {f.status === 'pending_review' && <Badge variant="outline" className="text-amber-500">待审核</Badge>}
          </div>

          {/* 支撑评论 ID */}
          {f.supporting_review_ids.length > 0 && (
            <div className="mt-3 text-xs">
              <span className="font-medium text-gray-500">支撑评论 ID: </span>
              <div className="flex flex-wrap gap-1 mt-1">
                {f.supporting_review_ids.map((rid, i) => (
                  <button
                    key={i}
                    className="px-1.5 py-0.5 bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-800 rounded font-mono transition-colors cursor-pointer"
                    onClick={() => openDetail(rid)}
                    title="点击查看评论详情"
                  >
                    {rid}
                  </button>
                ))}
              </div>
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

      {/* 评论详情弹窗 */}
      {detailReview && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setDetailReview(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-gray-800">评论详情</h3>
              <button className="text-gray-400 hover:text-gray-600 text-xl" onClick={() => setDetailReview(null)}>✕</button>
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-xl" style={{ color: ['#ef4444', '#f97316', '#eab308', '#86efac', '#22c55e'][detailReview.rating - 1] }}>
                  {'★'.repeat(detailReview.rating)}{'☆'.repeat(5 - detailReview.rating)}
                </span>
                <span className="text-sm text-gray-500">{detailReview.author}</span>
                <span className="text-xs text-gray-400">v{detailReview.version || '-'}</span>
              </div>
              <div className="text-xs text-gray-400 font-mono bg-gray-50 px-2 py-1 rounded">
                ID: {detailReview.review_id}
              </div>
              {detailReview.title && (
                <div className="text-sm font-medium text-gray-700">{detailReview.title}</div>
              )}
              <div className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                {detailReview.content}
              </div>
              <div className="flex items-center justify-between text-xs text-gray-400 pt-2 border-t">
                <span>{detailReview.date ? detailReview.date.slice(0, 10) : '-'}</span>
                <span>来源: {detailReview.source}</span>
                {detailReview.quality_score != null && (
                  <span>质量分: {detailReview.quality_score}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {detailLoading && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg px-6 py-3 shadow-lg text-sm text-gray-600">加载中...</div>
        </div>
      )}
    </div>
  )
}
