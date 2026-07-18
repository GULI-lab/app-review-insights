"""测试用例生成"""
from typing import Any
from pydantic import BaseModel


class GeneratedTest(BaseModel):
    description: str
    steps: list[str]
    expected: str


class TestSuite(BaseModel):
    test_cases: list[GeneratedTest]


async def generate_test_cases(requirements: list[dict], llm) -> list[dict]:
    """基于 PRD 需求生成测试用例"""
    if not requirements:
        return []

    req_text = "\n".join(f"- {r.get('title','')}: {r.get('description','')}" for r in requirements)

    messages = [
        {
            "role": "system",
            "content": "你是一个 QA 工程师。基于 PRD 需求编写测试用例。每个用例包含描述、步骤、预期结果。"
        },
        {
            "role": "user",
            "content": f"需求:\n{req_text}\n\n请为每个需求生成测试用例。"
        }
    ]

    try:
        result = await llm.chat_structured(messages, TestSuite)
        return [tc.model_dump() for tc in result.test_cases]
    except Exception:
        return []
