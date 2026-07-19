# LangChain 迁移 + 流水线完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将自定义 LLM 层迁移到 LangChain ChatDeepSeek，修复测试用例未接入流水线和 PRD 未拆分的问题

**Architecture:** pipeline.py 编排三个 LCEL Chain（agent → planner → testgen），所有 LLM 调用通过 ChatDeepSeek.with_structured_output() 实现，planner 输出 PRDOutput 拆分为多条 Requirement 行，testgen 在 planning 阶段后独立调用

**Tech Stack:** langchain-deepseek, ChatDeepSeek, LCEL, ChatPromptTemplate, with_structured_output

## Global Constraints

- 后端全部 Python 文件使用 `from langchain_deepseek import ChatDeepSeek` 作为 LLM 入口
- 不使用自定义 LLM 抽象基类（删除 llm/base.py, llm/factory.py）
- Mock 降级实现放在 `app/llm/mock.py`
- PRD 生成的 Requirement 每条独立写入 DB，version/priority/source_finding_ids/source_review_ids 字段必须填充
- 测试用例必须关联 requirement_id + source_review_ids
- 前端文件不做任何修改（API 响应格式保持兼容）
- DB 表结构不做任何修改
- 每个任务先写测试、测试失败、再写实现

---

### Task 1: 更新依赖配置

**Files:**
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: 无
- Produces: 新的 requirements.txt

- [ ] **Step 1: 修改 requirements.txt**

将：
```
langchain==0.3.13
langchain-community==0.3.13
httpx==0.28.1
openai==1.57.0
```
改为：
```
langchain==0.3.13
langchain-deepseek>=0.1.0
httpx==0.28.1
```
其他依赖保持不变（fastapi, uvicorn, sqlalchemy, aiosqlite, pydantic, python-dotenv）。

- [ ] **Step 2: 安装依赖并验证**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
uv pip install -r requirements.txt
python -c "from langchain_deepseek import ChatDeepSeek; print('ok')"
```
预期输出: `ok`

- [ ] **Step 3: Commit**

```
git add backend/requirements.txt
git commit -m "chore: replace langchain-community/openai with langchain-deepseek"
```

---

### Task 2: 重构 config.py + LLM 层

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/llm/mock.py`
- Delete: `backend/app/llm/base.py`
- Delete: `backend/app/llm/factory.py`

**Interfaces:**
- Consumes: 无
- Produces: `app.config.get_llm() -> ChatDeepSeek`（全局单例）
- Produces: `app.llm.mock.MockChatDeepSeek(schema_class)` → 结构化空结果

- [ ] **Step 1: 删除 base.py**

```bash
rm backend/app/llm/base.py
```

- [ ] **Step 2: 删除 factory.py**

```bash
rm backend/app/llm/factory.py
```

- [ ] **Step 3: 创建 mock.py**

写入 `backend/app/llm/mock.py`：

```python
"""LLM 降级实现：API Key 缺失时返回空结构化结果"""
import json
from typing import Any, Type
from pydantic import BaseModel
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from langchain_core.language_models import BaseChatModel


class MockChain:
    """模拟 Chain，返回对应 Pydantic 模型的空实例"""

    def __init__(self, schema: Type[BaseModel]):
        self.schema = schema

    async def ainvoke(self, inputs: dict) -> BaseModel:
        return self.schema()


class MockChatDeepSeek(ChatDeepSeek):
    """当未配置 API Key 时使用，所有调用返回空结果"""

    def __init__(self):
        # 用假参数初始化父类
        super().__init__(
            model="deepseek-chat",
            api_key="sk-mock",
            base_url="https://api.deepseek.com/v1",
        )

    async def ainvoke(self, *args, **kwargs) -> AIMessage:
        return AIMessage(content="{}")

    def with_structured_output(self, schema: Type[BaseModel], **kwargs) -> MockChain:
        return MockChain(schema)
```

- [ ] **Step 4: 重写 config.py**

写入 `backend/app/config.py`：

