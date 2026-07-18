import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getTestCases } from '@/api/client'
import type { TestCase } from '@/types'

interface TestCasesViewProps {
  taskId: string
}

export function TestCasesView({ taskId }: TestCasesViewProps) {
  const [cases, setCases] = useState<TestCase[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTestCases(taskId).then(setCases).finally(() => setLoading(false))
  }, [taskId])

  if (loading) return <div className="text-center py-8 text-gray-400">加载中...</div>

  if (cases.length === 0) {
    return (
      <Card className="p-8 text-center text-gray-400">
        暂无测试用例
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {cases.map(tc => (
        <Card key={tc.id} className="p-5">
          <div className="flex items-start gap-2 mb-3">
            <div className="flex-1">
              <h4 className="font-semibold text-sm">{tc.description}</h4>
            </div>
            <Badge variant={tc.verified ? 'default' : 'secondary'}>
              {tc.verified ? '已验证' : '待验证'}
            </Badge>
          </div>
          {tc.steps.length > 0 && (
            <div className="mb-2">
              <span className="text-xs text-gray-400 font-medium">测试步骤：</span>
              <ol className="list-decimal list-inside text-sm text-gray-600 mt-1 space-y-1">
                {tc.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}
          <div className="text-sm">
            <span className="text-xs text-gray-400 font-medium">预期结果：</span>
            <span className="text-gray-600">{tc.expected}</span>
          </div>
          {tc.source_review_ids.length > 0 && (
            <div className="mt-2 text-xs text-gray-400">
              关联评论 ID: {tc.source_review_ids.join(', ')}
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}
