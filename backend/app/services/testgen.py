"""测试用例生成 Agent — 使用 LangChain LCEL Chain"""

from typing import Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate


class GeneratedTest(BaseModel):
    description: str = Field(description="测试用例描述")
    steps: list[str] = Field(description="测试步骤列表")
    expected: str = Field(description="预期结果")
    requirement_id: int = Field(description="关联的需求 ID")
    source_review_ids: list[str] = Field(description="关联的评论 ID 列表")


class TestSuite(BaseModel):
    test_cases: list[GeneratedTest]


PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个 QA 工程师。基于 PRD 需求编写测试用例。\n"
               "每个用例包含：描述、测试步骤、预期结果、关联的 requirement_id 和支撑该需求的评论 ID。\n"
               "测试步骤应当是具体、可操作的操作序列。"),
    ("human", "需求列表:\n{requirements_text}"),
])


async def generate_test_cases(requirements: list[dict], llm) -> list[dict]:
    """基于 PRD 需求生成测试用例

    输入 requirements: list[dict] 每个包含 id, title, description, source_review_ids
    输出 list[dict]: description, steps, expected, requirement_id, source_review_ids
    """
    if not requirements:
        return []

    req_text = "\n".join(
        f"- (ID:{r.get('id','?')}) [{r.get('priority','p2')}] {r.get('title','')}: "
        f"{r.get('description','')} [关联评论:{','.join(str(x) for x in (r.get('source_review_ids') or []))}]"
        for r in requirements
    )

    chain = PROMPT | llm.with_structured_output(TestSuite)

    try:
        result = await chain.ainvoke({"requirements_text": req_text})
        return [
            {
                "description": tc.description,
                "steps": tc.steps,
                "expected": tc.expected,
                "requirement_id": tc.requirement_id,
                "source_review_ids": tc.source_review_ids,
            }
            for tc in result.test_cases
        ]
    except Exception:
        return []
