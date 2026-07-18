import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getRequirements } from '@/api/client'
import type { Requirement } from '@/types'
import ReactMarkdown from 'react-markdown'

interface PrdViewProps {
  taskId: string
}

export function PrdView({ taskId }: PrdViewProps) {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getRequirements(taskId).then(setRequirements).finally(() => setLoading(false))
  }, [taskId])

  if (loading) return <div className="text-center py-8 text-gray-400">加载中...</div>

  if (requirements.length === 0) {
    return (
      <Card className="p-8 text-center text-gray-400">
        暂无 PRD，请先配置 DeepSeek API Key 后重新运行分析
      </Card>
    )
  }

  const versionColors: Record<string, string> = {
    v1: 'bg-green-100 text-green-700',
    v2: 'bg-blue-100 text-blue-700',
    v3: 'bg-purple-100 text-purple-700',
  }

  const priorityLabels: Record<string, string> = {
    p0: 'P0 紧急',
    p1: 'P1 重要',
    p2: 'P2 一般',
  }

  return (
    <div className="space-y-4">
      {requirements.map(req => (
        <Card key={req.id} className="p-5">
          <div className="flex items-start gap-3 mb-2">
            <div className="flex-1">
              <h4 className="font-semibold">{req.title}</h4>
            </div>
            <Badge className={versionColors[req.version] || ''}>
              {req.version?.toUpperCase()}
            </Badge>
            <Badge variant="secondary">{priorityLabels[req.priority] || req.priority}</Badge>
          </div>
          <div className="prose prose-sm max-w-none text-gray-600">
            <ReactMarkdown>{req.description}</ReactMarkdown>
          </div>
        </Card>
      ))}
    </div>
  )
}
