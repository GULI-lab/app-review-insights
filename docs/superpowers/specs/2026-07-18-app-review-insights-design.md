# App Review Insights — 设计文档

## 概述

iOS App Store 评论分析平台：用户输入 App Store 链接 + 分析目标 → 系统自动收集评论、清洗去重、AI Agent 驱动分类分析、证据评估、版本规划/PRD、测试用例生成 → 全流程 SSE 实时进度 UI 展示。

## 技术栈

| 层 | 技术选型 |
|---|---------|
| 前端 | React 19 + Vite + TypeScript |
| 后端 | Python FastAPI |
| 数据库 | SQLite (SQLAlchemy ORM) |
| LLM | 抽象层设计 (支持 DeepSeek / OpenAI / Ollama 等) |
| Agent 框架 | LangChain (ChatOpenAI 兼容封装) |
| 实时通信 | SSE + 事件持久化 |
| 数据采集 | Apple RSS Feed (默认) + 可选爬虫 + CSV/JSON 导入 |


## 要求
AI分析必须使用agent(langchain)
评论网站：https://apps.apple.com/cn/app/workout-for-women-lose-weight/id839285684
https://apps.apple.com/cn/app/workout-for-women-lose-weight/id839285684?see-all=reviews&platform=iphone

## 系统架构

```
┌─────────────────────┐       SSE (实时进度 + 修订事件)    ┌──────────────────────────────────┐
│   React + Vite      │ ◄─────────────────────────────── │    FastAPI Backend               │
│   (Port 5173)        │       HTTP REST (CRUD)           │    (Port 8000)                   │
│                      │ ───────────────────────────────► │                                  │
│                      │                                  │   /api/analysis/start           │
│                      │                                  │   /api/analysis/{id}            │
│                      │                                  │   /api/analysis/{id}/stream     │
│                      │                                  │     (重连时回放已持久化事件)      │
│                      │                                  │   /api/analysis/{id}/conflicts  │
│                      │                                  │     (人工确认/驳回断链)          │
│                      │                                  │   /api/import                   │
│                      │                                  │                                  │
│                      │                                  │   Analysis Pipeline:            │
│                      │                                  │    1. 链接验证 + 目标解析        │
│                      │                                  │    2. 目标驱动的数据采集          │
│                      │                                  │    3. 清洗去重 + 范围裁剪        │
│                      │                                  │    4. 数据统计 + 局限性报告      │
│                      │                                  │    5. AI Agent 分析             │
│                      │                                  │    6. 证据评估 + 结论修订        │
│                      │                                  │    7. 版本规划                  │
│                      │                                  │    8. PRD 生成                  │
│                      │                                  │    9. 测试用例生成              │
│                      │                                  │    10. 溯源性验证 → 标记待审核  │
└─────────────────────┘                                  └──────────┬───────────────────────┘
                                                                     │
                                                              ┌──────▼───────────────────────┐
                                                              │   SQLite                     │
                                                              │   + analysis_events (持久化)  │
                                                              │   + conflicts (待审核标记)     │
                                                              │   + sample_outputs/           │
                                                              │   + data/raw/ (缓存)          │
                                                              └──────────────────────────────┘
```

## 项目结构

