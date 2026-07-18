"""LangChain Agent 分析服务

使用 LLM 从评论中动态发现主题（非预定义分类），
收集证据，检查矛盾，生成结构化Finding。
"""
from typing import Any
from pydantic import BaseModel


class TopicFinding(BaseModel):
    """单个分析发现"""
    topic: str
    confidence: str  # high/medium/low
    description: str
    supporting_review_ids: list[str]
    sample_count: int
    representative_excerpts: list[str]
    contradicting_evidence: list[str]


class AnalysisResult(BaseModel):
    """分析结果"""
    findings: list[TopicFinding]


async def analyze_reviews(reviews: list[dict], llm, goal: str = "") -> list[dict]:
    """使用 LLM 分析评论块，发现主题

    每条评论格式: {"review_id": str, "content": str, "title": str, "rating": int}

    返回 finding dict 列表。
    """
    if not reviews:
        return []

    reviews_text = "\n---\n".join(
        f"[ID:{r.get('review_id','?')}][{r.get('rating','?')}★] "
        f"{r.get('title','')} {r.get('content','')}"
        for r in reviews[:50]
    )

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个 App Store 评论分析师。从评论中动态发现用户关心的话题。\n"
                "对每个话题：\n"
                "  1. 命名 topic\n"
                "  2. 评估置信度 high/medium/low（≥5条支撑=high, ≥2条=medium）\n"
                "  3. 描述用户的问题或需求\n"
                "  4. 列出支撑评论的ID\n"
                "  5. 摘录代表性引文\n"
                "  6. 列出矛盾证据（如果有相反观点的评论）\n"
                "  7. 如果某个finding支撑评论<2条，confidence设为low\n\n"
                "输出JSON格式。"
            ),
        },
        {
            "role": "user",
            "content": f"分析目标: {goal}\n\n评论数据:\n{reviews_text}",
        },
    ]

    try:
        result = await llm.chat_structured(messages, AnalysisResult)
        return [
            {
                "topic": f.topic,
                "confidence": f.confidence,
                "description": f.description,
                "supporting_review_ids": f.supporting_review_ids,
                "sample_count": f.sample_count,
                "representative_excerpts": f.representative_excerpts,
                "contradicting_evidence": f.contradicting_evidence,
                "is_statistical": False,
                "is_model_generated": True,
                "was_downgraded": False,
                "downgrade_reason": None,
                "status": "approved",
            }
            for f in result.findings
        ]
    except Exception as e:
        # 降级: 尝试纯文本解析
        try:
            result = await llm.chat(messages)
            import json
            parsed = json.loads(result)
            findings = parsed if isinstance(parsed, list) else parsed.get("findings", [])
            return [
                {
                    "topic": f.get("topic", "unknown"),
                    "confidence": f.get("confidence", "low"),
                    "description": f.get("description", ""),
                    "supporting_review_ids": f.get("supporting_review_ids", []),
                    "sample_count": f.get("sample_count", 0),
                    "representative_excerpts": f.get("representative_excerpts", []),
                    "contradicting_evidence": f.get("contradicting_evidence", []),
                    "is_statistical": False,
                    "is_model_generated": True,
                    "was_downgraded": False,
                    "downgrade_reason": None,
                    "status": "approved",
                }
                for f in findings
            ]
        except Exception:
            return []