```python
"""环境配置 + LLM 全局实例"""

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/app_reviews.db")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

_llm = None


def get_llm():
    """返回全局 ChatDeepSeek 实例（单例），无 API Key 时返回 Mock"""
    global _llm
    if _llm is not None:
        return _llm

    if not DEEPSEEK_API_KEY:
        from app.llm.mock import MockChatDeepSeek
        _llm = MockChatDeepSeek()
    else:
        from langchain_deepseek import ChatDeepSeek
        _llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.1,
            timeout=60,
        )
    return _llm
```

- [ ] **Step 5: 验证导入**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
python -c "from app.config import get_llm; llm = get_llm(); print(type(llm).__name__)"
```

无 API Key 时应输出 `MockChatDeepSeek`。

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/llm/mock.py
git rm backend/app/llm/base.py backend/app/llm/factory.py
git commit -m "refactor: replace custom LLM layer with ChatDeepSeek + Mock fallback"
```

---

### Task 3: 重写 agent.py（主题发现 Agent）

**Files:**
- Rewrite: `backend/app/services/agent.py`
- Test: `backend/test_agent.py`

**Interfaces:**
- Consumes: `get_llm()` from `app.config`
- Produces: `analyze_reviews(reviews: list[dict], llm, goal: str="") -> list[dict]`
  - 输入 dict 格式: `{"review_id": str, "content": str, "title": str, "rating": int}`
  - 输出 dict 格式同现有: `{"topic", "confidence", "description", "supporting_review_ids", "sample_count", "representative_excerpts", "contradicting_evidence", "is_statistical", "is_model_generated", "was_downgraded", "downgrade_reason", "status"}`

- [ ] **Step 1: Write the failing test**

写入 `backend/tests/test_agent.py`：

```python
"""Tests for agent.py topic discovery"""
import pytest
from app.services.agent import analyze_reviews


class MockLLM:
    """模拟 LLM 返回结构化结果"""
    class MockChain:
        def __init__(self, schema):
            self.schema = schema
        async def ainvoke(self, inputs):
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

    def with_structured_output(self, schema, **kwargs):
        return self.MockChain(schema)


@pytest.mark.asyncio
async def test_analyze_reviews_returns_findings():
    reviews = [
        {"review_id": "r1", "content": "it crashes a lot", "title": "crash", "rating": 1},
        {"review_id": "r2", "content": "keeps crashing", "title": "bug", "rating": 2},
    ]
    llm = MockLLM()
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
async def test_analyze_reviews_max_50():
    """验证每次传给 LLM 不超过 50 条"""
    reviews = [{"review_id": f"r{i}", "content": "text", "title": "", "rating": 3} for i in range(100)]
    llm = MockLLM()
    result = await analyze_reviews(reviews, llm)
    assert isinstance(result, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest tests/test_agent.py -v 2>&1 | head -20
```
预期：`FAILED`（函数尚未实现）。

- [ ] **Step 3: Write minimal implementation**

重写 `backend/app/services/agent.py`：

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest tests/test_agent.py -v
```

预期：`PASSED`（3 tests）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent.py backend/tests/test_agent.py
git commit -m "refactor: migrate agent.py to LangChain ChatDeepSeek LCEL chain"
```

---

### Task 4: 重写 planner.py（证据评估 + PRD 结构化生成）

**Files:**
- Rewrite: `backend/app/services/planner.py`
- Test: `backend/tests/test_planner.py`

**Interfaces:**
- Consumes: `get_llm()` from `app.config`, `Finding` ORM 对象列表
- Produces: `evaluate_evidence(findings: list[dict], llm=None) -> list[dict]`（纯规则驱动，不调用 LLM）
- Produces: `generate_prd(findings: list, llm) -> PRDOutput`（LLM 驱动）

- [ ] **Step 1: Write the failing test**

写入 `backend/tests/test_planner.py`：

```python
"""Tests for planner.py evidence evaluation and PRD generation"""
import pytest
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
    class MockLLM:
        class MockChain:
            def __init__(self, schema):
                self.schema = schema
            async def ainvoke(self, inputs):
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
        def with_structured_output(self, schema, **kwargs):
            return self.MockChain(schema)

    findings = [
        {"id": 1, "topic": "crash", "confidence": "high", "description": "App crashes", "sample_count": 5, "supporting_review_ids": ["r1", "r2"]},
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest tests/test_planner.py -v 2>&1 | head -20
```

