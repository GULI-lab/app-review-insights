"""证据评估 + 版本规划 + PRD 生成"""
from typing import Any
from pydantic import BaseModel


class EvaluatedFinding(BaseModel):
    """带评估的发现"""
    topic: str
    confidence: str
    evidence_level: str  # 充分/有限/不足
    description: str


class PRDPlan(BaseModel):
    """版本规划"""
    v1: list[str]  # Quick Wins
    v2: list[str]  # Core
    v3: list[str]  # Future


async def evaluate_evidence(findings: list[dict], llm) -> list[dict]:
    """评估证据充分性: 三级标签"""
    evaluated = []
    for f in findings:
        if f.get("sample_count", 0) >= 5:
            level = "充分"
        elif f.get("sample_count", 0) >= 2:
            level = "有限"
        else:
            level = "不足"
            f["was_downgraded"] = True
            f["downgrade_reason"] = f"支撑评论不足({f.get('sample_count',0)}条)"
        evaluated.append(f)
    return evaluated


async def generate_prd(findings: list[dict], llm) -> str:
    """生成 Markdown 格式 PRD"""
    if not findings:
        return "暂无分析发现，无法生成 PRD。"

    findings_text = "\n".join(
        f"- [{f.get('confidence','low')}] {f.get('topic','')}: {f.get('description','')}"
        for f in findings
    )

    messages = [
        {
            "role": "system",
            "content": "你是一个产品经理。基于用户评论分析发现，编写产品需求文档(PRD)。\n"
                       "格式: Markdown，含概述、版本规划(V1/V2/V3)、各版本功能列表、验收标准。\n"
                       "每个需求需标注优先级(P0/P1/P2)和关联的评论发现。"
        },
        {
            "role": "user",
            "content": f"分析发现:\n{findings_text}\n\n请生成PRD。"
        }
    ]

    try:
        return await llm.chat(messages)
    except Exception:
        return "## PRD\n\n(LLM 暂不可用，请在配置 API Key 后重新生成)"
