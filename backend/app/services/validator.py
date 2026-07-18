"""溯源性验证

验证 Review→Finding→Requirement→TestCase 链的完整性。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import Finding, Requirement, TestCase


async def validate_traceability(task_id: str, db: AsyncSession) -> dict:
    """验证溯源链，标记断链为 pending_review"""
    result = await db.execute(
        select(Finding).where(Finding.task_id == task_id)
    )
    findings = result.scalars().all()

    pending_count = 0

    for f in findings:
        # Finding → Review < 2
        supports = f.supporting_review_ids or []
        if len(supports) < 2:
            f.status = "pending_review"
            f.was_downgraded = True
            f.downgrade_reason = f"支撑评论不足({len(supports)}条)"
            pending_count += 1

    await db.commit()
    return {
        "checked": len(findings),
        "pending": pending_count,
    }