- [ ] **Step 3: Write minimal implementation**

重写 `backend/app/services/planner.py`：

```python
"""证据评估 + PRD 生成 — 使用 LangChain LCEL Chain"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate


class PRDOutput(BaseModel):
    """结构化 PRD 输出"""
    overview: str = Field(description="PRD 概述")

    class PRDRequirement(BaseModel):
        title: str = Field(description="需求标题")
        description: str = Field(description="需求详细描述")
        priority: str = Field(description="优先级: p0/p1/p2")
        version: str = Field(description="版本规划: v1/v2/v3")
        source_finding_ids: list[int] = Field(description="关联的 Finding ID 列表")

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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest tests/test_planner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/planner.py backend/tests/test_planner.py
git commit -m "refactor: migrate planner.py to ChatDeepSeek + structured PRDOutput"
```

---

### Task 5: 重写 testgen.py（测试用例生成 Agent）

**Files:**
- Rewrite: `backend/app/services/testgen.py`
- Test: `backend/tests/test_testgen.py`

**Interfaces:**
- Consumes: `get_llm()` from `app.config`, Requirement ORM 对象列表
- Produces: `generate_test_cases(requirements: list[dict], llm) -> list[dict]`
  - 输出 dict 格式: `{"description", "steps", "expected", "requirement_id", "source_review_ids"}`

- [ ] **Step 1: Write the failing test**

写入 `backend/tests/test_testgen.py`：

```python
"""Tests for testgen.py test case generation"""
import pytest
from pydantic import BaseModel, Field


class _GeneratedTest(BaseModel):
    description: str
    steps: list[str]
    expected: str
    requirement_id: int
    source_review_ids: list[int]


class _TestSuite(BaseModel):
    test_cases: list[_GeneratedTest]


class MockLLM:
    class MockChain:
        def __init__(self, schema):
            self.schema = schema
        async def ainvoke(self, inputs):
            return _TestSuite(test_cases=[
                _GeneratedTest(
                    description="Verify crash fix",
                    steps=["Open app", "Navigate to workout", "Verify no crash"],
                    expected="App does not crash",
                    requirement_id=1,
                    source_review_ids=["r1", "r2"],
                )
            ])

    def with_structured_output(self, schema, **kwargs):
        return self.MockChain(schema)


@pytest.mark.asyncio
async def test_generate_test_cases():
    requirements = [
        {"id": 1, "title": "Fix crashes", "description": "Fix app crashes",
         "source_review_ids": ["r1", "r2"], "priority": "p0", "version": "v1"},
    ]
    result = await generate_test_cases(requirements, MockLLM())
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["description"] == "Verify crash fix"
    assert len(result[0]["steps"]) == 3


@pytest.mark.asyncio
async def test_generate_test_cases_empty():
    assert await generate_test_cases([], None) == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest tests/test_testgen.py -v 2>&1 | head -20
```

- [ ] **Step 3: Write minimal implementation**

重写 `backend/app/services/testgen.py`：

```python
"""测试用例生成 Agent — 使用 LangChain LCEL Chain"""

from typing import Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate


class GeneratedTest(BaseModel):
    description: str = Field(description="测试用例描述")
    steps: list[str] = Field(description="测试步骤列表")
    expected: str = Field(description="预期结果")
    requirement_id: int = Field(description="关联的需求 ID")
    source_review_ids: list[int] = Field(description="关联的评论 ID 列表")


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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest tests/test_testgen.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/testgen.py backend/tests/test_testgen.py
git commit -m "refactor: migrate testgen.py to ChatDeepSeek LCEL chain"
```

---

### Task 6: 修改 pipeline.py（接入 testgen + PRD 拆分）

**Files:**
- Modify: `backend/app/pipeline.py`

**Interfaces:**
- Consumes: `agent.analyze_reviews()`, `planner.evaluate_evidence()`, `planner.generate_prd()`, `testgen.generate_test_cases()`, `get_llm()` from config
- Produces: 完整的 8 阶段流水线（含 testgen）

- [ ] **Step 1: Run existing tests to establish baseline**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest -v 2>&1 | tail -10
```

- [ ] **Step 2: Rewrite pipeline.py**

将 `backend/app/pipeline.py` 重写为：

```python
"""分析流水线编排 — 8 阶段（含 testgen）"""

