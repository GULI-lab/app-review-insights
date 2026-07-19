"""Tests for agent.py topic discovery"""
import pytest
from langchain_core.runnables import RunnableLambda
from app.services.agent import analyze_reviews


def _make_mock_chain(schema):
    """创建返回空 schema 实例的 mock chain（LCEL Runnable）"""
    async def _invoke(inputs):
        return schema()
    return RunnableLambda(_invoke)


class MockLLM:
    """模拟 LLM 返回结构化结果"""
    def with_structured_output(self, schema, **kwargs):
        return _make_mock_chain(schema)


class MockLLMWithFindings:
    """模拟 LLM 返回具体发现结果"""
    def with_structured_output(self, schema, **kwargs):
        async def _invoke(inputs):
            from pydantic import BaseModel
            class TopicFinding(BaseModel):
                topic: str
                confidence: str
                description: str
                supporting_review_ids: list[str]
                sample_count: int
                representative_excerpts: list[str]
                contradicting_evidence: list[str]
            class AnalysisResult(BaseModel):
                findings: list[TopicFinding]
            return AnalysisResult(findings=[
                TopicFinding(
                    topic="crash issue",
                    confidence="high",
                    description="App crashes frequently",
                    supporting_review_ids=["r1", "r2", "r3"],
                    sample_count=3,
                    representative_excerpts=["it crashes"],
                    contradicting_evidence=[],
                )
            ])
        return RunnableLambda(_invoke)


@pytest.mark.asyncio
async def test_analyze_reviews_returns_findings():
    reviews = [
        {"review_id": "r1", "content": "it crashes a lot", "title": "crash", "rating": 1},
        {"review_id": "r2", "content": "keeps crashing", "title": "bug", "rating": 2},
    ]
    llm = MockLLMWithFindings()
    result = await analyze_reviews(reviews, llm, goal="find crashes")
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["topic"] == "crash issue"
    assert result[0]["confidence"] == "high"
    assert result[0]["is_model_generated"] is True
    assert result[0]["is_statistical"] is False
    assert result[0]["status"] == "approved"


@pytest.mark.asyncio
async def test_analyze_reviews_empty():
    assert await analyze_reviews([], None) == []


@pytest.mark.asyncio
async def test_analyze_reviews_fallback_on_error():
    """LLM 失败时返回空列表"""
    class FailingLLM:
        def with_structured_output(self, schema, **kwargs):
            async def _invoke(inputs):
                raise RuntimeError("LLM unavailable")
            return RunnableLambda(_invoke)

    reviews = [{"review_id": "r1", "content": "text", "title": "", "rating": 3}]
    result = await analyze_reviews(reviews, FailingLLM())
    assert result == []
