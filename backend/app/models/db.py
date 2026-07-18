"""SQLAlchemy ORM 模型

所有表定义：
  - analysis_tasks: 分析任务
  - analysis_events: SSE 事件持久化
  - raw_reviews: 原始评论（RSS 采集）
  - cleaned_reviews: 清洗后评论
  - findings: AI 分析发现
  - data_limitations: 数据集局限性
  - requirements: PRD 需求
  - test_cases: 测试用例
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    JSON, ForeignKey,
)
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ---------- 分析任务 ----------
class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    app_url = Column(String, nullable=False)
    app_id = Column(String, nullable=False)
    goal = Column(Text, default="")
    data_source = Column(String, default="rss")
    parsed_scope = Column(JSON, nullable=True)
    status = Column(String, default="pending")  # pending/running/completed/failed
    progress_pct = Column(Integer, default=0)
    current_stage = Column(String, default="")
    error = Column(Text, nullable=True)
    limitations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


# ---------- SSE 事件持久化 ----------
class AnalysisEvent(Base):
    __tablename__ = "analysis_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    event = Column(String, nullable=False)    # stage_start/stage_complete/stage_error/...
    stage = Column(String, nullable=False)     # scoping/collecting/cleaning/...
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


# ---------- 原始评论 ----------
class RawReview(Base):
    __tablename__ = "raw_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    review_id = Column(String, nullable=False)
    source = Column(String, default="rss")
    title = Column(Text, default="")
    content = Column(Text, default="")
    rating = Column(Integer, nullable=False)
    author = Column(String, default="")
    version = Column(String, nullable=True)
    date = Column(String, nullable=True)
    country = Column(String, nullable=True)
    fetch_page = Column(Integer, default=0)


# ---------- 清洗后评论 ----------
class CleanedReview(Base):
    __tablename__ = "cleaned_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    review_id = Column(String, nullable=False)
    source = Column(String, default="rss")
    title = Column(Text, default="")
    content = Column(Text, default="")
    rating = Column(Integer, nullable=False)
    author = Column(String, default="")
    version = Column(String, nullable=True)
    date = Column(String, nullable=True)
    country = Column(String, nullable=True)
    duplicate_of = Column(Integer, nullable=True)
    quality_score = Column(Float, default=0.5)
    relevance_score = Column(Float, default=0.0)


# ---------- 分析发现 ----------
class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    topic = Column(String, nullable=False)
    confidence = Column(String, default="medium")  # high/medium/low
    description = Column(Text, default="")
    supporting_review_ids = Column(JSON, default=list)
    sample_count = Column(Integer, default=0)
    representative_excerpts = Column(JSON, default=list)
    contradicting_evidence = Column(JSON, default=list)
    is_statistical = Column(Boolean, default=False)
    is_model_generated = Column(Boolean, default=True)
    was_downgraded = Column(Boolean, default=False)
    downgrade_reason = Column(Text, nullable=True)
    status = Column(String, default="approved")  # approved/pending_review/dismissed


# ---------- 数据局限性 ----------
class DataLimitation(Base):
    __tablename__ = "data_limitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    category = Column(String, nullable=False)  # coverage/timeliness/language/sampling/feed
    description = Column(Text, default="")
    impact = Column(Text, default="")
    is_actionable = Column(Boolean, default=False)


# ---------- PRD 需求 ----------
class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    priority = Column(String, default="p2")   # p0/p1/p2
    version = Column(String, default="v1")    # v1/v2/v3
    source_finding_ids = Column(JSON, default=list)
    source_review_ids = Column(JSON, default=list)
    status = Column(String, default="approved")


# ---------- 测试用例 ----------
class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=True)
    description = Column(Text, default="")
    steps = Column(JSON, default=list)
    expected = Column(Text, default="")
    source_review_ids = Column(JSON, default=list)
    verified = Column(Boolean, default=False)
