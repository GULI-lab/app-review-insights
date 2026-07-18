"""FastAPI 应用入口

路由列表:
  POST /api/analysis/start   — 启动分析任务
  GET  /api/analysis/{id}    — 查询任务状态
  GET  /api/analysis/{id}/stream — SSE 事件流
  GET  /api/analysis/{id}/reviews — 评论列表
  GET  /api/analysis/{id}/reviews/stats — 评论统计
  GET  /api/analysis/{id}/findings — 分析发现
  GET  /api/analysis/{id}/requirements — PRD 需求
  GET  /api/analysis/{id}/test-cases — 测试用例
  POST /api/import — 导入数据
"""
import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.database import init_db, get_db
from app.models.db import AnalysisTask, AnalysisEvent, RawReview, CleanedReview, Finding, Requirement, TestCase
from app.models.schemas import TaskCreate, TaskResponse
from app.event_manager import get_event_manager, EventManager
from app.pipeline import run_pipeline
from app.routers import import_

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="App Review Insights", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.include_router(import_.router, prefix="/api")


# ---------- 工具函数 ----------

def _extract_app_id(url: str) -> str:
    """从 App Store URL 中提取 app_id（纯数字）"""
    m = re.search(r"/id(\d+)", url)
    return m.group(1) if m else ""


# ---------- API 路由 ----------

