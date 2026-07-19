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
               "V1 是 Quick Wins（高优先级、低复杂度），V2 是核心功能，V3 是未来规划。\n"
               "每个 finding 已标注涉及的 App 版本号，在需求的 description 中写明该问题出现在哪些版本（如\"影响 v8.4.25 及之后版本\"），"
               "以便开发和测试定位。"),
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

    def _val(f, key, default=""):
        """安全取值：支持 ORM 对象和 dict"""
        if hasattr(f, key):
            return getattr(f, key) or default
        return f.get(key, default)

    findings_text = "\n".join(
        f"- (ID:{_val(f, 'id', '?')}) [{_val(f, 'confidence', 'low')}] "
        f"{_val(f, 'topic', '')}: {_val(f, 'description', '')} "
        f"[支撑{_val(f, 'sample_count', 0)}条评论]"
        f"[涉及版本:{','.join(str(v) for v in (_val(f, 'affected_versions', []) or []))}]"
        for f in findings
    )

    chain = PROMPT | llm.with_structured_output(PRDOutput)

    try:
        result = await chain.ainvoke({"findings_text": findings_text})
        if result is None:
            return PRDOutput(overview="PRD 生成返回空", requirements=[])
        return result
    except Exception:
        return PRDOutput(
            overview="PRD 生成失败（LLM 暂不可用）",
            requirements=[],
        )
