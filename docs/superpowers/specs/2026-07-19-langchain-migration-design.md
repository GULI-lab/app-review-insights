# LangChain 迁移 + 流水线完善设计文档

## 概述

对 App Review Insights 后端进行三项改造：
1. 自定义 LLM 层迁移到 LangChain `ChatDeepSeek` 集成
2. 测试用例生成接入流水线
3. PRD 生成拆分为独立需求行

## 架构变更

### 当前架构（自定义 LLM 层）

```
pipeline.py
  ├── agent.py:     llm.chat_structured()  → TopicFinding[]
  ├── planner.py:   llm.chat()             → PRD Markdown (单条 Requirement)
  └── testgen.py:   ❌ 未接入 pipeline
         │
      llm/factory.py
         ├── DeepSeekClient (AsyncOpenAI → api.deepseek.com)
         └── MockClient (降级)
```

### 目标架构（LangChain LCEL Chain）

```
pipeline.py
  ├── agent.py:     prompt | llm.with_structured_output(AnalysisResult)
  ├── planner.py:   prompt | llm.with_structured_output(PRDOutput) → 多条 Requirement
  └── testgen.py:   prompt | llm.with_structured_output(TestSuite)  ← 新接入
         │
      ChatDeepSeek (langchain-deepseek)
         └── MockChatDeepSeek (降级)
```

## 实现细节

### 1. 依赖变更

修改 `backend/requirements.txt`：

| 包 | 状态 | 说明 |
|---|------|------|
| `langchain-deepseek` | 新增 | 提供 `ChatDeepSeek` |
| `langchain` | 保留 | LCEL 基础设施 |
| `langchain-community` | 移除 | 不再需要 |
| `openai` | 移除 | 不再直接使用（由 langchain-deepseek 传递依赖提供） |
| `httpx` | 保留 | langchain-deepseek 需要 |
| 其他包 | 不变 | fastapi, sqlalchemy, aiosqlite, pydantic, python-dotenv |

### 2. config.py 变更

当前 `config.py` 读取 `.env` 定义常量。改为初始化全局 `ChatDeepSeek` 实例：

```python
from langchain_deepseek import ChatDeepSeek

_llm: ChatDeepSeek | None = None

def get_llm() -> ChatDeepSeek:
    global _llm
    if _llm is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            # 返回 Mock 版本
            from app.llm.mock import MockChatDeepSeek
            _llm = MockChatDeepSeek()
        else:
            _llm = ChatDeepSeek(
                model="deepseek-chat",
                api_key=api_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                temperature=0.1,
                timeout=60,
            )
    return _llm
```

### 3. LLM 层精简

| 文件 | 操作 |
|------|------|
| `app/llm/base.py` | 删除（不再需要抽象基类） |
| `app/llm/factory.py` | 删除（替代为 config.get_llm()） |
| `app/llm/mock.py` | 新增（Mock 降级实现） |
| `app/config.py` | 新增 get_llm() 工厂函数 |

Mock 降级实现：

```python
class MockChatDeepSeek(ChatDeepSeek):
    """API Key 缺失时的降级实现，返回空结果"""
    async def ainvoke(self, *args, **kwargs):
        return AIMessage(content="{}")

    def with_structured_output(self, schema, **kwargs):
        return MockChain(schema)
```

### 4. agent.py —— 主题发现

**输入**: `goal`, `reviews_text`（50 条/块）
**输出**: `AnalysisResult`（含 `TopicFinding[]`）
**Schema 定义**（移入服务文件）：

```python
class TopicFinding(BaseModel):
    topic: str
    confidence: str  # high/medium/low
    description: str
    supporting_review_ids: list[str]
    sample_count: int
    representative_excerpts: list[str]
    contradicting_evidence: list[str]

class AnalysisResult(BaseModel):
    findings: list[TopicFinding]
```

**Chain**:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个 App Store 评论分析师。从评论中动态发现用户关心的话题。\n"
               "对每个话题：[详细分析要求...]\n"
               "{format_instructions}"),
    ("human", "分析目标: {goal}\n\n评论数据:\n{reviews_text}"),
])
chain = prompt | llm.with_structured_output(AnalysisResult)
```

**分块逻辑保持**：`split_blocks()` 分块，逐块调用 chain。

### 5. planner.py —— PRD 生成 + 拆分

**输入**: `evaluated_findings` 列表
**输出**: `PRDOutput`（含 overview + 多条 PRDRequirement）

```python
class PRDRequirement(BaseModel):
    title: str
    description: str
    priority: str      # p0/p1/p2
    version: str       # v1/v2/v3
    source_finding_ids: list[int]

class PRDOutput(BaseModel):
    overview: str
    requirements: list[PRDRequirement]