```
app-review-insights/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AppInput.tsx            # 链接输入 + 分析目标 + 爬虫选项
│   │   │   ├── ProgressPanel.tsx       # SSE 实时进度（含修订展示）
│   │   │   ├── StageCard.tsx           # 单阶段卡片（状态/错误/修订标记）
│   │   │   ├── ReviewTable.tsx         # 评论数据表格
│   │   │   ├── FindingsView.tsx        # 分析发现（含置信度/局限性）
│   │   │   ├── PrdView.tsx             # PRD 文档
│   │   │   ├── ConflictPanel.tsx       # 人工确认/驳回面板 (NEW)
│   │   │   └── TraceabilityView.tsx    # 溯源链可视化（含断链标记）
│   │   ├── hooks/useSSE.ts
│   │   ├── api/client.ts
│   │   └── types/index.ts
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI 入口 + SSE 路由
│   │   ├── config.py                   # 环境配置
│   │   ├── database.py                 # 数据库连接 + session
│   │   ├── models/
│   │   │   ├── db.py                   # SQLAlchemy ORM
│   │   │   └── schemas.py              # Pydantic
│   │   ├── routers/
│   │   │   ├── analysis.py             # 分析任务 API
│   │   │   ├── conflicts.py            # 冲突管理 API (NEW)
│   │   │   └── import_.py              # 数据导入 API
│   │   ├── services/
│   │   │   ├── scoper.py               # 目标解析 + 范围确定
│   │   │   ├── collectors/
│   │   │   │   ├── base.py             # 数据源抽象接口 (NEW)
│   │   │   │   ├── rss.py              # RSS Feed 采集
│   │   │   │   └── scraper.py          # 可选爬虫采集 (NEW)
│   │   │   ├── cleaner.py              # 清洗去重（规则驱动）
│   │   │   ├── sampler.py              # LLM 上下文采样/分块
│   │   │   ├── agent.py                # LangChain Agent 分析
│   │   │   ├── planner.py              # 证据评估 + 版本规划 + PRD
│   │   │   ├── testgen.py              # 测试用例生成
│   │   │   └── validator.py            # 溯源性验证 → 标记待审核 (NEW)
│   │   ├── llm/
│   │   │   ├── base.py                 # LLM 抽象基类 (NEW)
│   │   │   └── factory.py              # LLM 工厂: 从配置创建实例 (NEW)
│   │   ├── event_manager.py            # SSE 事件管理 + 持久化 (NEW)
│   │   └── pipeline.py                 # 流水线编排 (NEW)
│   ├── data/
│   │   └── raw/                        # 原始数据缓存
│   ├── requirements.txt
│   └── .env.example
├── scripts/
│   ├── fetch_sample_reviews.py         # 抓取示例 App 的真实评论，自动生成 sample_data/sample_reviews.json
│   └── generate_sample_data.py         # 基于真评论运行精简流水线，产出 sample_outputs/
├── sample_data/                        # 脚本运行时自动生成，不手动维护
│   └── sample_reviews.json             # (由 fetch_sample_reviews.py 生成)
├── sample_outputs/                     # 预置的完整分析结果（基于真实评论运行流水线产出）
│   ├── README.md                       # 说明：这些结果是预计算的真实产出
│   └── app_id839285684/
│       ├── task_meta.json              # 分析任务元数据（goal, data_source, scope）
│       ├── cleaned_reviews.json        # 清洗后评论
│       ├── data_limitations.json       # 数据集局限性
│       ├── findings.json               # 发现列表（含置信度/引文ID/矛盾证据）
│       ├── prd.md                      # PRD 文档（需求可追溯到评论）
│       ├── test_cases.json             # 测试用例（可追溯到需求和评论）
│       ├── traceability_report.json    # 溯源验证报告
│       └── revision_log.json           # 修订日志（如需人工确认则含冲突列表）
└── README.md
```

## 改进 1：数据源插件接口 + 可选爬虫

### 数据源抽象层 (collectors/base.py)

```python
class DataSource(ABC):
    """所有数据采集器的统一接口"""
    @abstractmethod
    async def fetch_reviews(self, app_id: str, max_count: int = 500) -> list[RawReview]:
        pass
    
    @abstractmethod
    def get_limitations(self) -> list[Limitation]:
        """返回该数据源的已知局限性"""
        pass
```

### 内置实现

| 数据源 | 默认 | 上限 | 局限性 |
|--------|------|------|--------|
| RSS Feed | ✅ 默认选中 | 500 条 | 仅最近评论，内容可能截断 |
| 爬虫 (Scraper) | ❌ 用户勾选启用 | 1000 条 | 需自行承担合规责任 |
| CSV/JSON 导入 | ✅ 始终可用 | 无限制 | 依赖用户提供数据 |

### 前端交互 (NEW)

```
┌─ Data Source ────────────────────────────────────┐
│  ○ RSS Feed (快速, 最多 500 条)                    │
│  ○ RSS + 爬虫 (采集更多历史评论, 最多 1000 条)     │
│     ⚠ 爬虫模式需要遵守 Apple 服务条款, 请确认知情  │
│  [📁 Import from File] 支持 JSON / CSV            │
└──────────────────────────────────────────────────┘
```

