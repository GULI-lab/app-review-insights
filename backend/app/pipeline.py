"""分析流水线编排 — 8 阶段（含 testgen）"""

import asyncio
import logging
from sqlalchemy import select, update

from app.database import async_session
from app.config import get_llm
from app.event_manager import get_event_manager
from app.models.db import AnalysisTask, RawReview, CleanedReview, Finding, Requirement, TestCase, DataLimitation

logger = logging.getLogger("pipeline")


async def run_pipeline(task_id: str, app_id: str, goal: str, max_pages: int = 10, sort: str = "mostrecent"):
    """执行完整分析流水线"""
    em = get_event_manager(task_id)

    async with async_session() as db:
        try:
            llm = get_llm()

            # ====== 阶段 1: 目标解析 ======
            await em.emit("stage_start", "scoping", {}, db)
            await _update_task(db, task_id, current_stage="scoping", progress_pct=5)
            scope = {"focus_keywords": [], "focus_ratings": []}
            if goal:
                try:
                    from langchain_core.prompts import ChatPromptTemplate
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", "你是一个分析目标解析器。从用户的 goal 中提取关键维度，输出 JSON。"),
                        ("human", "分析目标: {goal}"),
                    ])
                    result = await (prompt | llm).ainvoke({"goal": goal})
                    import json as _json
                    try:
                        content = result.content if hasattr(result, 'content') else str(result)
                        parsed = _json.loads(content)
                        if isinstance(parsed, dict):
                            scope = parsed
                    except (_json.JSONDecodeError, TypeError):
                        pass
                except Exception as e:
                    logger.warning("Scope parsing failed: %s", e)
            await em.emit("scope_defined", "scoping", scope, db)
            await em.emit("stage_complete", "scoping", {}, db)

            # ====== 阶段 2: 数据采集 ======
            await em.emit("stage_start", "collecting", {}, db)
            await _update_task(db, task_id, current_stage="collecting", progress_pct=20)

            rating_history = {r: 0 for r in range(1, 6)}

            async def on_page(page, page_reviews, total):
                for rv in page_reviews:
                    rating_history[rv["rating"]] = rating_history.get(rv["rating"], 0) + 1
                await em.emit("stage_progress", "collecting", {
                    "page": page,
                    "total_pages": max_pages,
                    "count": total,
                    "rating_distribution": [
                        {"rating": r, "count": rating_history.get(r, 0)}
                        for r in range(1, 6)
                    ],
                })

            from app.services.collectors.rss import fetch_reviews
            raw_reviews = await fetch_reviews(app_id, db, task_id, max_pages, sort=sort, on_progress=on_page)
            await em.emit("stage_complete", "collecting", {"total": len(raw_reviews)}, db)

            # ====== 阶段 3: 清洗裁剪 ======
            await em.emit("stage_start", "cleaning", {}, db)
            await _update_task(db, task_id, current_stage="cleaning", progress_pct=40)

            from app.services.cleaner import clean_reviews
            cleaned, stats = clean_reviews(raw_reviews, task_id)
            for cr in cleaned:
                db.add(cr)
            await db.commit()
            await em.emit("stage_complete", "cleaning", {
                "input_count": stats.get("input_count", 0),
                "output_count": stats.get("output_count", 0),
                "invalid_filtered": stats.get("invalid_filtered", 0),
                "ad_filtered": stats.get("ad_filtered", 0),
                "duplicates_removed": stats.get("duplicates_removed", 0),
                "avg_quality": stats.get("avg_quality", 0),
            }, db)

            # ====== 阶段 4: AI Agent 分析 ======
            await em.emit("stage_start", "analyzing", {}, db)
            await _update_task(db, task_id, current_stage="analyzing", progress_pct=60)

            from app.services.sampler import split_blocks
            from app.services.agent import analyze_reviews

            review_dicts = [
                {"review_id": r.review_id, "content": r.content,
                 "title": r.title, "rating": r.rating}
                for r in cleaned
            ]

            all_findings = []
            blocks = split_blocks(review_dicts, block_size=100)
            for i, block in enumerate(blocks):
                await em.emit("stage_progress", "analyzing",
                              {"block": i + 1, "total_blocks": len(blocks)}, db)
                findings = await analyze_reviews(block, llm, goal)
                all_findings.extend(findings)

            for f_data in all_findings:
                db.add(Finding(task_id=task_id, **f_data))
            await db.flush()

            # 统计各置信度等级
            confidence_dist = {"high": 0, "medium": 0, "low": 0}
            for f in all_findings:
                c = f.get("confidence", "low")
                confidence_dist[c] = confidence_dist.get(c, 0) + 1
            top_topics = [f.get("topic", "") for f in all_findings[:5]]

            await em.emit("stage_complete", "analyzing", {
                "findings_count": len(all_findings),
                "confidence_dist": confidence_dist,
                "top_topics": top_topics,
            }, db)

            # ====== 阶段 5: 证据评估 + PRD 生成与拆分 ======
            await em.emit("stage_start", "planning", {}, db)
            await _update_task(db, task_id, current_stage="planning", progress_pct=80)

            from app.services.planner import evaluate_evidence, generate_prd

            evaluated = await evaluate_evidence(all_findings)

            # 重新读取 DB 中的 Finding 以获取 ID
            result = await db.execute(
                select(Finding).where(Finding.task_id == task_id)
            )
            saved_findings = list(result.scalars().all())

            # 将 DB id 匹配回 evaluated dict
            for f_data in evaluated:
                f_data["_db_id"] = next(
                    (sf.id for sf in saved_findings
                     if sf.topic == f_data.get("topic", "")
                       and sf.description == f_data.get("description", "")),
                    None
                )

            prd = await generate_prd(saved_findings, llm)

            downgraded_topics = []
            for f in evaluated:
                if f.get("was_downgraded"):
                    downgraded_topics.append(f.get("topic", ""))

            for req in prd.requirements:
                source_review_ids = []
                for fid in req.source_finding_ids:
                    finding = next((sf for sf in saved_findings if sf.id == fid), None)
                    if finding and finding.supporting_review_ids:
                        source_review_ids.extend(finding.supporting_review_ids)

                db.add(Requirement(
                    task_id=task_id,
                    title=req.title,
                    description=req.description,
                    priority=req.priority,
                    version=req.version,
                    source_finding_ids=req.source_finding_ids,
                    source_review_ids=list(set(source_review_ids)),
                ))
            await db.commit()

            await em.emit("stage_complete", "planning", {
                "prd_snippet": prd.overview[:500] if prd.overview else "",
                "evaluated_count": len(evaluated),
                "downgraded_count": len(downgraded_topics),
                "downgraded_topics": downgraded_topics,
                "requirements_count": len(prd.requirements),
            }, db)

            # ====== 阶段 5b: 测试用例生成 ======
            await em.emit("stage_start", "testgen", {}, db)
            await _update_task(db, task_id, current_stage="testgen", progress_pct=90)

            from app.services.testgen import generate_test_cases

            req_result = await db.execute(
                select(Requirement).where(Requirement.task_id == task_id)
            )
            reqs = req_result.scalars().all()

            req_dicts = [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "version": r.version,
                    "source_review_ids": r.source_review_ids or [],
                }
                for r in reqs
            ]

            test_cases = await generate_test_cases(req_dicts, llm)

            for tc in test_cases:
                db.add(TestCase(
                    task_id=task_id,
                    requirement_id=tc.get("requirement_id"),
                    description=tc.get("description", ""),
                    steps=tc.get("steps", []),
                    expected=tc.get("expected", ""),
                    source_review_ids=tc.get("source_review_ids", []),
                ))
            await db.commit()

            await em.emit("stage_complete", "testgen", {
                "test_cases_count": len(test_cases),
            }, db)

            # ====== 阶段 6: 溯源验证 + 最终确定 ======
            await em.emit("stage_start", "done", {}, db)
            await _update_task(db, task_id, progress_pct=95, current_stage="done")

            from app.services.validator import validate_traceability
            trace_result = {"checked": 0, "pending": 0}
            try:
                trace_result = await validate_traceability(task_id, db)
                await em.emit("stage_progress", "done", {"traceability": trace_result}, db)
            except Exception as e:
                logger.warning("Traceability validation failed: %s", e)

            limitations = [
                DataLimitation(task_id=task_id, category="feed",
                    description="评论数据来自 Apple RSS Feed，仅包含最近评论，无法获取历史全量",
                    impact="分析结论可能不反映长期趋势", is_actionable=False),
                DataLimitation(task_id=task_id, category="coverage",
                    description="RSS Feed 内容可能被截断，超长评论不完整",
                    impact="部分用户反馈可能缺失细节", is_actionable=False),
                DataLimitation(task_id=task_id, category="timeliness",
                    description="RSS 仅返回最近评论，时间窗口有限",
                    impact="最新版本的问题可能比旧版本更突出", is_actionable=True),
            ]
            for lim in limitations:
                db.add(lim)
            await db.commit()

            await _update_task(db, task_id, status="completed", progress_pct=100,
                               current_stage="done")
            await em.emit("stage_complete", "done", {"traceability": trace_result}, db)
            await em.emit("analysis_complete", "done", {"task_id": task_id}, db)

        except Exception as e:
            logger.exception("Pipeline failed")
            await _update_task(db, task_id, status="failed", current_stage="pipeline",
                               error=str(e))
            await em.emit("stage_error", "pipeline", {"error": str(e)}, db)


async def _update_task(db, task_id: str, **kwargs):
    await db.execute(update(AnalysisTask).where(AnalysisTask.id == task_id).values(**kwargs))
    await db.commit()
