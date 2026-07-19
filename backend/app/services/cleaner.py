"""评论清洗去重服务（规则驱动）

复用 demo/cleaner_demo.py 的确定性清洗逻辑：
  1. 重复检测（同author+同rating+日期差≤3d+Jaccard>0.9）
  2. 无效过滤（<5字符/纯标点/纯emoji）
  3. 广告过滤（含URL/促销关键词）
  4. 字段规范化
  5. 隐私脱敏
  6. 质量评分
"""
import re
import logging
from collections import Counter
from datetime import datetime
from typing import List, Optional, Tuple

from app.models.db import RawReview, CleanedReview

logger = logging.getLogger("cleaner")


# ---------- 工具函数 ----------

def _jaccard_similarity(t1: str, t2: str) -> float:
    """Jaccard 字符级相似度"""
    if not t1 or not t2:
        return 0.0
    c1 = set(t1.lower().replace(" ", ""))
    c2 = set(t2.lower().replace(" ", ""))
    inter = c1 & c2
    union = c1 | c2
    return len(inter) / len(union) if union else 0.0


_MEANINGLESS = {
    "ok", "good", "bad", "nice", "great", "fine", "no", "yes",
    "好", "不好", "可以", "不错", "一般", "还行", "差", "很好",
}

_AD_PATTERNS = [
    r"https?://\S+", r"www\.\S+",
    r"\bfree\b", r"\bdiscount\b", r"\bbuy\s*now\b",
]


# ---------- 清洗规则 ----------

def _is_invalid(content: str, title: str) -> Tuple[bool, str]:
    """检测无效评论"""
    combined = (title + " " + content).strip()
    if not combined:
        return True, "内容为空"
    if len(combined) < 5:
        return True, "内容过短(<5字符)"
    text_only = re.sub(r"[a-zA-Z0-9一-鿿\s]", "", combined)
    if text_only and len(text_only) / len(combined) > 0.8:
        return True, "仅标点/emoji"
    if re.fullmatch(r"\d+[\s\d]*", combined):
        return True, "仅数字"
    words = combined.lower().split()
    if words and all(w.strip(".,!? ") in _MEANINGLESS for w in words):
        return True, "仅无意义词语"
    return False, ""


def _is_ad(content: str) -> bool:
    """检测广告/垃圾内容（匹配 ≥2 个模式才判定）"""
    combined = content.lower()
    count = sum(1 for p in _AD_PATTERNS if re.search(p, combined))
    return count >= 2


def _sanitize(text: str) -> str:
    """脱敏隐私信息（邮箱/电话）"""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text)
    text = re.sub(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]\d{4}", "[PHONE]", text)
    text = re.sub(r"1[3-9]\d[-.\s]?\d{4}[-.\s]?\d{4}", "[PHONE]", text)
    return text


def dedup_cleaned(cleaned: List[CleanedReview]) -> Tuple[List[CleanedReview], dict]:
    """对已入库的 CleanedReview 执行去重（不重新执行脱敏/无效/广告过滤）"""
    stats = {"input_count": len(cleaned), "output_count": 0, "duplicates_removed": 0}
    items = []
    for r in cleaned:
        items.append({
            "obj": r, "content": r.content or "", "title": r.title or "",
            "rating": r.rating, "author": r.author or "", "date": r.date or "",
        })
    kept = []
    for item in items:
        is_dup = False
        for existing in kept:
            if (item["author"] and existing["author"]
                    and item["author"] == existing["author"]
                    and item["rating"] == existing["rating"]):
                try:
                    d1 = item["date"][:10]
                    d2 = existing["date"][:10]
                    diff = abs((datetime.fromisoformat(d1) - datetime.fromisoformat(d2)).days)
                    if diff > 3:
                        continue
                except (ValueError, TypeError, IndexError):
                    continue
                sim = _jaccard_similarity(
                    item["title"] + item["content"],
                    existing["title"] + existing["content"],
                )
                if sim > 0.9:
                    is_dup = True
                    stats["duplicates_removed"] += 1
                    break
        if not is_dup:
            kept.append(item)
    kept_objects = [item["obj"] for item in kept]
    stats["output_count"] = len(kept_objects)
    return kept_objects, stats


