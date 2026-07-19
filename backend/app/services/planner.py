"""证据评估 + PRD 生成 — 使用 LangChain LCEL Chain"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate


class PRDOutput(BaseModel):
    """结构化 PRD 输出"""

    class PRDRequirement(BaseModel):
        title: str = Field(description="需求标题")
        description: str = Field(description="需求详细描述")
        priority: str = Field(description="优先级: p0/p1/p2")
        version: str = Field(description="版本规划: v1/v2/v3")
        source_finding_ids: list[int] = Field(description="关联的 Finding ID 列表")

    overview: str = Field(description="PRD 概述")
    requirements: list[PRDRequirement] = Field(description="需求列表")


PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个产品经理。基于用户评论分析发现，编写产品需求文档(PRD)。\n"
               "每个需求必须包含：标题、描述、优先级(P0/P1/P2)、版本规划(V1/V2/V3)、关联的 Finding ID。\n"
               "V1 是 Quick Wins（高优先级、低复杂度），V2 是核心功能，V3 是未来规划。"),
    ("human", "分析发现:\n{findings_text}\n\n请生成 PRD。"),
])


async def evaluate_evidence(findings: list[dict], llm=None) -> list[dict]:
    """评估证据充分性: 三级标签（纯规则驱动，不调用 LLM）"""
    evaluated = []
    for f in findings:
        if f.get("sample_count", 0) >= 5:
            pass  # 充分
        elif f.get("sample_count", 0) >= 2:
            pass  # 有限
        else:
            f["was_downgraded"] = True
            f["downgrade_reason"] = f"支撑评论不足({f.get('sample_count',0)}条)"
        evaluated.append(f)
    return evaluated


async def generate_prd(findings: list, llm) -> PRDOutput:
    """基于分析发现生成结构化 PRD"""
    if not findings:
        return PRDOutput(overview="暂无分析发现，无法生成 PRD。", requirements=[])

    findings_text = "\n".join(
        f"- (ID:{f.get('id','?')}) [{f.get('confidence','low')}] {f.get('topic','')}: {f.get('description','')}"
        for f in findings
    )

    chain = PROMPT | llm.with_structured_output(PRDOutput)

    try:
        return await chain.ainvoke({"findings_text": findings_text})
    except Exception:
        return PRDOutput(
            overview="PRD 生成失败（LLM 暂不可用）",
            requirements=[],
        )
