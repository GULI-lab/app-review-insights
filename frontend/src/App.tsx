import { useState, useCallback, useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AppInput } from './components/AppInput'
import { ProgressPanel } from './components/ProgressPanel'
import { ReviewTable } from './components/ReviewTable'
import { FindingsView } from './components/FindingsView'
import { PrdView } from './components/PrdView'
import { TestCasesView } from './components/TestCasesView'
import { TraceabilityView } from './components/TraceabilityView'
import { LimitationsView } from './components/LimitationsView'
import { ImportView } from './components/ImportView'
import { useSSE } from './hooks/useSSE'
import { startAnalysis, getTask, deleteTask } from './api/client'
import type { AnalysisTask } from './types'

interface TaskOption {
  id: string
  app_url: string
  goal: string
  status: string
  current_stage: string
  created_at: string | null
}

export default function App() {
  const [task, setTask] = useState<AnalysisTask | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('dashboard')
  const { events, connected } = useSSE({ taskId: task?.id ?? null })

  // 历史任务选择
  const [taskList, setTaskList] = useState<TaskOption[]>([])
  const [showTaskPicker, setShowTaskPicker] = useState(false)

  // 加载历史任务列表
  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch('/api/tasks')
      if (res.ok) {
        setTaskList(await res.json())
      }
    } catch { /* ignore */ }
  }, [])

  // 首次加载任务列表
  useEffect(() => { fetchTasks() }, [fetchTasks])

  const handleStart = useCallback(async (url: string, goal: string, maxReviews: number, sort: string) => {
    setLoading(true)
    try {
      const t = await startAnalysis(url, goal, maxReviews, sort)
      setTask(t)
      setActiveTab('dashboard')
    } catch (err: any) {
      alert('启动分析失败: ' + (err?.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }, [])

  // 删除历史任务
  const handleDeleteTask = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('确定删除此任务及其所有数据？')) return
    try {
      await deleteTask(taskId)
      setTaskList(prev => prev.filter(t => t.id !== taskId))
      if (task?.id === taskId) setTask(null)
    } catch { /* ignore */ }
  }

  // 选择历史任务
  const handleSelectTask = useCallback(async (taskId: string) => {
    try {
      const t = await getTask(taskId)
      setTask(t)
      setActiveTab('dashboard')
      setShowTaskPicker(false)
    } catch { /* ignore */ }
  }, [])

  // 轮询任务状态（检测 running→completed 转换）
  useEffect(() => {
    if (!task || task.status !== 'running') return
    const timer = setInterval(async () => {
      try {
        const updated = await getTask(task.id)
        if (updated.status !== task.status) {
          setTask(updated)
        }
      } catch { /* ignore */ }
    }, 3000)
    return () => clearInterval(timer)
  }, [task])

  const isRunning = task && (task.status === 'running' || task.status === 'pending')
  const isCompleted = task?.status === 'completed'
  const isFailed = task?.status === 'failed'
  const showTabs = task && (isRunning || isCompleted || isFailed)

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="max-w-6xl mx-auto p-4 md:p-8">
        {/* 标题 + 操作栏 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">App Review Insights</h1>
            <p className="text-sm text-gray-500 mt-1">App Store 评论智能分析平台</p>
          </div>
          <div className="flex items-center gap-3">
            {task && (
              <span className="text-xs text-gray-400">
                当前任务: {task.id.slice(0, 8)}...
                <span className={`ml-1 font-medium ${isRunning ? 'text-blue-500' : isCompleted ? 'text-green-500' : 'text-red-500'}`}>
                  {isRunning ? '进行中' : isCompleted ? '已完成' : '失败'}
                </span>
              </span>
            )}
            <button
              onClick={() => { fetchTasks(); setShowTaskPicker(!showTaskPicker) }}
              className="px-3 py-1.5 text-xs border rounded-lg hover:bg-gray-50 text-gray-600"
            >
              {showTaskPicker ? '关闭' : '查看历史任务'}
            </button>
          </div>
        </div>

        {/* 历史任务选择面板 */}
        {showTaskPicker && (
          <div className="mb-6 p-4 bg-white border rounded-lg shadow-sm">
            <h3 className="text-sm font-bold mb-3">选择历史任务查看结果</h3>
            {taskList.length === 0 ? (
              <p className="text-sm text-gray-400">暂无历史任务</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {taskList.filter(t => t.id !== task?.id).map(t => (
                  <div
                    key={t.id}
                    onClick={() => handleSelectTask(t.id)}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate">{t.app_url}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                          t.status === 'completed' ? 'bg-green-100 text-green-700' :
                          t.status === 'failed' ? 'bg-red-100 text-red-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>{t.status}</span>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5 truncate">
                        ID: {t.id} | {t.created_at ? new Date(t.created_at).toLocaleString() : ''}
                        {t.goal ? ` | 目标: ${t.goal}` : ''}
                      </p>
                    </div>
                    <span className="text-xs text-blue-500 ml-2 shrink-0">查看 &rarr;</span>
                    <button
                      onClick={(e) => handleDeleteTask(t.id, e)}
                      className="ml-2 text-xs text-red-400 hover:text-red-600 shrink-0 cursor-pointer"
                      title="删除此任务"
                    >
                      删除
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 输入区 */}
        <AppInput onStart={handleStart} loading={loading} />

        {/* 进度面板 */}
        {showTabs && (
          <ProgressPanel task={task} events={events} connected={connected} />
        )}

        {/* 结果 Tabs */}
        {showTabs && (
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-6">
            <TabsList className="w-full justify-start border-b rounded-none h-auto p-0 bg-transparent overflow-x-auto">
              {[
                { value: 'dashboard', label: '数据概览' },
                { value: 'reviews', label: `评论${isRunning ? ' (采集中)' : ''}` },
                { value: 'findings', label: '发现' },
                { value: 'prd', label: 'PRD' },
                { value: 'tests', label: '测试' },
                { value: 'traceability', label: '溯源' },
                { value: 'limitations', label: '数据局限' },
              ].map(tab => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="rounded-none border-b-2 border-transparent data-[state=active]:border-blue-500 data-[state=active]:bg-transparent px-4 py-2 text-sm"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="dashboard" className="mt-4">
              <ReviewTable taskId={task.id} mode="dashboard" />
            </TabsContent>
            <TabsContent value="reviews" className="mt-4">
              <ReviewTable taskId={task.id} mode="table" />
            </TabsContent>
            <TabsContent value="findings" className="mt-4">
              <FindingsView taskId={task.id} />
            </TabsContent>
            <TabsContent value="prd" className="mt-4">
              <PrdView taskId={task.id} />
            </TabsContent>
            <TabsContent value="tests" className="mt-4">
              <TestCasesView taskId={task.id} />
            </TabsContent>
            <TabsContent value="traceability" className="mt-4">
              <TraceabilityView taskId={task.id} />
            </TabsContent>
            <TabsContent value="limitations" className="mt-4">
              <LimitationsView taskId={task.id} />
            </TabsContent>
          </Tabs>
        )}

        {/* 导入数据区域 */}
        <div className="mt-6">
          <ImportView onImportSuccess={(_count, newTaskId) => {
            if (newTaskId) {
              handleSelectTask(newTaskId)
              fetchTasks()
            }
          }} />
        </div>
      </div>
    </div>
  )
}
