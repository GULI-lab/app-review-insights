export interface AnalysisTask {
  id: string
  app_url: string
  app_id: string
  goal: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress_pct: number
  current_stage: string
  error?: string
  created_at: string
}

export interface ReviewItem {
  id: number
  review_id: string
  source: string
  title?: string
  content: string
  rating: number
  author: string
  version?: string
  date?: string
  quality_score?: number
}

export interface ReviewStats {
  rating_distribution: { rating: number; count: number }[]
  daily_trend: { date: string; count: number }[]
  daily_trend_by_rating: { date: string; rating: number; count: number }[]
  version_distribution: { version: string; count: number }[]
}

export interface Finding {
  id: number
  topic: string
  confidence: 'high' | 'medium' | 'low'
  description: string
  supporting_review_ids: string[]
  sample_count: number
  representative_excerpts: string[]
  contradicting_evidence: any[]
  affected_versions: string[]
  is_statistical: boolean
  is_model_generated: boolean
  was_downgraded?: boolean
  downgrade_reason?: string
  status: string
}

export interface Requirement {
  id: number
  title: string
  description: string
  priority: string
  version: string
  status: string
}

export interface TestCase {
  id: number
  requirement_id: number | null
  description: string
  steps: string[]
  expected: string
  source_review_ids: string[]
  verified: boolean
}

export interface SSEEvent {
  id: number
  event: string
  stage: string
  data: any
  created_at: string
}

export interface TraceabilityResult {
  checked: number
  pending: number
  pending_items: { id: number; topic: string; confidence: string; sample_count: number; downgrade_reason: string | null }[]
}

export interface Limitation {
  id: number
  category: string
  description: string
  impact: string
  is_actionable: boolean
}