- 默认仅使用 RSS Feed（零风险）
- 用户可自愿勾选"启用爬虫"扩大数据量
- 爬虫使用 `httpx` + 页面解析，遵守 robots.txt，限制速率

## 改进 2：LLM 采样策略增强

### 异常关键词预筛选 (NEW)

在分层抽样之前，对所有被丢弃的评论执行高危词扫描：

```
被丢弃的评论 (300 条)
    │
    ▼
[高危关键词扫描]  ─── crash, bug, refund, broken, error, can't, 崩溃, 闪退, 付费问题...
    │
    ├── 匹配 → 强制保留到待分析集 (提升权重至 99)
    └── 不匹配 → 继续丢弃
```

规则驱动（确定性），无需 LLM，性能高效。

### 分块合并策略 (NEW)

当评论超出单次窗口时，拆分为 100 条/块分别分析，然后统一合并：

```
Block A (1-100):  [Finding: UI too complex, Conf: high]
Block B (101-200): [Finding: UI is clean, Conf: medium]
                     [Finding: Subscription expensive, Conf: high]
    │
    ▼
[LLM 合并仲裁] ─── 输入: 所有 block 的 findings + 矛盾列表
    │
    ├── 去重: 相同 topic 合并
    ├── 冲突仲裁: "UI too complex" vs "UI is clean"
    │   ├── 检查支持评论数 → 多数派胜出
    │   └── 若数量接近 → 标记为"用户意见分歧"
    └── 输出: 仲裁后的 unification_findings
```

## 改进 3：LLM 抽象层 (llm/)

### base.py — 抽象基类

```python
class LLMClient(ABC):
    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> str:
        pass
    
    @abstractmethod
    async def chat_structured(self, messages: list, response_model: Type[BaseModel]) -> BaseModel:
        """支持结构化输出（function calling / JSON mode）"""
        pass
```

### factory.py — 工厂模式

```python
def create_llm() -> LLMClient:
    provider = config.LLM_PROVIDER  # "deepseek" | "openai" | "ollama"
    if provider == "deepseek":
        return DeepSeekClient(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)
    elif provider == "openai":
        return OpenAIClient(api_key=config.OPENAI_API_KEY)
    elif provider == "ollama":
        return OllamaClient(base_url=config.OLLAMA_BASE_URL, model=config.OLLAMA_MODEL)
    ...
```

### .env.example (NEW)

```env
# LLM Provider: deepseek | openai | ollama
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 或者 OpenAI (兼容)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-xxx

# 或者本地 Ollama
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3

# 数据库
DATABASE_URL=sqlite:///data/app_reviews.db
```

## 改进 4：事件持久化 + SSE 断线重连

### analysis_events 表 (NEW)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| event | str | 事件类型 |
| stage | str | 阶段 |
| data | JSON | 事件负载 |
| created_at | datetime | |

**策略：**
- 所有 `stage_start` / `stage_complete` / `revision` / `limitation_reported` / `stage_error` 事件在推送到 SSE 的同时写入 DB
- `stage_progress` (高频增量) 不持久化，避免写入爆炸

### SSE 断线重连流程 (NEW)

```
用户刷新页面
    │
    ▼
前端 GET /api/analysis/{id}/stream?since_id={last_event_id}
    │
    ├── 从 DB 读取 since_id 之后的所有历史事件 → 批量回放
    │   (前端按原始顺序重新渲染, 恢复进度面板状态)
    │
    └── 回放结束后 → 切换为实时流
        (后续事件正常推送)
```

## 改进 5：溯源验证 → 标记待审核 + 人工确认

### 断链处理策略 (更新)

| 检查 | 旧行为 | 新行为 |
|------|--------|--------|
| Finding → Review < 2 | 自动降级 | 标记为 `pending_review`，保留原置信度 |
| Requirement ← Finding 缺失 | 自动移除 | 标记为 `pending_review`，放入冲突列表 |
| TestCase ← Requirement 缺失 | 自动移除 | 标记为 `pending_review` |
| 需求无用户问题支撑 | 自动降级 | 标记为 `pending_review` |

### conflicts 表 (NEW)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| entity_type | str | finding / requirement / test_case |
| entity_id | int | |
| check_type | str | traceability 检查类型 |
| issue | str | 问题描述 |
| suggested_action | str | 系统建议操作 |
| user_action | enum | pending / confirmed / dismissed / revised |
| created_at | datetime | |

