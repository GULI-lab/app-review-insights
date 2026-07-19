"""数据导入 API（JSON/CSV）"""
import asyncio
import csv, io, json, logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.db import RawReview

logger = logging.getLogger("import_api")

router = APIRouter()

FIELD_ALIASES = {
    "content": ["content", "body", "text", "review", "description"],
    "rating": ["rating", "score", "stars"],
    "author": ["author", "user", "username", "name"],
    "title": ["title", "subject", "headline"],
    "version": ["version", "app_version"],
    "date": ["date", "created", "timestamp", "review_date"],
}


def _detect_mapping(headers: list[str]) -> dict[str, str]:
    """自动检测字段映射"""
    mapping = {}
    header_lower = [h.lower() for h in headers]
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in header_lower:
                idx = header_lower.index(alias)
                mapping[headers[idx]] = canonical
                break
    return mapping


@router.post("/import")
async def import_reviews(
    file: UploadFile = File(...),
    task_id: str = "",
    db: AsyncSession = Depends(get_db),
):
    """导入 JSON/CSV 评论数据

    如果未提供 task_id，自动创建新任务。
    导入的数据直接进入 CleanedReview 表，可在评论 Tab 查看。
    """
    from app.models.db import AnalysisTask
    from sqlalchemy import select, func

    if not task_id:
        # 自动创建任务
        task = AnalysisTask(
            app_url="imported",
            app_id="imported",
            goal="导入的外部评论数据",
            status="imported",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    content = await file.read()
    fmt = "csv" if file.filename and file.filename.endswith(".csv") else "json"

    if fmt == "csv":
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV has no headers")
        mapping = _detect_mapping(reader.fieldnames)
        imported = []
        for row in reader:
            rating = int(row.get(mapping.get("rating", "") or 0))
            if not 1 <= rating <= 5:
                continue
            imported.append(RawReview(
                task_id=task_id,
                review_id=row.get("review_id", ""),
                author=row.get(mapping.get("author", ""), ""),
                title=row.get(mapping.get("title", ""), ""),
                content=row.get(mapping.get("content", ""), ""),
                rating=rating,
                version=row.get(mapping.get("version", ""), None),
                date=row.get(mapping.get("date", ""), None),
                source="import",
            ))
    else:
        data = json.loads(content.decode("utf-8"))
        items = data if isinstance(data, list) else data.get("reviews", [data])
        imported = []
        for item in items:
            if not isinstance(item, dict):
                continue
            rating = int(item.get("rating", 0))
            if not 1 <= rating <= 5:
                continue
            imported.append(RawReview(
                task_id=task_id,
                review_id=str(item.get("review_id", item.get("id", ""))),
                author=item.get("author", ""),
                title=item.get("title", ""),
                content=item.get("content", item.get("body", "")),
                rating=rating,
                version=item.get("version", None),
                date=item.get("date", None),
                source="import",
            ))

    for r in imported:
        db.add(r)
    await db.commit()

    # 自动触发 pipeline（跳过采集阶段）
    task.status = "running"
    await db.commit()

    from app.pipeline import run_pipeline
    asyncio.create_task(run_pipeline(
        task_id=task_id,
        app_id=task.app_id,
        goal=task.goal,
        skip_collection=True,
    ))

    return {"imported": len(imported), "task_id": task_id}
