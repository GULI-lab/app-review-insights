import type { AnalysisTask, ReviewItem, ReviewStats, Finding, Requirement, TestCase, TraceabilityResult, Limitation } from '@/types'

const BASE = '/api'

export async function deleteTask(taskId: string): Promise<void> {
  const res = await fetch(`${BASE}/analysis/${taskId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Delete failed')
}

export async function startAnalysis(app_url: string, goal: string, max_reviews = 200, sort = 'mostrecent'): Promise<AnalysisTask> {
  const res = await fetch(`${BASE}/analysis/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_url, goal, max_reviews, sort }),
  })
  return res.json()
}

export async function getTask(taskId: string): Promise<AnalysisTask> {
  const res = await fetch(`${BASE}/analysis/${taskId}`)
  return res.json()
}

export async function getReviews(
  taskId: string,
  page = 1,
  rating?: number
): Promise<{ items: ReviewItem[]; total: number }> {
  const params = new URLSearchParams({ page: String(page) })
  if (rating) params.set('rating', String(rating))
  const res = await fetch(`${BASE}/analysis/${taskId}/reviews?${params}`)
  return res.json()
}

export async function getReviewById(taskId: string, reviewId: string): Promise<ReviewItem> {
  const res = await fetch(`${BASE}/analysis/${taskId}/reviews/${reviewId}`)
  if (!res.ok) throw new Error('Review not found')
  return res.json()
}

export async function getReviewStats(taskId: string): Promise<ReviewStats> {
  const res = await fetch(`${BASE}/analysis/${taskId}/reviews/stats`)
  return res.json()
}

export async function getFindings(taskId: string): Promise<Finding[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/findings`)
  return res.json()
}

export async function getRequirements(taskId: string): Promise<Requirement[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/requirements`)
  return res.json()
}

export async function getTestCases(taskId: string): Promise<TestCase[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/test-cases`)
  return res.json()
}

export async function getTraceability(taskId: string): Promise<TraceabilityResult> {
  const res = await fetch(`${BASE}/analysis/${taskId}/traceability`)
  return res.json()
}

export async function getLimitations(taskId: string): Promise<Limitation[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/limitations`)
  return res.json()
}