### 前端 ConflictPanel (NEW)

```
┌─── Conflict Resolution ─────────────────────────┐
│                                                  │
│  ⚠ Finding #5 "订阅价格过高" 支撑不足           │
│  系统建议: 降级为假设 (仅 1 条评论支撑)         │
│  [确认降级] [保留并忽略] [查看源评论]            │
│                                                  │
│  ⚠ Requirement #3 "增加月度订阅选项" 无 Finding  │
│  系统建议: 从 PRD 移除                          │
│  [确认移除] [保留为假设性需求] [查看相关数据]    │
│                                                  │
│  剩余: 2 个待处理                               │
└──────────────────────────────────────────────────┘
```

**默认行为：** 分析完成后不自动删除，等用户确认后才执行操作。

## 改进 6：基于真实评论的样本数据

### 预采集的真实评论 (sample_data/)

```bash
python scripts/fetch_sample_reviews.py --app-id 839285684 --output sample_data/sample_reviews.json
```

- 使用 RSS Feed 抓取示例 App 的真实评论（约 200-300 条）
- 结果作为静态文件提交到仓库，不依赖于运行时网络
- 所有评论标注 source: "sample_data"，与运行时数据可区分

### 样本产出生成脚本 (scripts/generate_sample_data.py)

```python
"""
1. 加载 sample_data/sample_reviews.json 中的真实评论
2. 运行流水线子集：清洗 → 采样 → Agent 分析 → 证据评估 → PRD → 测试用例 → 溯源验证
   (跳过数据采集阶段，直接使用预采集评论)
3. 完整结果输出到 sample_outputs/app_id{app_id}/
4. 如需 LLM 但无 API Key，使用预缓存的 Agent 输出
5. 所有文件标注 generation_mode: "sample_data"
"""
```

**优势：**
- PRD 和测试用例基于**真实用户评论**，内容有逻辑关联
- 面试官阅读 findings.json 和 prd.md 时可以理解「评论 → 发现 → 需求 → 测试」的完整推理链
- 不依赖运行时网络和 API Key 即可审查产出质量

### 更新策略

Schema 变更时：
1. `python scripts/generate_sample_data.py --reload`
2. 脚本重新加载 sample_data/sample_reviews.json，基于新 Schema 重新运行精简流水线
3. 自动覆盖 sample_outputs/ 目录
4. 输出日志标注因 Schema 变更而更新的字段

## 数据库模型

### analysis_tasks
| 字段 | 类型 | 说明 |
|------|------|------|
| id | str (UUID) | 主键 |
| app_url | str | App Store URL |
| app_id | str | 解析出的 app_id |
| goal | str | 用户提供的分析目标 |
| data_source | str | rss / scraper / import (NEW) |
| parsed_scope | JSON | 从 goal 解析出的结构化范围 |
| status | enum | pending/running/completed/failed |
| progress_pct | int | 0-100 |
| current_stage | str | 当前阶段名 |
| error | str | 错误信息 |
| limitations | JSON | 数据集局限性说明 |
| created_at | datetime | |

### analysis_events (NEW)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| event | str | 事件类型 |
| stage | str | 阶段 |
| data | JSON | 事件负载 |
| created_at | datetime | |

### raw_reviews / cleaned_reviews
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | 关联分析任务 |
| review_id | str | App Store 评论 ID |
| source | str | rss / scraper / import |
| title | str | |
| content | str | |
| rating | int | 1-5 |
| author | str | |
| version | str | 用户评论的 App 版本 |
| date | datetime | |
| country | str | |
| duplicate_of | int | 去重时标记 |
| quality_score | float | 0-1 |
| relevance_score | float | 0-1，与 goal 的相关性 |

### findings
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| topic | str | 主题/问题名 |
| confidence | enum | high/medium/low |
| description | str | |
| supporting_review_ids | JSON | 源评论 ID 列表 |
| sample_count | int | 支持样本数 |
| representative_excerpts | JSON | 引文片段 |
| contradicting_evidence | JSON | 矛盾证据 |
| is_statistical | bool | 是否为统计结论 |
| is_model_generated | bool | 是否为 AI 生成 |
| was_downgraded | bool | 是否被修订降级过 |
| downgrade_reason | str | 降级原因 |
| status | enum | approved / pending_review / dismissed (NEW) |

