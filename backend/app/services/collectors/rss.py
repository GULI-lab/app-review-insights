"""RSS Feed 评论采集服务

复用 demo/rss_feed_demo.py 的核心逻辑，改造为异步服务：
  - 分页抓取 Apple RSS Feed
  - 提取评论数据写入 raw_reviews 表
  - 每页完成后回调 on_progress（用于 SSE 进度推送）
"""
import json
import logging
import re
import ssl
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import urllib.error
import urllib.request

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import RawReview

logger = logging.getLogger("rss_collector")

# 宽松 SSL 上下文（Windows 证书验证问题）
_PERMISSIVE_SSL = ssl.create_default_context()
_PERMISSIVE_SSL.check_hostname = False
_PERMISSIVE_SSL.verify_mode = ssl.CERT_NONE


def _build_url(app_id: str, page: int, sort: str = "mostrecent") -> str:
    """构建 RSS Feed URL"""
    return (
        f"https://itunes.apple.com/us/rss/customerreviews/"
        f"page={page}/id={app_id}/sortby={sort}/json"
    )


def _fetch_page(url: str, timeout: int = 15) -> Optional[dict]:
    """抓取单页 RSS Feed（同步函数，由 asyncio.to_thread 包装调用）

    重试策略:
      第1次: 严格 SSL
      第2次: 宽松 SSL（跳过证书验证）
      第3次: 宽松 SSL + 等待
    """
    last_error = None
    for attempt in range(3):
        try:
            use_strict = (attempt == 0)
            ctx = ssl.create_default_context() if use_strict else _PERMISSIVE_SSL
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AppReviewInsights/1.0 (RSS collector)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
                elif resp.status == 429:
                    wait = 5 * (attempt + 1)
                    logger.warning("HTTP 429, wait %ds", wait)
                    time.sleep(wait)
                    last_error = f"HTTP 429"
                    continue
                else:
                    logger.error("HTTP %d for %s", resp.status, url)
                    return None
        except ssl.CertificateError:
            logger.warning("SSL error, retrying with relaxed mode")
            last_error = "SSL error"
            continue
        except urllib.error.URLError as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return None

    logger.error("Failed after 3 retries: %s", last_error)
    return None


def _extract_reviews(entries: list, fetch_page: int) -> list[dict]:
    """从 RSS Feed entry 列表中提取评论字段"""
    reviews = []

    for entry in entries:
        # 没有 im:rating 的条目不是评论
        rating_label = entry.get("im:rating", {}).get("label")
        if rating_label is None:
            continue

        def _get(*keys):
            c = entry
            for k in keys:
                if isinstance(c, dict):
                    c = c.get(k)
                else:
                    return None
            return c

        review = {
            "review_id": str(_get("id", "label") or ""),
            "author": str(_get("author", "name", "label") or ""),
            "title": str(_get("title", "label") or ""),
            "content": str(_get("content", "label") or ""),
            "rating": int(rating_label),
            "version": str(_get("im:version", "label") or "") or None,
            "date": str(_get("updated", "label") or "") or None,
            "fetch_page": fetch_page,
        }

        if 1 <= review["rating"] <= 5:
            reviews.append(review)

    return reviews


async def fetch_reviews(
    app_id: str,
    db: AsyncSession,
    task_id: str,
    max_pages: int = 10,
    sort: str = "mostrecent",
    on_progress: Optional[Callable] = None,
) -> list[RawReview]:
    """分页抓取 RSS Feed，写入 DB，回调进度

    参数:
      app_id: Apple App ID
      db: 数据库 session
      task_id: 关联的分析任务 ID
      max_pages: 最大页数（每页50条）
      sort: 排序方式 mostrecent(最新) / mosthelpful(最有帮助)
      on_progress: 每页完成后的回调 (page, reviews, total)

    返回:
      RawReview 对象列表
    """
    import asyncio

    all_reviews: list[dict] = []
    orm_objects: list[RawReview] = []

    for page in range(1, max_pages + 1):
        url = _build_url(app_id, page, sort)
        logger.info("Fetching page %d/%d", page, max_pages)

        data = await asyncio.to_thread(_fetch_page, url)
        if data is None:
            logger.warning("Page %d failed, skipping", page)
            continue

        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        if not entries:
            logger.info("Page %d empty, stopping pagination", page)
            break

        page_reviews = _extract_reviews(entries, page)
        all_reviews.extend(page_reviews)

        # 写入 DB
        for r in page_reviews:
            orm = RawReview(
                task_id=task_id,
                review_id=r["review_id"],
                source="rss",
                title=r["title"],
                content=r["content"],
                rating=r["rating"],
                author=r["author"],
                version=r["version"],
                date=r["date"],
                fetch_page=r["fetch_page"],
            )
            db.add(orm)
            orm_objects.append(orm)

        await db.commit()

        logger.info("Page %d: %d reviews (total %d)", page, len(page_reviews), len(all_reviews))

        # 进度回调
        if on_progress:
            await on_progress(page, page_reviews, len(all_reviews))

        if page < max_pages:
            await asyncio.sleep(1.2)

    return orm_objects