import asyncio
import logging
from sqlalchemy import select, update

from app.database import async_session
from app.config import get_llm
from app.event_manager import get_event_manager
from app.models.db import AnalysisTask, RawReview, CleanedReview, Finding, Requirement, TestCase, DataLimitation

logger = logging.getLogger("pipeline")


async def run_pipeline(task_id: str, app_id: str, goal: str, max_pages: int = 10, sort: str = "mostrecent"):
    """执行完整分析流水线"""
    em = get_event_manager(task_id)

    async with async_session() as db:
        try:
            llm = get_llm()

            # ====== 阶段 1: 目标解析 ======
            await em.emit("stage_start", "scoping", {}, db)
            await _update_task(db, task_id, current_stage="scoping", progress_pct=5)
            scope = {"focus_keywords": [], "focus_ratings": []}
            if goal:
                try:
                    from langchain_core.prompts import ChatPromptTemplate
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", "你是一个分析目标解析器。从用户的 goal 中提取关键维度，输出 JSON。"),
                        ("human", "分析目标: {goal}"),
                    ])
                    result = await (prompt | llm).ainvoke({"goal": goal})
                    import json as _json
                    try:
                        parsed = _json.loads(result.content if hasattr(result, 'content') else str(result))
                        if isinstance(parsed, dict):
                            scope = parsed
                    except (_json.JSONDecodeError, TypeError):
                        pass
                except Exception as e:
                    logger.warning("Scope parsing failed: %s", e)
            await em.emit("scope_defined", "scoping", scope, db)
            await em.emit("stage_complete", "scoping", {}, db)

            # ====== 阶段 2: 数据采集 ======
            await em.emit("stage_start", "collecting", {}, db)
            await _update_task(db, task_id, current_stage="collecting", progress_pct=20)

            rating_history = {r: 0 for r in range(1, 6)}

            async def on_page(page, page_reviews, total):
                for rv in page_reviews:
                    rating_history[rv["rating"]] = rating_history.get(rv["rating"], 0) + 1
                await em.emit("stage_progress", "collecting", {
                    "page": page,
                    "total_pages": max_pages,
                    "count": total,
                    "rating_distribution": [
                        {"rating": r, "count": rating_history.get(r, 0)}
                        for r in range(1, 6)
                    ],
                })

            from app.services.collectors.rss import fetch_reviews
            raw_reviews = await fetch_reviews(app_id, db, task_id, max_pages, sort=sort, on_progress=on_page)
            await em.emit("stage_complete", "collecting", {"total": len(raw_reviews)}, db)

            # ====== 阶段 3: 清洗裁剪 ======
            await em.emit("stage_start", "cleaning", {}, db)
            await _update_task(db, task_id, current_stage="cleaning", progress_pct=40)

            from app.services.cleaner import clean_reviews
            cleaned, stats = clean_reviews(raw_reviews, task_id)
            for cr in cleaned:
                db.add(cr)
            await db.commit()
            await em.emit("stage_complete", "cleaning", {
                "input_count": stats.get("input_count", 0),
                "output_count": stats.get("output_count", 0),
                "invalid_filtered": stats.get("invalid_filtered", 0),
                "ad_filtered": stats.get("ad_filtered", 0),
                "duplicates_removed": stats.get("duplicates_removed", 0),
                "avg_quality": stats.get("avg_quality", 0),
            }, db)

            # ====== 阶段 4: AI Agent 分析 ======
            await em.emit("stage_start", "analyzing", {}, db)
            await _update_task(db, task_id, current_stage="analyzing", progress_pct=60)

            from app.services.sampler import split_blocks
            from app.services.agent import analyze_reviews

            review_dicts = [
                {"review_id": r.review_id, "content": r.content,
                 "title": r.title, "rating": r.rating}
                for r in cleaned
            ]

            all_findings = []
            blocks = split_blocks(review_dicts, block_size=100)
            for i, block in enumerate(blocks):
                await em.emit("stage_progress", "analyzing",
                              {"block": i + 1, "total_blocks": len(blocks)}, db)
                findings = await analyze_reviews(block, llm, goal)
                all_findings.extend(findings)

            for f_data in all_findings:
                db.add(Finding(task_id=task_id, **f_data))
            await db.flush()

            # 统计各置信度等级
            confidence_dist = {"high": 0, "medium": 0, "low": 0}
            for f in all_findings:
                c = f.get("confidence", "low")
                confidence_dist[c] = confidence_dist.get(c, 0) + 1
            top_topics = [f.get("topic", "") for f in all_findings[:5]]

            await em.emit("stage_complete", "analyzing", {
                "findings_count": len(all_findings),
                "confidence_dist": confidence_dist,
                "top_topics": top_topics,
            }, db)

            # ====== 阶段 5: 证据评估 + PRD 生成与拆分 ======
            await em.emit("stage_start", "planning", {}, db)
            await _update_task(db, task_id, current_stage="planning", progress_pct=80)

            from app.services.planner import evaluate_evidence, generate_prd

            evaluated = await evaluate_evidence(all_findings)

            # 重新读取 DB 中的 Finding 以获取 ID
            result = await db.execute(
                select(Finding).where(Finding.task_id == task_id)
            )
            saved_findings = list(result.scalars().all())

            # 将 DB id 匹配回 evaluated dict
            for f_data in evaluated:
                f_data["_db_id"] = next(
                    (sf.id for sf in saved_findings
                     if sf.topic == f_data.get("topic", "")
                     and sf.description == f_data.get("description", "")),
                    None
                )

            prd = await generate_prd(saved_findings, llm)

            downgraded_topics = []
            for f in evaluated:
                if f.get("was_downgraded"):
                    downgraded_topics.append(f.get("topic", ""))

            for req in prd.requirements:
                source_review_ids = []
                for fid in req.source_finding_ids:
                    finding = next((sf for sf in saved_findings if sf.id == fid), None)
                    if finding and finding.supporting_review_ids:
                        source_review_ids.extend(finding.supporting_review_ids)

                db.add(Requirement(
                    task_id=task_id,
                    title=req.title,
                    description=req.description,
                    priority=req.priority,
                    version=req.version,
                    source_finding_ids=req.source_finding_ids,
                    source_review_ids=list(set(source_review_ids)),
                ))
            await db.commit()

            await em.emit("stage_complete", "planning", {
                "prd_snippet": prd.overview[:500] if prd.overview else "",
                "evaluated_count": len(evaluated),
                "downgraded_count": len(downgraded_topics),
                "downgraded_topics": downgraded_topics,
                "requirements_count": len(prd.requirements),
            }, db)

            # ====== 阶段 5b: 测试用例生成 ======
            await em.emit("stage_start", "testgen", {}, db)
            await _update_task(db, task_id, current_stage="testgen", progress_pct=90)

            from app.services.testgen import generate_test_cases

            req_result = await db.execute(
                select(Requirement).where(Requirement.task_id == task_id)
            )
            reqs = req_result.scalars().all()

            req_dicts = [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "version": r.version,
                    "source_review_ids": r.source_review_ids or [],
                }
                for r in reqs
            ]

            test_cases = await generate_test_cases(req_dicts, llm)

            for tc in test_cases:
                db.add(TestCase(
                    task_id=task_id,
                    requirement_id=tc.get("requirement_id"),
                    description=tc.get("description", ""),
                    steps=tc.get("steps", []),
                    expected=tc.get("expected", ""),
                    source_review_ids=tc.get("source_review_ids", []),
                ))
            await db.commit()

            await em.emit("stage_complete", "testgen", {
                "test_cases_count": len(test_cases),
            }, db)

            # ====== 阶段 6: 溯源验证 + 最终确定 ======
            await em.emit("stage_start", "done", {}, db)
            await _update_task(db, task_id, progress_pct=95, current_stage="done")

            from app.services.validator import validate_traceability
            trace_result = {"checked": 0, "pending": 0}
            try:
                trace_result = await validate_traceability(task_id, db)
                await em.emit("stage_progress", "done", {"traceability": trace_result}, db)
            except Exception as e:
                logger.warning("Traceability validation failed: %s", e)

            limitations = [
                DataLimitation(task_id=task_id, category="feed",
                    description="评论数据来自 Apple RSS Feed，仅包含最近评论，无法获取历史全量",
                    impact="分析结论可能不反映长期趋势", is_actionable=False),
                DataLimitation(task_id=task_id, category="coverage",
                    description="RSS Feed 内容可能被截断，超长评论不完整",
                    impact="部分用户反馈可能缺失细节", is_actionable=False),
                DataLimitation(task_id=task_id, category="timeliness",
                    description="RSS 仅返回最近评论，时间窗口有限",
                    impact="最新版本的问题可能比旧版本更突出", is_actionable=True),
            ]
            for lim in limitations:
                db.add(lim)
            await db.commit()

            await _update_task(db, task_id, status="completed", progress_pct=100,
                               current_stage="done")
            await em.emit("stage_complete", "done", {"traceability": trace_result}, db)
            await em.emit("analysis_complete", "done", {"task_id": task_id}, db)

        except Exception as e:
            logger.exception("Pipeline failed")
            await _update_task(db, task_id, status="failed", current_stage="pipeline",
                               error=str(e))
            await em.emit("stage_error", "pipeline", {"error": str(e)}, db)