### conflicts (NEW)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| entity_type | str | finding / requirement / test_case |
| entity_id | int | |
| check_type | str | |
| issue | str | |
| suggested_action | str | |
| user_action | enum | pending / confirmed / dismissed / revised |
| created_at | datetime | |

### data_limitations
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| category | str | coverage/timeliness/language/sampling/feed |
| description | str | |
| impact | str | |
| is_actionable | bool | 是否可通过补充数据解决 |

### requirements (PRD)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | str (FK) | |
| title | str | |
| description | str | |
| priority | enum | p0/p1/p2 |
| version | str | v1/v2/v3 |
| source_finding_ids | JSON | |
| source_review_ids | JSON | |
| status | enum | approved / pending_review / dismissed (NEW) |

### test_cases
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| requirement_id | int (FK) | |
| task_id | str (FK) | |
| description | str | |
| steps | JSON | |
| expected | str | |
| source_review_ids | JSON | |
| verified | bool | |

## 核心模块详述

### 1. 目标解析 + 范围确定 (scoper.py)

流水线第一步，在数据采集之前执行。将用户的自然语言 goal 解析为结构化筛选条件。

**流程：**
1. 用 LLM 解析 goal，提取关键维度：
   - 评分关注范围（如 goal = "低评分评论" → `focus_ratings: [1, 2]`）
   - 主题关键词（如 goal = "订阅转化" → `focus_keywords: ["订阅", "付费", "price", "premium"]`）
   - 版本范围（如 goal = "v2.5 最近的反馈" → `focus_versions: ["2.5"]`）
   - 分析侧重点（如 goal = "功能建议" → `analysis_focus: "feature_requests"`）
2. 输出 `parsed_scope` 写入 analysis_tasks 表
3. 若无明确 goal 或无法解析，使用默认全量范围

**SSE 事件：**
```json
{"event": "stage_progress", "stage": "scoping", "detail": "解析分析目标: 关注订阅转化与低评分评论", "pct": 5}
{"event": "scope_defined", "stage": "scoping", "scope": {"focus_ratings": [1,2], "focus_keywords": ["订阅","付费","价格","premium","in-app purchase"], "sampling_priority": "low_rating"}}
```

**设计决策**：使用 LLM（非规则）解析 goal，因为 goal 是自然语言输入，用户的表达方式多样。

### 2. 数据采集 (collectors/)

#### 2a. RSS Feed (默认, collector_rss.py)

- 基础 URL: `https://itunes.apple.com/rss/customerreviews/page={page}/id={app_id}/sortby={sort}/json`
- 支持多种排序维度：mostrecent, mosthelpful
- 分页抓取：每页 50 条，最多 10 页 = 500 条
- 速率限制：每页间隔 ≥ 1 秒

**RSS Feed 的已知局限：**

| 局限 | 说明 | 应对 |
|------|------|------|
| 评论内容截断 | Apple RSS 返回的 content.label 可能在长评论中被截断 | 在局限性报告中标记截断比例 |
| 仅最新评论 | RSS 只返回最近的评论，无法获取历史全量 | 在局限性报告中注明时间窗口 |
| 分页深度限制 | 超过 10 页后结果不稳定 | 硬限制 500 条上限 |
| 部分字段缺失 | 某些评分/版本字段可能缺失 | 缺失字段标记为 null，统计时排除 |
| 请求频率限制 | 频繁请求可能被限流 | 指数退避重试，最大 3 次 |

#### 2b. 可选爬虫 (collector_scraper.py, 用户勾选启用)

- 使用 `httpx` + `selectolax` 解析 App Store 页面
- 用户必须主动勾选"我已了解风险"才能启用
- 默认上限 1000 条，速率限制 ≥ 2 秒/页
- 失败时不阻断流程 → 降级回 RSS 结果

#### 2c. CSV/JSON 导入 (import API)

- 始终可用，不受网络限制
- 支持标准格式（字段映射在 README 中说明）
- 导入数据自动复用清洗/分析/验证全流程

### 3. 数据清洗 + 目标驱动的范围裁剪 (cleaner.py)

**阶段 A：通用清洗（规则驱动）**

