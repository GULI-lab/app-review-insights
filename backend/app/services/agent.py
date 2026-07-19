"""主题发现 Agent — 使用 LangChain ChatDeepSeek + LCEL Chain"""

from typing import Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate


class TopicFinding(BaseModel):
    topic: str = Field(description="话题名称")
    confidence: str = Field(description="置信度: high/medium/low")
    description: str = Field(description="描述用户的问题或需求")
    supporting_review_ids: list[str] = Field(description="支撑的评论ID列表")
    sample_count: int = Field(description="支撑评论数")
    representative_excerpts: list[str] = Field(description="代表性引文")
    contradicting_evidence: list[str] = Field(description="矛盾证据")


class AnalysisResult(BaseModel):
    findings: list[TopicFinding]


PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个 App Store 评论分析师。从评论中动态发现用户关心的话题。\n"
               "对每个话题：\n"
               "  1. 命名 topic\n"
               "  2. 评估置信度 high/medium/low（≥5条支撑=high, ≥2条=medium）\n"
               "  3. 描述用户的问题或需求\n"
               "  4. 列出支撑评论的ID\n"
               "  5. 摘录代表性引文\n"
               "  6. 列出矛盾证据（如果有相反观点的评论）\n"
               "  7. 如果某个finding支撑评论<2条，confidence设为low"),
    ("human", "分析目标: {goal}\n\n评论数据:\n{reviews_text}"),
])


async def analyze_reviews(reviews: list[dict], llm, goal: str = "") -> list[dict]:
    """使用 LLM 分析评论块，发现主题

    返回 finding dict 列表（格式与现有代码一致）。
    """
    if not reviews:
        return []

    chain = PROMPT | llm.with_structured_output(AnalysisResult)

    all_results = []
    # 分块，每块最多 50 条
    for i in range(0, len(reviews), 50):
        block = reviews[i:i + 50]
        reviews_text = "\n---\n".join(
            f"[ID:{r.get('review_id','?')}][{r.get('rating','?')}★] "
            f"{r.get('title','')} {r.get('content','')}"
            for r in block
        )

        try:
            result = await chain.ainvoke({"goal": goal, "reviews_text": reviews_text})
            findings = result.findings if result else []
        except Exception:
            findings = []

        for f in findings:
            all_results.append({
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
            })

    return all_results
