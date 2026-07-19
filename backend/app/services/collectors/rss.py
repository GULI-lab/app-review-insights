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

# 真实浏览器 UA（自定义 UA 容易被 Apple 屏蔽）
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
}


def _build_url(storefront: str, app_id: str, page: int, sort: str = "mostrecent") -> str:
    """构建 RSS Feed URL

    Apple 在 2026 年 7 月静默变更了 RSS Feed 路由：
      旧格式（已失效）: /{storefront}/rss/customerreviews/...
      新格式（可用）  : /rss/customerreviews/...?cc={storefront}
    旧路径返回空 200 响应（静默屏蔽），需使用 cc 查询参数指定 storefront。
    """
    return (
        f"https://itunes.apple.com/rss/customerreviews/"
        f"page={page}/id={app_id}/sortby={sort}/json"
        f"?cc={storefront}"
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
            req = urllib.request.Request(url, headers=_BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
                elif resp.status == 429:
                    wait = int(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                    logger.warning("HTTP 429, Retry-After=%ds", wait)
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
        except urllib.error.HTTPError as e:
            logger.error("HTTP %d %s for %s", e.code, e.reason, url)
            return None
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


def _extract_reviews(feed_data: dict, fetch_page: int) -> list[dict]:
    """从 RSS Feed 中健壮地提取评论字段

    注意: Apple RSS 在只有 1 条评论时 entry 是 dict 而非 list。
    """
    feed = feed_data.get("feed", {})
    entries = feed.get("entry", [])
    # 核心修复：单条评论时 entry 是字典，统一为列表
    if isinstance(entries, dict):
        entries = [entries]
    if not entries:
        return []

    reviews = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        # 没有 im:rating 的条目不是评论
        rating_label = entry.get("im:rating", {}).get("label")
        if rating_label is None:
            continue

        try:
            rating = int(rating_label)
        except (ValueError, TypeError):
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
            "rating": rating,
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
    storefront: str = "us",
    on_progress: Optional[Callable] = None,
) -> list[RawReview]:
    """分页抓取 RSS Feed，写入 DB，回调进度

    参数:
      app_id: Apple App ID
      db: 数据库 session
      task_id: 关联的分析任务 ID
      max_pages: 最大页数（每页50条）
      sort: 排序方式 mostrecent(最新) / mosthelpful(最有帮助)
      storefront: 国家代码（us/cn/jp 等），反映 App Store 区域
      on_progress: 每页完成后的回调 (page, reviews, total)

    返回:
      RawReview 对象列表
    """
    import asyncio

    all_reviews: list[dict] = []
    orm_objects: list[RawReview] = []
    consecutive_empty = 0  # 连续空页计数，用于检测限流
    max_consecutive_empty = 3  # 最多容忍连续空页数

    for page in range(1, max_pages + 1):
        url = _build_url(storefront, app_id, page, sort)
        logger.info("Fetching page %d/%d (storefront=%s)", page, max_pages, storefront)

        data = await asyncio.to_thread(_fetch_page, url)
        if data is None:
            logger.warning("Page %d failed, skipping", page)
            continue

        page_reviews = _extract_reviews(data, page)
        if not page_reviews:
            # 诊断：区分"无评论"还是"接口被限流屏蔽"
            feed = data.get("feed", {})
            has_entry_key = "entry" in feed
            feed_keys = list(feed.keys())
            logger.info(
                "Page %d empty | has_entry_key=%s | feed_keys=%s | storefront=%s",
                page, has_entry_key, feed_keys, storefront,
            )
            if not has_entry_key:
                # 没有 entry 字段 = Apple 静默限流
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    logger.warning(
                        "Consecutive empty pages (%d), likely rate-limited by Apple. Stopping.",
                        consecutive_empty,
                    )
                    break
                if page == 1:
                    logger.warning(
                        "Storefront '%s' returned empty feed (no 'entry' field) — "
                        "may be rate-limited or this app has no reviews in this region",
                        storefront,
                    )
                # 指数退避：3s → 6s → 12s，等待限流解除
                backoff = 3 * (2 ** (consecutive_empty - 1))
                logger.info("Rate-limited, backing off %ds before retry...", backoff)
                await asyncio.sleep(backoff)
                continue
            # 有 entry 字段但无评论 → 数据到底了
            break

        all_reviews.extend(page_reviews)
        consecutive_empty = 0  # 成功获取评论后重置限流计数

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
            await asyncio.sleep(3)

    return orm_objects