| 规则 | 方法 | 类型 |
|------|------|------|
| 重复检测 | 相同 author + same rating + 日期差 ≤ 3d + Levenshtein 相似度 > 0.9 | 确定性 |
| 无效过滤 | 纯标点 / 纯表情 / 广告内容模式匹配 | 确定性 |
| 字段规范化 | 评分归一化 1-5, 日期→ISO 8601 | 确定性 |
| 隐私脱敏 | 邮箱/电话正则替换 | 确定性 |

**阶段 B：目标驱动的范围裁剪**

根据 `parsed_scope` 做以下操作：
- **评分过滤**：若 goal 指定低评分，保留 1-2 星评论，3 星及以上打标为 `out_of_scope`
- **关键词加权**：对每条评论计算 `relevance_score`（与 focus_keywords 的匹配程度）
- **版本过滤**：若 goal 指定版本，仅保留该版本的评论
- **采样优先级**：在保留目标相关评论的同时，按比例保留部分"不相关"评论作为对比基线

**阶段 C：局限性评估**

自动生成数据集局限性报告：
- 采集范围与 goal 的匹配度评估
- RSS 截断比例
- 时间覆盖窗口
- 评分分布偏差
- 非英文评论比例

输出到 `data_limitations` 表。

### 4. LLM 上下文管理策略 (sampler.py)

**完整流程：**

```
N 条原始评论 (最多 1000)
    │
    ▼
[规则预过滤] ─── 按 rating/关键词/版本 裁剪
    │
    ▼
[高危关键词扫描] ─── crash/bug/refund/崩溃/闪退/付费
    │   ├── 匹配 → 强制保留 (权重=99)
    │   └── 不匹配 → 进入分层抽样池
    │
    ▼
[分层抽样]
    ├── 高相关评论 (relevance > 0.7) → 保留 80%
    ├── 中相关评论 (relevance 0.3-0.7) → 保留 15%
    ├── 基线评论 (relevance < 0.3) → 保留 5%
    │
    ▼
最终量: max(50, min(200, target_count))
    │
    ├── ≤ 200 条 → 直接送 Agent
    │
    └── > 200 条 → 分块分析
        │
        ├── 拆分为 100 条/块
        ├── 每块独立 Agent 分析
        └── LLM 合并仲裁:
            ├── 去重相同 topic
            ├── 冲突仲裁: 多数派评论数胜出
            ├── 数量接近 → "用户意见分歧"标签
            └── 输出 unification_findings
```

### 5. Agent 驱动分析 (agent.py)

LangChain Agent + LLM 抽象层（不直接依赖 DeepSeek）。

**Tools:**
- `topic_discovery(reviews: list) → list[Topic]`
- `evidence_gathering(topic: str, review_ids: list) → Evidence`
- `contradiction_check(topic: str, reviews: list) → list[Conflict]`
- `story_builder(findings: list) → Narrative`

**Reflection 机制：**
每次输出前 Agent 执行自检：
> "对每个 finding：是否有 ≥ 2 条评论支撑？如不足标记为假设。是否有矛盾评论？如实记录。数据集局限性是否影响该结论的置信度？如是，在备注中说明。"

**降级策略：**
若 LLM function calling 不支持 → 降级为 prompt + JSON mode

### 6. 证据评估 + 版本规划 + PRD (planner.py)

**证据评估：**
- 聚合 Agent 输出，三级标签：✅ 充分 / ⚠️ 有限 / ❌ 不足
- 统计事实标注 `is_statistical: true`
- 按 frequency + severity 排序

**版本规划：**
- V1 (Quick Wins): 高置信度 + 低实施成本
- V2 (Core): 中等置信度 + 核心体验改进
- V3 (Future): 低置信度 + 探索性需求

**PRD：** Markdown 格式

### 7. 溯源性验证 → 标记待审核 (validator.py)

**验证链：**
```
Review ──→ Finding ──→ Requirement ──→ TestCase
```

**断链处理策略（修改版）：**
不再自动删除/降级，改为标记 `pending_review` + 写入 `conflicts` 表。

| 检查 | 操作 | 
|------|------|
| Finding → Review < 2 | 标记 `pending_review`，建议降级 |
| Requirement ← Finding 缺失 | 标记 `pending_review`，建议移除 |
| TestCase ← Requirement 缺失 | 标记 `pending_review` |
| 需求无用户问题支撑 | 标记 `pending_review`，建议降优先级 |

