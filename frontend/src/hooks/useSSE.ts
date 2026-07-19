import { useEffect, useRef, useState, useCallback } from 'react'
import type { SSEEvent } from '@/types'

interface UseSSEOptions {
  taskId: string | null
  sinceId?: number
}

export function useSSE({ taskId, sinceId = 0 }: UseSSEOptions) {
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const taskIdRef = useRef(taskId)

  // 任务切换时清空老事件
  if (taskId !== taskIdRef.current) {
    taskIdRef.current = taskId
    if (events.length > 0) {
      setEvents([])
    }
  }

  const connect = useCallback(() => {
    if (!taskId) return
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    const es = new EventSource(`/api/analysis/${taskId}/stream?since_id=${sinceId}`)
    eventSourceRef.current = es
    setConnected(true)

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as SSEEvent
        setEvents(prev => [...prev, event])
      } catch { /* ignore parse errors */ }
    }

    es.onerror = () => {
      setConnected(false)
      es.close()
      setTimeout(connect, 3000)
    }
  }, [taskId, sinceId])

  useEffect(() => {
    connect()
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [connect])

  return { events, connected }
}