```

**清理旧函数**：
- `evaluate_evidence()`：保持规则驱动逻辑（基于 sample_count 分配三级标签），不涉及 LLM，保留不动
- `generate_prd()`：改为返回 `PRDOutput` 而非 Markdown 字符串

**pipeline.py 中调用方改为**：

```python
# flush 后重新读取 Finding 以获取 DB id
await db.flush()
result = await db.execute(select(Finding).where(Finding.task_id == task_id))
saved_findings = list(result.scalars().all())
# 将 DB id 注入 findings dict
finding_id_map = {f.id: f for f in saved_findings}
for f_data in all_findings:
    # 通过 topic + description 匹配 DB 记录
    f_data["_db_id"] = next(
        (sf.id for sf in saved_findings if sf.topic == f_data["topic"] and sf.description == f_data["description"]),
        None
    )

prd = await generate_prd(saved_findings, llm)  # 传入 ORM 对象
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
```

### 6. testgen.py —— 测试用例生成

**输入**: requirements 列表
**输出**: `TestSuite`（含 `GeneratedTest[]`）

```python
class GeneratedTest(BaseModel):
    description: str
    steps: list[str]
    expected: str
    requirement_id: int
    source_review_ids: list[int]

class TestSuite(BaseModel):
    test_cases: list[GeneratedTest]
```

**Chain**:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个 QA 工程师。基于 PRD 需求编写测试用例。\n"
               "每个用例必须关联到对应的 requirement_id 和支撑该需求的评论 ID。"),
    ("human", "需求列表:\n{requirements_text}"),
])
chain = prompt | llm.with_structured_output(TestSuite)
```

### 7. pipeline.py 变更

新增阶段标记 `testgen`，在 planning 之后、done 之前：

```
Stage 5  (planning):  evaluate_evidence → generate_prd → 保存 Requirement[多行]
Stage 5b (testgen):   读取 Requirement[] → generate_test_cases() → 保存 TestCase[]
Stage 6  (done):       validate_traceability → limitations → completed
```

SSE 事件新增：
- `stage_start` / `testgen`
- `stage_progress` / `testgen`（生成进度）
- `stage_complete` / `testgen`（统计：生成用例数）

### 8. pipeline.py 的 test_cases 表检查

当前 `pipeline.py` 的 done 阶段调用 `validate_traceability()`，该函数只检查 Finding 的支撑评论数是否 ≥2。测试用例接入后，溯源验证还应当检查 Requirement 是否关联了 TestCase。

**vs 当前 validator.py 不变**，因为 validator 只验证 Finding→Review 这条线。TestCase→Requirement→Finding 的线在生成时就已确定。

### 9. 前端适配

前端无需大改，现有 `tests` Tab 已经能接收并展示 TestCase 列表：

| 字段 | 前端已支持 | 说明 |
|------|-----------|------|
| `description` | ✅ | 用例描述 |
| `steps` | ✅ | 步骤列表渲染 |
| `expected` | ✅ | 预期结果 |
| `source_review_ids` | ✅ | 关联评论 ID |
| `verified` | ✅ | 已验证徽章 |

`prd` Tab 的 `PrdView.tsx` 已渲染 `version` 和 `priority` 徽章，拆分后这些字段会被正确填充。

## 未变更部分

- `cleaner.py`：规则驱动，不动
- `sampler.py`：规则驱动，不动
- `validator.py`：逻辑保持不变
- `collectors/rss.py`：不变
- `event_manager.py`：不变
- 全部前端代码：不需要修改（API 响应格式保持不变）
- Database ORM 模型：表结构不变

## 风险与降级

| 风险 | 应对 |
|------|------|
| `langchain-deepseek` 包兼容性问题 | 备选方案用 `ChatOpenAI(base_url=deepseek)` 替代 |
| DeepSeek 结构化输出不稳定 | `with_structured_output()` 内部有重试；降级为 `invoke()` + 手动 JSON 解析 |
| Mock 模式下测试用例生成跳过 | Mock 返回空列表，pipeline 继续执行 |
| PRD 拆分后前端展示变化 | PRD Tab 显示 `description`（Markdown），格式不变 |

## 文件变更总览

| 文件 | 操作类型 |
|------|---------|
| `backend/requirements.txt` | 修改 |
| `backend/app/config.py` | 修改 |
| `backend/app/llm/__init__.py` | 删除（可选） |
| `backend/app/llm/base.py` | 删除 |
| `backend/app/llm/factory.py` | 删除 |
| `backend/app/llm/mock.py` | 新增 |
| `backend/app/pipeline.py` | 修改 |
| `backend/app/services/agent.py` | 重写 |
| `backend/app/services/planner.py` | 重写 |
| `backend/app/services/testgen.py` | 重写 |
| 前端文件 | 无变更 |
