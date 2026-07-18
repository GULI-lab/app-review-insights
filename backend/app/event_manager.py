"""SSE 事件管理 + 持久化

每个分析任务有一个 EventManager 实例，负责：
  1. 广播 SSE 事件给所有订阅者（前端连接）
  2. 持久化非 progress 事件到 DB（断线重连用）
  3. 回放历史事件（since_id）
"""
import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AnalysisEvent


class EventManager:
    """单任务事件管理器"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._subscribers: list[asyncio.Queue] = []
        self._event_id = 0

    def subscribe(self) -> asyncio.Queue:
        """订阅者注册（返回一个 Queue 用于接收事件）"""
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """取消订阅"""
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def emit(
        self,
        event: str,
        stage: str,
        data: dict | None = None,
        db: AsyncSession | None = None,
    ):
        """广播事件到所有订阅者 + 持久化到 DB

        参数:
          event: 事件类型（stage_start/stage_complete/stage_progress/stage_error/...）
          stage: 阶段名（scoping/collecting/cleaning/analyzing/planning）
          data: 事件负载
          db: 数据库 session（传入则持久化非 progress 事件）
        """
        self._event_id += 1
        payload = {
            "id": self._event_id,
            "event": event,
            "stage": stage,
            "data": data or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 广播到所有订阅者
        for q in self._subscribers:
            await q.put(payload)

        # 持久化（高频 progress 事件不入库）
        if event != "stage_progress" and db:
            db_event = AnalysisEvent(
                task_id=self.task_id,
                event=event,
                stage=stage,
                data=data,
            )
            db.add(db_event)
            await db.commit()

    async def replay(self, db: AsyncSession, since_id: int = 0) -> list[AnalysisEvent]:
        """回放历史事件（断线重连用）"""
        result = await db.execute(
            select(AnalysisEvent)
            .where(AnalysisEvent.task_id == self.task_id, AnalysisEvent.id > since_id)
            .order_by(AnalysisEvent.id)
        )
        return list(result.scalars().all())


# 全局管理器注册表：task_id -> EventManager
_managers: dict[str, EventManager] = {}


def get_event_manager(task_id: str) -> EventManager:
    """获取（或创建）任务的 EventManager"""
    if task_id not in _managers:
        _managers[task_id] = EventManager(task_id)
    return _managers[task_id]