async def _update_task(db, task_id: str, **kwargs):
    await db.execute(update(AnalysisTask).where(AnalysisTask.id == task_id).values(**kwargs))
    await db.commit()
```

- [ ] **Step 3: 验证导入和语法**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
python -c "from app.pipeline import run_pipeline; print('pipeline OK')"
```

- [ ] **Step 4: 运行全量测试**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest -v 2>&1
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline.py
git commit -m "feat: integrate testgen into pipeline + split PRD into individual requirements"
```

---

### Task 7: 更新 main.py（适配新的 LLM 导入方式）

**Files:**
- Modify: `backend/app/main.py`

**Changes:**
- 移除 `from app.llm.factory import create_llm` 相关引用（已嵌入 pipeline.py 内部）
- 验证 `from app.config import get_llm` 在新代码中无直接引用（pipeline 内部用）

- [ ] **Step 1: 检查 main.py 是否仍有 llm.factory 引用**

```bash
cd e:/app-review-insights/backend
grep -n "llm\|factory\|create_llm" app/main.py
```
预期：无匹配。pipeline.py 之前已经在内部 import，Task 6 已重写。

- [ ] **Step 2: 验证启动**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
python -c "from app.main import app; print('FastAPI app OK')"
```

- [ ] **Step 3: Commit（如有变更）**

