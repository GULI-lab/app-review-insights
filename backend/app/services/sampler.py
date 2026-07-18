"""评论采样/分块服务"""
import re
import random
from typing import Any


def high_risk_scan(reviews: list[dict], risk_keywords: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """高危关键词扫描"""
    if risk_keywords is None:
        risk_keywords = ["crash", "bug", "refund", "broken", "error", "can't", "freeze",
                         "闪退", "崩溃", "付费", "退款"]
    pattern = re.compile("|".join(re.escape(k) for k in risk_keywords), re.IGNORECASE)
    high_risk = []
    normal = []
    for r in reviews:
        text = (r.get("content") or "") + " " + (r.get("title") or "")
        if pattern.search(text):
            high_risk.append(r)
        else:
            normal.append(r)
    return high_risk, normal


def split_blocks(reviews: list[dict], block_size: int = 100) -> list[list[dict]]:
    """拆分为固定大小的块"""
    return [reviews[i:i + block_size] for i in range(0, len(reviews), block_size)]


def stratified_sample(reviews: list[dict], target_count: int = 200, seed: int = 42) -> list[dict]:
    """简单分层抽样"""
    if len(reviews) <= target_count:
        return reviews
    random.seed(seed)
    return random.sample(reviews, min(target_count, len(reviews)))
