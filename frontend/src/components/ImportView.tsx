/* ============================================================
   数据导入组件
   支持上传 JSON / CSV 文件，字段自动映射，无需先创建分析任务
   ============================================================ */
import { useState, useRef, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface ImportViewProps {
  onImportSuccess?: (count: number, taskId?: string) => void
}

interface TaskOption {
  id: string
  app_url: string
  status: string
  goal: string
  created_at: string | null
}

export function ImportView({ onImportSuccess }: ImportViewProps) {
  const [taskId, setTaskId] = useState('')
  const [taskMode, setTaskMode] = useState<'select' | 'new'>('select')
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<{ imported: number; task_id: string } | null>(null)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState<TaskOption[]>([])
  const [loadingTasks, setLoadingTasks] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (taskMode === 'select') {
      fetchTasks()
    }
  }, [taskMode])

  const fetchTasks = async () => {
    setLoadingTasks(true)
    try {
      const res = await fetch('/api/tasks')
      if (res.ok) {
        setTasks(await res.json())
      }
    } catch {
      // ignore
    } finally {
      setLoadingTasks(false)
    }
  }

  const handleImport = async () => {
    if (!file) return

    setImporting(true)
    setError('')
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      if (taskMode === 'select' && taskId.trim()) {
        formData.append('task_id', taskId.trim())
      }

      const res = await fetch('/api/import', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        setError(err.detail || '导入失败')
        return
      }

      const data = await res.json()
      setResult(data)
      onImportSuccess?.(data.imported, data.task_id)
    } catch (e: any) {
      setError(e.message || '网络错误')
    } finally {
      setImporting(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setResult(null)
      setError('')
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-6">
        <h3 className="text-base font-bold mb-1">导入评论数据</h3>
        <p className="text-xs text-gray-400 mb-4">
          将外部 JSON/CSV 评论数据导入系统，与 RSS 采集的数据合并，参与 AI 分析和可视化展示
        </p>

        <div className="space-y-4">
          {/* 选择已有任务 or 创建新任务 */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <label className="text-sm font-medium">关联任务</label>
              <div className="flex bg-gray-100 rounded p-0.5 text-xs">
                <button
                  className={`px-2 py-0.5 rounded ${taskMode === 'select' ? 'bg-white shadow-sm' : ''}`}
                  onClick={() => setTaskMode('select')}
                >
                  选择已有任务
                </button>
                <button
                  className={`px-2 py-0.5 rounded ${taskMode === 'new' ? 'bg-white shadow-sm' : ''}`}
                  onClick={() => setTaskMode('new')}
                >
                  自动创建新任务
                </button>
              </div>
            </div>

            {taskMode === 'select' ? (
              <div>
                <Select value={taskId} onValueChange={(v: string | null) => v && setTaskId(v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={loadingTasks ? '加载中...' : '选择已有任务（加载评论到该任务）'} />
                  </SelectTrigger>
                  <SelectContent>
                    {tasks.map(t => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.id.slice(0, 8)}... — {t.app_url.slice(0, 30)} ({t.status})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <button className="text-xs text-blue-500 mt-1 hover:underline" onClick={fetchTasks}>
                  刷新任务列表
                </button>
                {taskId && (
                  <p className="text-xs text-gray-400 mt-1">数据将导入到该任务，与原有评论合并</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-400">导入时会自动创建新分析任务</p>
            )}
          </div>

          {/* 文件上传 */}
          <div>
            <label className="text-sm font-medium mb-1 block">选择文件</label>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.csv"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">
              JSON 格式： {'[{ "content": "...", "rating": 5 }]'} 或 {'{ "reviews": [...] }'}
              <br />
              CSV 格式：需包含 `content` 和 `rating` 列
            </p>
          </div>

          {/* 字段映射说明 */}
          <div className="p-3 bg-gray-50 rounded text-xs text-gray-500">
            <span className="font-medium">自动字段映射：</span>
            content(评论内容) / rating(评分 1-5) / author(用户) / title(标题) / version(版本) / date(日期)
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center gap-3">
            <Button onClick={handleImport} disabled={importing || !file || (taskMode === 'select' && !taskId)}>
              {importing ? '导入中...' : '开始导入'}
            </Button>
            {file && <span className="text-sm text-gray-500">已选择: {file.name}</span>}
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-600">
              ⚠ {error}
            </div>
          )}

          {/* 导入结果 */}
          {result && (
            <div className="p-4 bg-green-50 border border-green-200 rounded">
              <div className="flex items-center gap-2">
                <span className="text-green-600 font-semibold text-lg">✓</span>
                <span className="text-sm text-green-700">
                  成功导入 <strong>{result.imported}</strong> 条评论
                  {taskMode === 'new' && <>，任务 ID：<code className="bg-green-100 px-1 rounded font-bold">{result.task_id}</code></>}
                </span>
              </div>
              <p className="text-xs text-green-600 mt-1">
                {taskMode === 'new'
                  ? <>导入成功，正在自动启动 AI 分析...</>
                  : '导入的数据已合并到该任务中，可刷新查看'}
              </p>
            </div>
          )}
        </div>
      </Card>

      {/* 数据格式示例 */}
      <Card className="p-5">
        <h4 className="text-sm font-bold mb-2">数据格式示例</h4>
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div className="p-3 bg-gray-50 rounded">
            <span className="font-medium text-gray-600">JSON 格式：</span>
            <pre className="mt-1 text-gray-500">{`[
  {
    "review_id": "r12345",
    "content": "非常好用的 App",
    "rating": 5,
    "author": "user123",
    "version": "8.4.26",
    "date": "2026-07-01"
  }
]`}</pre>
          </div>
          <div className="p-3 bg-gray-50 rounded">
            <span className="font-medium text-gray-600">CSV 格式：</span>
            <pre className="mt-1 text-gray-500">{`content,rating,author,version,date
非常好用的 App,5,user123,8.4.26,2026-07-01
经常闪退,1,user456,8.4.25,2026-07-02`}</pre>
          </div>
        </div>
      </Card>
    </div>
  )
}