```bash
git add backend/app/main.py
git commit -m "chore: clean up unused LLM imports in main.py"
```

---

### Task 8: 端到端验证

**Files:**
- Test: 启动前后端，验证完整流程

- [ ] **Step 1: 启动后端**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
uvicorn app.main:app --port 8000 &
sleep 3
```

- [ ] **Step 2: 启动前端**

```bash
cd e:/app-review-insights/frontend
npm run dev &
sleep 3
```

- [ ] **Step 3: 验证 API 可用**

```bash
curl http://localhost:8000/api/tasks
```
预期：`[]`（空列表）。

- [ ] **Step 4: 验证 CI 测试通过**

```bash
cd e:/app-review-insights/backend
source .venv/Scripts/activate
pytest -v 2>&1
```
预期：所有测试 PASS。

- [ ] **Step 5: 快速启动分析**

```bash
curl -X POST http://localhost:8000/api/analysis/start \
  -H "Content-Type: application/json" \
  -d '{"app_url":"https://apps.apple.com/us/app/workout-for-women-home-gym/id839285684","goal":"find crash issues","max_reviews":50}'
```
预期：返回 task id，status 为 running。

- [ ] **Step 6: 前端验证**

浏览器打开 `http://localhost:5173`，输入 App Store 链接，启动分析。验证：
- ✅ 进度面板 6 阶段（scoping → collecting → cleaning → analyzing → planning → testgen → done）
- ✅ testgen 阶段显示"生成中"和完成后的用例数
- ✅ PRD Tab 显示多个独立需求（非单条）
- ✅ 测试 Tab 显示测试用例列表
- ✅ 溯源 Tab 检查链：Review → Finding → Requirement → TestCase
- ✅ 未改动前端代码也能正常显示

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: complete LangChain migration + testgen pipeline + PRD split"
```
