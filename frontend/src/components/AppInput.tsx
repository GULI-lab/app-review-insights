import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface AppInputProps {
  onStart: (url: string, goal: string, maxReviews: number, sort: string) => void
  loading: boolean
}

export function AppInput({ onStart, loading }: AppInputProps) {
  const [url, setUrl] = useState('')
  const [goal, setGoal] = useState('')
  const [maxReviews, setMaxReviews] = useState('200')
  const [sort, setSort] = useState('mostrecent')

  return (
    <Card className="p-6 mb-6">
      <h2 className="text-xl font-bold mb-4">App Store 评论分析</h2>
      <div className="space-y-4">
        {/* App Store 链接 */}
        <div>
          <label className="text-sm font-medium mb-1 block">App Store 链接</label>
          <Input
            placeholder="https://apps.apple.com/us/app/.../id839285684"
            value={url}
            onChange={e => setUrl(e.target.value)}
          />
        </div>

        {/* 分析目标 */}
        <div>
          <label className="text-sm font-medium mb-1 block">分析目标（可选）</label>
          <Textarea
            placeholder="例如：关注订阅转化和低评分评论"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            rows={2}
          />
        </div>

        {/* 采集选项 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">评论数量</label>
            <Input
              type="number"
              min={1}
              max={500}
              placeholder="默认 500 条"
              value={maxReviews}
              onChange={e => setMaxReviews(e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-1">最多 500 条（Apple RSS Feed 限制）</p>
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">排序方式</label>
            <Select value={sort} onValueChange={(v: string | null) => v && setSort(v)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mostrecent">最新评论</SelectItem>
                <SelectItem value="mosthelpful">最有帮助</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 提交按钮 */}
        <div className="flex items-center gap-3">
          <Button onClick={() => onStart(url, goal, Number(maxReviews), sort)} disabled={loading || !url.trim()}>
            {loading ? '分析中...' : '开始分析'}
          </Button>
          <span className="text-xs text-gray-400">
            数据来源：Apple RSS Feed（美区 App Store）
          </span>
        </div>
      </div>
    </Card>
  )
}
