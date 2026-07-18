"""Pydantic 数据模型（请求/响应 schema）"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskCreate(BaseModel):
    """创建分析任务的请求"""
    app_url: str
    goal: str = ""
    max_reviews: int = 200
    sort: str = "mostrecent"  # mostrecent / mosthelpful


class TaskResponse(BaseModel):
    """分析任务响应"""
    id: str
    app_url: str
    app_id: str
    goal: str
    data_source: str
    status: str
    progress_pct: int
    current_stage: str
    error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    """SSE 事件响应"""
    id: int
    task_id: str
    event: str
    stage: str
    data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewItem(BaseModel):
    """评论数据"""
    id: int
    review_id: str
    source: str
    title: Optional[str] = ""
    content: str
    rating: int
    author: str
    version: Optional[str] = None
    date: Optional[str] = None
    quality_score: Optional[float] = None

    class Config:
        from_attributes = True


class ReviewStats(BaseModel):
    """评论统计数据"""
    rating_distribution: list[dict]
    daily_trend: list[dict]
    version_distribution: list[dict]


class FindingItem(BaseModel):
    """分析发现"""
    id: int
    topic: str
    confidence: str
    description: str
    supporting_review_ids: list
    sample_count: int
    representative_excerpts: list
    contradicting_evidence: list
    is_statistical: bool
    is_model_generated: bool
    status: str

    class Config:
        from_attributes = True


class RequirementItem(BaseModel):
    """PRD 需求"""
    id: int
    title: str
    description: str
    priority: str
    version: str
    source_finding_ids: list
    source_review_ids: list
    status: str

    class Config:
        from_attributes = True


class TestCaseItem(BaseModel):
    """测试用例"""
    id: int
    requirement_id: Optional[int] = None
    description: str
    steps: list
    expected: str
    source_review_ids: list
    verified: bool

    class Config:
        from_attributes = True