def _quality_score(content: str, title: str) -> float:
    """0-1 质量评分"""
    score = 0.5
    total_len = len(content) + len(title)
    if total_len > 50:
        score += 0.2
    if total_len > 200:
        score += 0.15
    if title.strip():
        score += 0.1
    if re.search(r"[a-zA-Z]{3,}|[一-鿿]{2,}", content):
        score += 0.1
    if re.search(r"(.)\1{4,}", content):
        score -= 0.15
    if content and content.isupper():
        score -= 0.1
    return max(0.0, min(1.0, score))


# ---------- 主函数 ----------

async def clean_reviews(
    raw_reviews: List[RawReview],
    task_id: str,
    llm=None,
) -> Tuple[List[CleanedReview], dict]:
    """执行完整清洗流程

    参数:
      llm: 传入时启用 AI 广告/垃圾检测（异步），否则使用纯规则

    返回:
      (清理后的 CleanedReview 列表, 清洗统计)
    """
    stats = {
        "input_count": len(raw_reviews),
        "invalid_filtered": 0,
        "ad_filtered": 0,
        "ai_filtered": 0,
        "duplicates_removed": 0,
        "output_count": 0,
    }

    # 1. 构造中间字典方便处理
    items = []
    for r in raw_reviews:
        items.append({
            "raw": r,
            "content": r.content or "",
            "title": r.title or "",
            "rating": r.rating,
            "author": r.author or "",
            "date": r.date or "",
        })

    # 2. 脱敏
    for item in items:
        item["content"] = _sanitize(item["content"])
        item["title"] = _sanitize(item["title"])

    # 3. 无效过滤（规则）
    valid = []
    for item in items:
        is_inv, reason = _is_invalid(item["content"], item["title"])
        if is_inv:
            stats["invalid_filtered"] += 1
        else:
            valid.append(item)

    # 4. 广告过滤（规则）
    non_ad = []
    for item in valid:
        if _is_ad(item["content"]):
            stats["ad_filtered"] += 1
        else:
            non_ad.append(item)

    # 4b. AI 过滤（语义级别垃圾/广告/模板/机翻）
    after_ai = non_ad
    if llm is not None:
        from app.services.ai_cleaner import ai_filter
        after_ai, ai_removed = await ai_filter(non_ad, llm)
        stats["ai_filtered"] = ai_removed

    # 5. 重复检测（基于内容相似度）
    kept = []
    for item in non_ad:
        is_dup = False
        for existing in kept:
            if (item["author"] and existing["author"]
                    and item["author"] == existing["author"]
                    and item["rating"] == existing["rating"]):
                # 日期差
                try:
                    d1 = item["date"][:10]
                    d2 = existing["date"][:10]
                    diff = abs((datetime.fromisoformat(d1) - datetime.fromisoformat(d2)).days)
                    if diff > 3:
                        continue
                except (ValueError, TypeError, IndexError):
                    continue
                sim = _jaccard_similarity(
                    item["title"] + item["content"],
                    existing["title"] + existing["content"],
                )
                if sim > 0.9:
                    is_dup = True
                    stats["duplicates_removed"] += 1
                    break
        if not is_dup:
            kept.append(item)

    # 6. 生成 CleanedReview
    cleaned = []
    for item in kept:
        cr = CleanedReview(
            task_id=task_id,
            review_id=item["raw"].review_id,
            source=item["raw"].source,
            title=item["title"],
            content=item["content"],
            rating=item["rating"],
            author=item["author"],
            version=item["raw"].version,
            date=item["date"],
            quality_score=round(_quality_score(item["content"], item["title"]), 2),
        )
        cleaned.append(cr)

    stats["output_count"] = len(cleaned)
    stats["avg_quality"] = round(
        sum(cr.quality_score for cr in cleaned) / max(len(cleaned), 1), 2
    ) if cleaned else 0
    return cleaned, stats
