import { Badge } from '@/components/ui/badge'

interface StageCardProps {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

const stageLabels: Record<string, string> = {
  scoping: '目标解析',
  collecting: '数据采集',
  cleaning: '清洗裁剪',
  analyzing: 'AI 分析',
  planning: '证据评估与 PRD',
  done: '完成',
}

export function StageCard({ name, status }: StageCardProps) {
  const label = stageLabels[name] || name

  const statusConfig: Record<string, { icon: string; badge: string; badgeClass: string }> = {
    pending: { icon: '○', badge: '等待中', badgeClass: 'text-gray-400 border-gray-300' },
    running: { icon: '◌', badge: '进行中', badgeClass: 'text-blue-500 border-blue-300 animate-pulse' },
    completed: { icon: '✓', badge: '完成', badgeClass: 'bg-green-100 text-green-700 border-green-300' },
    failed: { icon: '✕', badge: '失败', badgeClass: 'bg-red-100 text-red-700 border-red-300' },
  }

  const cfg = statusConfig[status] || statusConfig.pending

  return (
    <div className="flex items-center gap-3 p-3 border rounded-lg bg-white">
      <span className={`text-lg font-bold ${status === 'running' ? 'text-blue-500' : status === 'completed' ? 'text-green-500' : status === 'failed' ? 'text-red-500' : 'text-gray-400'}`}>
        {cfg.icon}
      </span>
      <span className="flex-1 text-sm">{label}</span>
      <Badge variant="outline" className={cfg.badgeClass}>
        {cfg.badge}
      </Badge>
    </div>
  )
}