@app.post("/api/analysis/start", response_model=TaskResponse)
async def start_analysis(task_in: TaskCreate, db: AsyncSession = Depends(get_db)):
    """创建并启动分析任务"""
    app_id = _extract_app_id(task_in.app_url)
    if not app_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="无法从 URL 中解析 app_id")

    # max_reviews → max_pages（每页 50 条）
    import math
    max_pages = max(1, math.ceil(task_in.max_reviews / 50))

    task = AnalysisTask(
        app_url=task_in.app_url,
        app_id=app_id,
        goal=task_in.goal,
        status="running",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 后台运行流水线
    asyncio.create_task(run_pipeline(task.id, app_id, task_in.goal, max_pages=max_pages, sort=task_in.sort))

    return TaskResponse.model_validate(task)


@app.get("/api/tasks")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    """列出所有分析任务"""
    result = await db.execute(
        select(AnalysisTask).order_by(AnalysisTask.created_at.desc()).limit(50)
    )
    return [{
        "id": t.id,
        "app_url": t.app_url,
        "goal": t.goal,
        "status": t.status,
        "progress_pct": t.progress_pct,
        "current_stage": t.current_stage,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    } for t in result.scalars()]


@app.get("/api/analysis/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """查询任务状态"""
    result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@app.get("/api/analysis/{task_id}/stream")
async def stream_events(task_id: str, since_id: int = 0, db: AsyncSession = Depends(get_db)):
    """SSE 事件流（断线重连支持）

    query param since_id=0 表示全量回放
    """

    async def event_generator():
        em = get_event_manager(task_id)

        # 1. 回放历史事件
        result = await db.execute(
            select(AnalysisEvent)
            .where(AnalysisEvent.task_id == task_id, AnalysisEvent.id > since_id)
            .order_by(AnalysisEvent.id)
        )
        for ev in result.scalars():
            payload = {
                "id": ev.id,
                "event": ev.event,
                "stage": ev.stage,
                "data": ev.data,
                "created_at": ev.created_at.isoformat(),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # 2. 实时流
        q = em.subscribe()
        try:
            while True:
                payload = await q.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            em.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/analysis/{task_id}/reviews")
async def get_reviews(
    task_id: str,
    page: int = 1,
    rating: int = None,
    db: AsyncSession = Depends(get_db),
):
    """获取清洗后的评论列表（分页+筛选）"""
    query = select(CleanedReview).where(CleanedReview.task_id == task_id)
    if rating:
        query = query.where(CleanedReview.rating == rating)
    query = query.order_by(CleanedReview.date.desc().nulls_last()).limit(20).offset((page - 1) * 20)

    result = await db.execute(query)
    items = result.scalars().all()

    count_q = select(func.count()).select_from(CleanedReview).where(CleanedReview.task_id == task_id)
    if rating:
        count_q = count_q.where(CleanedReview.rating == rating)
    total = (await db.execute(count_q)).scalar()

    return {
        "items": [{
            "id": r.id,
            "review_id": r.review_id,
            "source": r.source,
            "title": r.title or "",
            "content": r.content,
            "rating": r.rating,
            "author": r.author,
            "version": r.version,
            "date": r.date,
            "quality_score": r.quality_score,
        } for r in items],
        "total": total,
        "page": page,
    }


@app.get("/api/analysis/{task_id}/reviews/stats")
async def get_review_stats(task_id: str, db: AsyncSession = Depends(get_db)):
    """评论统计（评分分布、时间趋势、版本分布）"""
    result = await db.execute(
        select(CleanedReview).where(CleanedReview.task_id == task_id)
    )
    reviews = result.scalars().all()

    # 评分分布
    rating_dist = {}
    for r in reviews:
        rating_dist[r.rating] = rating_dist.get(r.rating, 0) + 1

    # 时间趋势（按日）
    daily = {}
    for r in reviews:
        if r.date:
            day = r.date[:10]
            daily[day] = daily.get(day, 0) + 1

    # 版本分布
    version_dist = {}
    for r in reviews:
        if r.version:
            version_dist[r.version] = version_dist.get(r.version, 0) + 1

    return {
        "rating_distribution": [
            {"rating": k, "count": v} for k, v in sorted(rating_dist.items(), reverse=True)
        ],
        "daily_trend": [
            {"date": k, "count": v} for k, v in sorted(daily.items())
        ],
        "version_distribution": [
            {"version": k, "count": v} for k, v in sorted(version_dist.items(), key=lambda x: -x[1])
        ],
    }


@app.get("/api/analysis/{task_id}/findings")
async def get_findings(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Finding).where(Finding.task_id == task_id).order_by(Finding.confidence)
    )
    return [{
        "id": f.id,
        "topic": f.topic,
        "confidence": f.confidence,
        "description": f.description,
        "supporting_review_ids": f.supporting_review_ids or [],
        "sample_count": f.sample_count,
        "representative_excerpts": f.representative_excerpts or [],
        "contradicting_evidence": f.contradicting_evidence or [],
        "is_statistical": f.is_statistical,
        "is_model_generated": f.is_model_generated,
        "status": f.status,
    } for f in result.scalars()]


@app.get("/api/analysis/{task_id}/requirements")
async def get_requirements(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Requirement).where(Requirement.task_id == task_id).order_by(Requirement.priority)
    )
    return [{
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "priority": r.priority,
        "version": r.version,
        "source_finding_ids": r.source_finding_ids or [],
        "source_review_ids": r.source_review_ids or [],
        "status": r.status,
    } for r in result.scalars()]


@app.get("/api/analysis/{task_id}/test-cases")
async def get_test_cases(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestCase).where(TestCase.task_id == task_id)
    )
    return [{
        "id": tc.id,
        "requirement_id": tc.requirement_id,
        "description": tc.description,
        "steps": tc.steps or [],
        "expected": tc.expected,
        "source_review_ids": tc.source_review_ids or [],
        "verified": tc.verified,
    } for tc in result.scalars()]


@app.get("/api/analysis/{task_id}/traceability")
async def get_traceability(task_id: str, db: AsyncSession = Depends(get_db)):
    """溯源性验证结果"""
    from app.services.validator import validate_traceability
    result = await validate_traceability(task_id, db)
    # 同时返回 pending 的 findings
    findings_result = await db.execute(
        select(Finding).where(Finding.task_id == task_id, Finding.status == "pending_review")
    )
    pending = [{
        "id": f.id, "topic": f.topic, "confidence": f.confidence,
        "sample_count": f.sample_count,
        "downgrade_reason": f.downgrade_reason,
    } for f in findings_result.scalars()]
    return {**result, "pending_items": pending}


@app.get("/api/analysis/{task_id}/limitations")
async def get_limitations(task_id: str, db: AsyncSession = Depends(get_db)):
    """数据局限性报告"""
    from app.models.db import DataLimitation
    result = await db.execute(
        select(DataLimitation).where(DataLimitation.task_id == task_id)
    )
    items = [{
        "id": l.id, "category": l.category,
        "description": l.description, "impact": l.impact,
        "is_actionable": l.is_actionable,
    } for l in result.scalars()]
    if not items:
        items = [
            {"id": 0, "category": "feed", "description": "评论数据来自 Apple RSS Feed，仅包含最近评论，无法获取历史全量", "impact": "分析结论可能不反映长期趋势", "is_actionable": False},
            {"id": 0, "category": "coverage", "description": "RSS Feed 内容可能被截断，超长评论不完整", "impact": "部分用户反馈可能缺失细节", "is_actionable": False},
        ]
    return items
