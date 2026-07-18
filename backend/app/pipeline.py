"""分析流水线编排

按顺序执行所有阶段：
  1. 目标解析 (scoper)       → LLM 解析 goal
  2. 数据采集 (rss)          → RSS Feed 分页抓取
  3. 清洗裁剪 (cleaner)      → 规则驱动去重/过滤
  4. AI Agent 分析 (agent)   → LangChain 动态发现主题
  5. 证据评估+PRD (planner)  → 置信度评估+版本规划
  6. 测试用例 (testgen)      → 生成测试用例
  7. 溯源验证 (validator)    → Review→Finding→Requirement 链检查
"""
import asyncio
import logging

from app.database import async_session
from app.event_manager import get_event_manager

logger = logging.getLogger("pipeline")


async def run_pipeline(task_id: str, app_id: str, goal: str, max_pages: int = 10, sort: str = "mostrecent"):
    """执行完整分析流水线"""
    em = get_event_manager(task_id)

    async with async_session() as db:
        try:
            # ====== 阶段 1: 目标解析 ======
            await em.emit("stage_start", "scoping", {}, db)
            await _update_task(db, task_id, current_stage="scoping", progress_pct=5)
            scope = {"focus_keywords": [], "focus_ratings": []}
            if goal:
                from app.llm.factory import create_llm
                llm = create_llm()
                try:
                    scope_result = await llm.chat([
                        {"role": "system", "content": "你是一个分析目标解析器。从用户的 goal 中提取关键维度，输出 JSON。"},
                        {"role": "user", "content": f"分析目标: {goal}"},
                    ])
                    import json as _json
                    try:
                        parsed = _json.loads(scope_result)
                        if isinstance(parsed, dict):
                            scope = parsed
                    except (_json.JSONDecodeError, TypeError):
                        pass
                except Exception as e:
                    logger.warning("Scope parsing failed (LLM may not be configured): %s", e)
            await em.emit("scope_defined", "scoping", scope, db)
            await em.emit("stage_complete", "scoping", {}, db)

            # ====== 阶段 2: 数据采集 ======
            await em.emit("stage_start", "collecting", {}, db)
            await _update_task(db, task_id, current_stage="collecting", progress_pct=20)

            rating_history = {r: 0 for r in range(1, 6)}

            async def on_page(page, page_reviews, total):
                nonlocal rating_history
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
            await em.emit("stage_complete", "collecting",
                          {"total": len(raw_reviews)}, db)

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
            from app.llm.factory import create_llm
            llm = create_llm()

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

            from app.models.db import Finding
            for f_data in all_findings:
                db.add(Finding(task_id=task_id, **f_data))
            await db.commit()

            # 统计各置信度等级
            confidence_dist = {"high": 0, "medium": 0, "low": 0}
            for f in all_findings:
                c = f.get("confidence", "low")
                confidence_dist[c] = confidence_dist.get(c, 0) + 1

            # 提取前5个发现主题作为预览
            top_topics = [f.get("topic", "") for f in all_findings[:5]]

            await em.emit("stage_complete", "analyzing", {
                "findings_count": len(all_findings),
                "confidence_dist": confidence_dist,
                "top_topics": top_topics,
            }, db)

            # 证据评估总结
            downgraded = []
            unchanged = []
            for f in all_findings:
                if f.get("sample_count", 0) < 2:
                    downgraded.append(f.get("topic", ""))
                else:
                    unchanged.append(f.get("topic", ""))

            # ====== 阶段 5: 证据评估 + PRD ======
            await em.emit("stage_start", "planning", {}, db)
            await _update_task(db, task_id, current_stage="planning", progress_pct=80)

            from app.services.planner import evaluate_evidence, generate_prd
            from app.models.db import Requirement

            evaluated = await evaluate_evidence(all_findings, llm)
            prd_text = await generate_prd(evaluated, llm)

            from app.models.db import Requirement
            req = Requirement(
                task_id=task_id,
                title="产品需求文档",
                description=prd_text,
                priority="p0",
            )
            db.add(req)
            await db.commit()

            await em.emit("stage_complete", "planning", {
                "prd_snippet": prd_text[:500] if prd_text else "",
                "evaluated_count": len(evaluated),
                "downgraded_count": sum(1 for f in evaluated if f.get("was_downgraded")),
                "downgraded_topics": downgraded,
                "unchanged_topics": unchanged,
            }, db)

            # ====== 阶段 6: 溯源验证 ======
            await em.emit("stage_start", "done", {}, db)
            await _update_task(db, task_id, progress_pct=95, current_stage="done")
            # 溯源验证
            from app.services.validator import validate_traceability
            try:
                trace_result = await validate_traceability(task_id, db)
                await em.emit("stage_progress", "done", {"traceability": trace_result}, db)
            except Exception as e:
                logger.warning("Traceability validation failed: %s", e)

            # 数据局限性报告
            from app.models.db import DataLimitation
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
            await em.emit("stage_complete", "done", {"traceability": trace_result if trace_result else None}, db)
            await em.emit("analysis_complete", "done", {"task_id": task_id}, db)

        except Exception as e:
            logger.exception("Pipeline failed")
            await _update_task(db, task_id, status="failed", current_stage="pipeline",
                               error=str(e))
            await em.emit("stage_error", "pipeline", {"error": str(e)}, db)


async def _update_task(db, task_id: str, **kwargs):
    from sqlalchemy import update
    from app.models.db import AnalysisTask
    await db.execute(update(AnalysisTask).where(AnalysisTask.id == task_id).values(**kwargs))
    await db.commit()