前端 ConflictPanel 展示所有待处理项，用户可选择：确认 / 保留 / 驳回。

### 8. SSE 进度流 + 事件持久化

前端连接 `GET /api/analysis/{id}/stream?since_id=0`：

- 若 `since_id` > 0 → 从 DB 回放历史事件，再切换实时流
- 若 `since_id` = 0 → 从当前开始，仅实时

**持久化的事件类型：** `stage_start` / `stage_complete` / `scope_defined` / `limitation_reported` / `revision` / `stage_error` / `analysis_complete`

**不持久化：** `stage_progress`（高频增量）

### 9. 错误处理

| 场景 | 策略 |
|------|------|
| 网络临时故障 | 自动重试 (3 次, 指数退避) |
| RSS Feed 不可用 | 引导用户使用 CSV/JSON 导入 或 勾选爬虫 |
| 爬虫失败 | 降级到 RSS，不阻断流程 |
| API Key 无效 | 明确提示配置问题 |
| 数据不足 (< 5 条清洗后) | 全部结论低置信度，建议补充数据 |
| LLM function calling 失败 | 降级纯 prompt + JSON mode |
| 任意阶段失败 | SSE 通知 + 保留中间结果，可重试特定阶段 |

## 用户界面设计

```
┌───────────────────────────────────────────────────────┐
│  App Review Insights                                  │
├───────────────────────────────────────────────────────┤
│  Input Section                                        │
│  ┌─ App Store URL ────────────────────────────────┐   │
│  │  https://apps.apple.com/us/app/.../id839285684  │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─ Analysis Goal ─────────────────────────────────┐   │
│  │  关注订阅转化和低评分评论                         │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─ Data Source ───────────────┬──────────────────┐   │
│  │  ○ RSS Feed (默认, ≤500)    │ [📁 Import File] │   │
│  │  ○ RSS + 爬虫 (≤1000)      │                  │   │
│  └─────────────────────────────┴──────────────────┘   │
│  [▶ Start Analysis]                                   │
├─┬─────────────────────────────────────────────────────┤
│ │  Progress Panel                                     │
│ │  [可展开的阶段列表 + 实时修订事件]                    │
│ │  ✅ 目标解析 (3s)                                   │
│ │  ⏳ 数据采集 → 已获取 150/500 条                     │
│ │  ☐ 清洗/裁剪/局限性报告                              │
│ │  ...                                                │
│ │  ⚠ 修订: finding_5 置信度待审核                     │
│ ├─────────────────────────────────────────────────────┤
│ │  Results + Conflict Resolution                      │
│ │  Tabs: [评论] [发现] [PRD] [测试] [溯源] [局限] ✋冲突│
│ │                                                     │
│ │  ✋冲突 Tab (如有待处理):                            │
│ │  ┌─────────────────────────────────────────────┐    │
│ │  │ ⚠ Finding #5 支撑不足, 建议降级              │    │
│ │  │ [确认降级] [保留] [驳回]                     │    │
│ │  └─────────────────────────────────────────────┘    │
│ └─────────────────────────────────────────────────────┘
```

## 验收标准

1. ✅ 用户输入链接 + goal 后自动完成流水线
2. ✅ 支持 RSS、爬虫、CSV/JSON 三种数据源（爬虫需用户确认）
3. ✅ Goal 驱动数据采集范围
4. ✅ 实时 SSE 进度 + 断线重连回放
5. ✅ Agent 动态发现主题（非预定义分类）
6. ✅ 高危关键词预筛防止遗漏关键 Bug
7. ✅ 分块分析 + LLM 冲突仲裁
8. ✅ LLM 抽象层，一键切换 DeepSeek / OpenAI / Ollama
9. ✅ 溯源验证标记为待审核，用户可人工确认/驳回
10. ✅ 全程报告数据局限性
11. ✅ 支持 JSON/CSV 导入
12. ✅ `sample_data/sample_reviews.json` 包含预抓取的真实评论，`sample_outputs/` 基于真实评论运行流水线产出，可离线审查推理链质量
13. ✅ 前后端分离架构
