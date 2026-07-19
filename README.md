# App Review Insights

iOS App Store 评论智能分析平台。输入任意美区 App Store 链接，系统自动完成评论采集→清洗→AI 分析→PRD 生成→测试用例设计的完整产品分析工作流。

---

## 查看历史任务

每次分析完成后，任务及其所有结果（评论数据、AI 发现、PRD、测试用例、溯源验证）均持久化存储在 SQLite 数据库中，不会丢失。

**重新查看已完成的任意任务：**

1. 启动后端 + 前端
2. 点击页面右上角「查看历史任务」
3. 从列表中选择任一任务
4. 页面自动加载该任务的完整结果：数据概览 → 评论 → AI 发现 → PRD → 测试用例 → 溯源验证 → 数据局限

所有历史任务均支持重新打开和结果查阅，无需重新分析。

## test_data 用法

项目附带 502 条真实美区 App Store 评论样例数据，位于 `test_data/test_data.json`，导入已采集的数据即可验证完整流水线。

### 导入方式

1. 启动后端 + 前端
2. 在页面底部"导入评论数据"区域
3. 选择 `test_data/test_data.json`，选"自动创建新任务"
4. 点击"开始导入"，系统自动运行采集→清洗→AI 分析→PRD→测试用例全流程

### 数据格式

```json
[
  {
    "review_id": "14312293284",
    "author": "Kuromi@123",
    "title": "Really good app",
    "content": "This app is the best...",
    "rating": 5,
    "version": "8.4.26",
    "date": "2026-07-16T18:03:06-07:00"
  }
]
```


## 目录

- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [功能模块](#功能模块)
- [AI 模型说明](#ai-模型说明)
- [规则驱动的确定性任务](#规则驱动的确定性任务)
- [数据采集说明](#数据采集说明)
- [API 路由](#api-路由)
- [项目结构](#项目结构)
- [数据库表](#数据库表)
- [交付验证](#交付验证)
- [环境变量](#环境变量)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        前端 (React 19 + Vite)                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────────┐  │
│  │  AppInput │  │ ProgressPanel│  │ ReviewTable│  │ FindingsView  │  │
│  │ 输入面板   │  │ 实时进度+图表 │  │ 仪表盘/表格 │  │ AI 发现展示    │  │
│  └──────────┘  └──────────────┘  └───────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────────┐  │
│  │  PrdView │  │ TestCasesView│  │ Traceability│ │ Limitations   │  │
│  │ PRD 文档  │  │ 测试用例      │  │ 溯源验证    │ │ 局限性报告     │  │
│  └──────────┘  └──────────────┘  └───────────┘  └───────────────┘  │
│                          ▲  SSE 实时流                              │
├──────────────────────────┼──────────────────────────────────────────┤
│                   后端 (FastAPI + SQLite)                            │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────────┐  │
│  │ Pipeline │→│  Cleaner    │→│  Agent    │→│  Planner      │  │
│  │ 流水线编排 │  │ 清洗去重    │  │ AI 分析    │  │ 证据评估+PRD  │  │
│  └──────────┘  └──────────────┘  └───────────┘  └───────────────┘  │
│                        ↕ SQLite + SSE 事件持久化                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Apple RSS Feed API (美区 App Store)               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术选型 |
|---|---------|
| 前端 | React 19 + Vite + TypeScript + shadcn/ui + ECharts |
| 后端 | Python FastAPI + SQLAlchemy + SQLite |
| AI 分析 | LangChain + DeepSeek LLM（支持 Mock 模式无 API Key 运行） |
| 数据采集 | Apple 官方 RSS Feed API 分页抓取 |
| 实时通信 | SSE + 事件持久化（断线重连 + 历史回放） |
| 包管理 | uv（后端）/ npm（前端） |

## 快速开始

### 前置要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.12 | 后端运行环境 |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.6 | Python 包管理器（推荐） |
| Node.js | ≥ 18 | 前端运行环境 |
| npm | ≥ 9 | 前端包管理 |

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
# 不配置 API Key 时以 Mock 模式运行，LLM 分析阶段跳过
```

### 2. 启动后端

```bash
cd backend

# 方式一：uv（推荐）
uv sync
# 进入虚拟环境
.venv/Scripts/activate      # Windows
# source .venv/bin/activate        # macOS/Linux

uv run uvicorn app.main:app --port 8000
```



### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 访问

浏览器打开 `http://localhost:5173`

输入 App Store 链接，如：

```
https://apps.apple.com/us/app/workout-for-women-home-gym/id839285684
```

点击"开始分析"，系统自动完成：目标解析 → 数据采集 → 清洗裁剪 → AI 分析 → PRD 生成 → 测试用例 → 溯源验证。

## 功能模块

### 1. 目标解析

用户可输入分析目标（如"关注订阅转化和低评分评论"），LLM 自动提取关键维度，指导后续分析聚焦。

### 2. 数据采集

- **来源**：Apple 官方 RSS Feed API
- **分页**：每页 50 条，最多 500 条（10 页）
- **限流保护**：连续空页检测 + 指数退避重试
- **区域**：通过 storefront 参数支持美区/中国区等

### 3. 数据清洗

两阶段清洗：

| 阶段 | 规则 | 处理内容 |
|------|------|---------|
| 规则层 | 确定性规则 | 无效过滤（<5字符/纯标点/纯emoji/纯数字），广告检测（URL/促销词），重复检测（Jaccard 相似度+时间窗口） |
| AI 层 | LLM 语义判断 | 垃圾评论、推广软文、模板好评、机翻内容 |

附加处理：隐私脱敏（邮箱→`[EMAIL]`、电话→`[PHONE]`）、质量评分（0-1，基于长度/内容/重复等）

### 4. AI 主题发现

LangChain `with_structured_output` 构建结构化分析链，从评论中动态发现用户关注话题。每条评论携带评分、版本号、日期信息。

每个 finding 包含：
- `topic` — 话题名称
- `confidence` — 置信度（high/medium/low）
- `description` — 用户问题/需求描述
- `supporting_review_ids` — 支撑评论 ID 列表
- `sample_count` — 支撑评论数
- `representative_excerpts` — 代表性引文
- `contradicting_evidence` — 矛盾证据
- `is_statistical` / `is_model_generated` — 来源区分

### 5. 证据评估 + PRD

- 规则驱动的证据充分性评估（≥5条=充分，≥2条=有限，<2条=降级标记 `pending_review`）
- LLM 生成结构化 PRD，含版本规划（V1 Quick Wins / V2 核心功能 / V3 未来规划）
- 每个需求关联源 Finding ID 和源 Review ID

### 6. 测试用例生成

- 基于 PRD 需求生成，每个用例关联 requirement_id 和 source_review_ids
- 包含可操作的测试步骤和预期结果

### 7. 溯源性验证

自动检查 Review→Finding→Requirement→TestCase 链完整性：

```
用户评论 → 分析发现 → PRD 需求 → 测试用例
         ↑ 至少 2 条评论支撑
                      ↑ 至少 1 个 Finding 支撑
                                    ↑ 需求可测试
```

断链自动标注为 `pending_review`，在 UI 中展示降级原因。

### 8. 数据局限性报告

| 局限性类别 | 描述 | 可改善 |
|-----------|------|--------|
| feed | Apple RSS Feed 仅最近评论，无历史全量 | 否 |
| coverage | RSS 内容可能被截断 | 否 |
| timeliness | 最新版本问题更突出 | 是 |

### 9. UI 可视化

| 页面 | 内容 |
|------|------|
| 进度面板 | 7 阶段卡片 + 进度条 + 实时评分分布图 + 采集趋势图 |
| 数据概览 | 4 维度指标卡 + 评分分布/时间趋势/版本分布/热力图 |
| 评论列表 | 分页表格 + 星级筛选 + 关键词搜索 |
| 分析发现 | 置信度标签 + 支撑评论 + 原声引文 + 矛盾证据 |
| PRD | 按版本分组的 Markdown 需求文档 |
| 测试用例 | 步骤列表 + 预期结果 + 关联评论 |
| 溯源验证 | 检查概览 + 待审核项 |
| 数据局限 | 局限性分类展示 |
| 数据导入 | JSON/CSV 上传 + 字段自动映射 |

## AI 模型说明

| 项目 | 说明 |
|------|------|
| 模型 | DeepSeek Chat (`deepseek-chat`) |
| 框架 | LangChain LCEL + `with_structured_output` |
| 配置 | temperature=0.1, timeout=60s |
| 降级 | 无 API Key 时自动切换 Mock 模式（跳过 LLM 阶段） |
| 失败策略 | 单块失败不影响整体，跳过继续处理 |

### 模型驱动的语义任务

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1 | 分析目标解析 | pipeline.py 内联 | 从自然语言 goal 提取分析维度 |
| 2 | 评论清洗过滤 | [ai_cleaner.py](backend/app/services/ai_cleaner.py) | 垃圾/推广/模板/机翻检测 |
| 3 | 动态主题发现 | [agent.py](backend/app/services/agent.py) | 从评论自动发现话题（核心模型驱动任务） |
| 4 | PRD 生成 | [planner.py](backend/app/services/planner.py) | 基于 findings 生成结构化 PRD |
| 5 | 测试用例生成 | [testgen.py](backend/app/services/testgen.py) | 基于 PRD 需求生成测试用例 |

## 规则驱动的确定性任务

| # | 任务 | 文件 | 规则说明 |
|---|------|------|---------|
| 1 | RSS 分页采集 | [rss.py](backend/app/services/collectors/rss.py) | 限流检测 + 指数退避 + 连续空页终止 |
| 2 | 无效评论过滤 | [cleaner.py](backend/app/services/cleaner.py) | <5字符/纯标点/纯emoji/纯数字/无意义词语 |
| 3 | 广告检测 | [cleaner.py](backend/app/services/cleaner.py) | URL/促销关键词匹配（≥2个模式） |
| 4 | 重复检测 | [cleaner.py](backend/app/services/cleaner.py) | 同author+同rating+日期差≤3d+Jaccard>0.9 |
| 5 | 隐私脱敏 | [cleaner.py](backend/app/services/cleaner.py) | 邮箱/电话正则替换 |
| 6 | 质量评分 | [cleaner.py](backend/app/services/cleaner.py) | 基于长度/内容/重复的 0-1 评分 |
| 7 | 证据评估 | [planner.py](backend/app/services/planner.py) | 基于支撑评论数的三级标签 |
| 8 | 溯源验证 | [validator.py](backend/app/services/validator.py) | Review→Finding→Requirement→TestCase 链检查 |

## 数据采集说明

### 数据源

```
https://itunes.apple.com/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json?cc={storefront}
```

Apple 官方公共 RSS Feed 接口，无需爬虫或逆向工程。

### 采集参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| page | 1-10 | 分页，每页 50 条 |
| app_id | 由 URL 自动提取 | 纯数字 App ID |
| sortby | mostrecent | mostrecent / mosthelpful |
| cc | us | 国家代码，控制 storefront |

### 局限性

- 仅包含最近评论，无法获取历史全量数据
- 超长评论可能被截断
- 超过 10 页后分页不稳定
- 系统在运行时会自动标注这些局限性到报告中

## API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analysis/start` | 创建并启动分析任务 |
| GET | `/api/analysis/{id}` | 查询任务状态 |
| GET | `/api/analysis/{id}/stream` | SSE 事件流（支持 `since_id` 断线重连） |
| GET | `/api/analysis/{id}/reviews` | 评论列表（分页 + 星级筛选） |
| GET | `/api/analysis/{id}/reviews/stats` | 评论统计（评分分布/时间趋势/版本分布） |
| GET | `/api/analysis/{id}/findings` | AI 分析发现 |
| GET | `/api/analysis/{id}/requirements` | PRD 需求 |
| GET | `/api/analysis/{id}/test-cases` | 测试用例 |
| GET | `/api/analysis/{id}/traceability` | 溯源性验证结果 |
| GET | `/api/analysis/{id}/limitations` | 数据局限性报告 |
| POST | `/api/import` | 导入 JSON/CSV 评论数据 |
| GET | `/api/tasks` | 列出所有分析任务 |

## 项目结构

```
app-review-insights/
├── frontend/                          # React 19 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui 基础组件
│   │   │   ├── AppInput.tsx           # App Store 链接 + 参数输入
│   │   │   ├── ProgressPanel.tsx      # SSE 实时进度面板（含 ECharts 图表）
│   │   │   ├── StageCard.tsx          # 阶段状态卡片
│   │   │   ├── StageResult.tsx        # 阶段产出详情展示
│   │   │   ├── ReviewTable.tsx        # 仪表盘 + 评论表格（4 张 ECharts 图表）
│   │   │   ├── FindingsView.tsx       # AI 发现展示（置信度/引文/矛盾）
│   │   │   ├── PrdView.tsx            # PRD 文档（react-markdown 渲染）
│   │   │   ├── TestCasesView.tsx      # 测试用例
│   │   │   ├── TraceabilityView.tsx   # 溯源验证结果
│   │   │   ├── LimitationsView.tsx    # 数据局限性报告
│   │   │   └── ImportView.tsx         # JSON/CSV 导入
│   │   ├── hooks/useSSE.ts            # SSE 连接（断线重连）
│   │   ├── api/client.ts              # API 请求封装
│   │   └── types/index.ts             # TypeScript 类型定义
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                           # FastAPI 后端
│   ├── pyproject.toml                 # uv 依赖配置
│   ├── requirements.txt               # pip 依赖配置
│   ├── .env.example                   # 环境变量模板
│   ├── app/
│   │   ├── main.py                    # 入口 + API 路由
│   │   ├── config.py                  # 环境配置 + LLM 全局单例
│   │   ├── database.py                # SQLAlchemy 异步引擎
│   │   ├── event_manager.py           # SSE 事件管理 + 持久化
│   │   ├── pipeline.py                # 8 阶段流水线编排
│   │   ├── models/
│   │   │   ├── db.py                  # ORM 模型（8 张表）
│   │   │   └── schemas.py             # Pydantic schema
│   │   ├── routers/
│   │   │   └── import_.py             # JSON/CSV 导入 API
│   │   ├── services/
│   │   │   ├── collectors/
│   │   │   │   └── rss.py             # RSS Feed 分页采集
│   │   │   ├── cleaner.py             # 规则驱动清洗去重
│   │   │   ├── ai_cleaner.py          # AI 垃圾/模板检测
│   │   │   ├── sampler.py             # 采样/分块/高危扫描
│   │   │   ├── agent.py               # LangChain 主题发现 Agent
│   │   │   ├── scoper.py              # 目标解析（兼容保留）
│   │   │   ├── planner.py             # 证据评估 + PRD 生成
│   │   │   ├── testgen.py             # 测试用例生成
│   │   │   └── validator.py           # 溯源性验证
│   │   └── llm/
│   │       └── mock.py                # Mock LLM（无 API Key 降级）
│   └── data/                          # SQLite 运行时数据库
│       └── .gitkeep
│
├── demo/                              # 最小功能单元演示
│   ├── rss_feed_demo.py               # RSS 采集
│   ├── cleaner_demo.py                # 清洗去重
│   ├── importer_demo.py               # 数据导入
│   ├── sampler_demo.py                # 分层抽样
│   └── data/
│       └── raw_reviews_*.json         # 采集缓存（被 .gitignore 排除）
│
├── test_data/                         # 样例数据目录
│   └── test_data.json                 # 502 条真实美区评论（可直接导入运行）
│
├── 要求.md                            # 项目需求文档
├── CLAUDE.md                          # 开发规则
├── .gitignore
└── README.md
```

## 数据库表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `analysis_tasks` | 分析任务 | app_id, goal, status, progress_pct, current_stage |
| `analysis_events` | SSE 事件持久化 | event, stage, data (JSON), created_at |
| `raw_reviews` | 原始评论 | review_id, content, rating, author, version, date, country |
| `cleaned_reviews` | 清洗后评论 | 同 raw + duplicate_of, quality_score, relevance_score |
| `findings` | AI 分析发现 | topic, confidence, supporting_review_ids (JSON), sample_count |
| `data_limitations` | 数据集局限性 | category, description, impact, is_actionable |
| `requirements` | PRD 需求 | title, description, priority, version, source_finding_ids |
| `test_cases` | 测试用例 | requirement_id, description, steps (JSON), expected |

## 交付验证

| 功能 | 状态 | 说明 |
|------|------|------|
| App Store 链接输入 | ✅ | 自动解析 app_id 和 storefront |
| 分析目标输入 | ✅ | 可选，LLM 提取关键维度 |
| RSS Feed 分页采集 | ✅ | 最多 500 条，限流检测+指数退避 |
| 数据清洗去重 | ✅ | 规则+AI 混合，隐私脱敏 |
| 采集进度可视化 | ✅ | SSE 实时推送 + 评分分布/趋势图 |
| 评论多维可视化 | ✅ | 4 ECharts 图表（评分/时间/版本/热力） |
| 评论列表 | ✅ | 分页 + 星级筛选 + 关键词搜索 |
| AI 动态主题发现 | ✅ | LangChain + DeepSeek，非预定义分类 |
| 证据评估 | ✅ | 置信度标注 + 矛盾检测 + 支撑不足降级 |
| 数据局限性报告 | ✅ | 自动标注数据源限制和影响 |
| PRD 生成 | ✅ | 结构化 PRD，版本规划（V1/V2/V3） |
| 测试用例生成 | ✅ | 关联需求和源评论，可操作步骤 |
| 溯源性验证 | ✅ | Review→Finding→Requirement→TestCase 链 |
| JSON/CSV 导入 | ✅ | POST /api/import，自动启动分析 |
| 断线重连 | ✅ | SSE since_id 回放 |
| Mock 模式 | ✅ | 无 API Key 时跳过 LLM 阶段 |
| 样本缓存数据 | ✅ | test_data/ 包含 502 条真实评论 |
| 最小功能单元 Demo | ✅ | 采集/清洗/导入/采样独立可运行 |
| 中文界面 | ✅ | 全部中文标签和注释 |

## 环境变量

参考 `backend/.env.example`：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DATABASE_URL=sqlite+aiosqlite:///data/app_reviews.db
```

不配置 API Key 时系统以 Mock 模式运行，LLM 分析阶段会跳过。

### 升级依赖

```bash
# 后端（uv）
cd backend
uv sync --upgrade-package fastapi

# 前端
cd frontend
npm update
```
