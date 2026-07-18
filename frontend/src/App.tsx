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
import { startAnalysis, getTask } from './api/client'
import type { AnalysisTask } from './types'

export default function App() {
  const [task, setTask] = useState<AnalysisTask | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('dashboard')
  const { events, connected } = useSSE({ taskId: task?.id ?? null })

  const handleStart = useCallback(async (url: string, goal: string, maxReviews: number, sort: string) => {
    setLoading(true)
    try {
      const t = await startAnalysis(url, goal, maxReviews, sort)
      setTask(t)
    } catch (err: any) {
      alert('启动分析失败: ' + (err?.message || '未知错误'))
    } finally {
      setLoading(false)
    }
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
  // 只要有任务（含进行中），就显示结果区
  const showTabs = task && (isRunning || isCompleted || isFailed)

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="max-w-6xl mx-auto p-4 md:p-8">
        {/* 标题 */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">App Review Insights</h1>
          <p className="text-sm text-gray-500 mt-1">App Store 评论智能分析平台</p>
        </div>

        {/* 输入区 */}
        <AppInput onStart={handleStart} loading={loading} />

        {/* 进度面板：任务启动后就一直显示 */}
        {showTabs && (
          <ProgressPanel task={task} events={events} connected={connected} />
        )}

        {/* 结果 Tabs：有任务就开始显示，分析中也能看已采集的评论 */}
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

        {/* 导入数据区域：始终可见，不依赖任务 */}
        <div className="mt-6">
          <ImportView />
        </div>
      </div>
    </div>
  )
}
