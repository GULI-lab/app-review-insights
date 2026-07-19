"""Tests for planner.py evidence evaluation and PRD generation"""
import pytest
from langchain_core.runnables import RunnableLambda
from app.services.planner import evaluate_evidence, generate_prd, PRDOutput


@pytest.mark.asyncio
async def test_evaluate_evidence_sufficient():
    findings = [
        {"topic": "crash", "sample_count": 5, "confidence": "high", "was_downgraded": False},
        {"topic": "ui", "sample_count": 2, "confidence": "medium", "was_downgraded": False},
        {"topic": "feature", "sample_count": 1, "confidence": "low", "was_downgraded": False},
    ]
    result = await evaluate_evidence(findings)
    # sample_count >= 5: 充分，保持
    assert result[0]["was_downgraded"] is False
    # sample_count 2: 有限
    assert result[1]["was_downgraded"] is False
    # sample_count 1: 不足 → 降级
    assert result[2]["was_downgraded"] is True
    assert "不足" in result[2]["downgrade_reason"]


@pytest.mark.asyncio
async def test_generate_prd_returns_prdoutput():
    async def _mock_invoke(inputs):
        return PRDOutput(
            overview="Test PRD overview",
            requirements=[
                PRDOutput.PRDRequirement(
                    title="Fix crashes",
                    description="Fix app crashes",
                    priority="p0",
                    version="v1",
                    source_finding_ids=[1],
                )
            ],
        )

    class MockLLM:
        def with_structured_output(self, schema, **kwargs):
            return RunnableLambda(_mock_invoke)

    findings = [
        {"id": 1, "topic": "crash", "confidence": "high", "description": "App crashes",
         "sample_count": 5, "supporting_review_ids": ["r1", "r2"]},
    ]
    result = await generate_prd(findings, MockLLM())
    assert isinstance(result, PRDOutput)
    assert len(result.requirements) == 1
    assert result.requirements[0].priority == "p0"
    assert result.requirements[0].version == "v1"


@pytest.mark.asyncio
async def test_generate_prd_empty():
    result = await generate_prd([], None)
    assert isinstance(result, PRDOutput)
    assert len(result.requirements) == 0
