"""Tests for testgen.py test case generation"""
import pytest
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from app.services.testgen import generate_test_cases
from app.services.testgen import GeneratedTest, TestSuite as ServiceTestSuite


@pytest.mark.asyncio
async def test_generate_test_cases():
    async def _mock_invoke(inputs):
        return ServiceTestSuite(test_cases=[
            GeneratedTest(
                description="Verify crash fix",
                steps=["Open app", "Navigate to workout", "Verify no crash"],
                expected="App does not crash",
                requirement_id=1,
                source_review_ids=["r1", "r2"],
            )
        ])

    class MockLLM:
        def with_structured_output(self, schema, **kwargs):
            return RunnableLambda(_mock_invoke)

    requirements = [
        {"id": 1, "title": "Fix crashes", "description": "Fix app crashes",
         "source_review_ids": ["r1", "r2"], "priority": "p0", "version": "v1"},
    ]
    result = await generate_test_cases(requirements, MockLLM())
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["description"] == "Verify crash fix"
    assert len(result[0]["steps"]) == 3
    assert result[0]["requirement_id"] == 1
    assert "r1" in result[0]["source_review_ids"]


@pytest.mark.asyncio
async def test_generate_test_cases_empty():
    assert await generate_test_cases([], None) == []
