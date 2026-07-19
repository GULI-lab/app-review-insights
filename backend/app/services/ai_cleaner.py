"""AI 驱动的评论清洗 — 检测垃圾、广告、无效内容

与规则清洗互补：规则清洗处理明显可判定的情况（空内容、纯数字），
AI 处理语义层面的判断（推广软文、模版好评、机翻内容、跨语言广告）。
"""
import asyncio
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger("ai_cleaner")


class ClassificationResult(BaseModel):
    """AI 对单条评论的清洗判定"""
    is_spam: bool = Field(default=False, description="是否为垃圾/推广/广告评论")
    reason: str = Field(default="", description="判定理由")
    should_remove: bool = Field(default=False, description="是否应从分析中移除")
    category: str = Field(default="normal", description="类别: normal/spam/ad/promotion/machine_translated/template")


PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个 App Store 评论质量审核员。判断每条评论是否需要从分析中排除。

排除条件（符合任一即可排除）:
1. **垃圾/广告**: 包含推广链接、推销其他 App、刷榜/水军内容
2. **模板好评**: 明显复制粘贴的通用好评，不同 App 间通用的内容
3. **机翻痕迹明显**: 中文评论但语法完全混乱，无法理解真实反馈
4. **完全无关内容**: 与 App 完全无关的讨论

保留条件:
- 真实用户的正面/负面反馈（即使语言简单、拼写错误）
- 短评如"好用"、"太差了" — 虽简短但有真实情感，不应排除

输出 JSON，不要多余文字。"""),
    ("human", "评论标题: {title}\n评论内容: {content}\n评分: {rating}星"),
])


async def classify_review(title: str, content: str, rating: int, llm: Any) -> ClassificationResult:
    """用 LLM 判断单条评论是否为垃圾/无效"""
    try:
        chain = PROMPT | llm.with_structured_output(ClassificationResult)
        result = await chain.ainvoke({
            "title": title or "",
            "content": content or "",
            "rating": rating,
        })
        return result or ClassificationResult()
    except Exception as e:
        logger.warning("AI classify failed (will keep review): %s", e)
        return ClassificationResult()


async def ai_filter(items: list[dict], llm: Any, max_concurrent: int = 10) -> tuple[list[dict], int]:
    """批量 AI 检测，返回 (保留的items, 过滤数)"""
    sem = asyncio.Semaphore(max_concurrent)

    async def _classify(item: dict) -> tuple[bool, dict]:
        async with sem:
            result = await classify_review(
                item.get("title", ""),
                item.get("content", ""),
                item.get("rating", 3),
                llm,
            )
        if result.should_remove:
            return False, item
        return True, item

    tasks = [_classify(item) for item in items]
    results = await asyncio.gather(*tasks)

    kept = []
    removed = 0
    for ok, item in results:
        if ok:
            kept.append(item)
        else:
            removed += 1
    return kept, removed
