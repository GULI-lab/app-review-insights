# App Review Insights

iOS App Store 评论智能分析平台。

## 系统架构

```
前端 (React 19 + Vite + shadcn/ui + ECharts)  ←SSE实时→  后端 (FastAPI + SQLite + DeepSeek LLM)
                                                                  │
                                                          Apple RSS Feed (美区)
```

## 技术栈

| 层 | 技术选型 |
|---|---------|
| 前端 | React 19 + Vite + TypeScript + shadcn/ui + ECharts |
| 后端 | Python FastAPI + SQLAlchemy + SQLite |
| AI 分析 | LangChain Agent + DeepSeek LLM（可切换 OpenAI / Ollama） |
| 数据采集 | Apple RSS Feed（美区） |
| 实时通信 | SSE + 事件持久化（支持断线重连） |

## 快速开始

### 前置要求

- Node.js 18+（前端）
- Python 3.12+（后端）
- uv（Python 包管理器）

### 1. 启动后端

```bash
cd backend

# 创建虚拟环境并安装依赖
uv venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # macOS/Linux
uv pip install -r requirements.txt

# 配置环境变量（可选，不配置 LLM 分析阶段会跳过）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 启动服务器
uvicorn app.main:app --port 8000
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 3. 访问

浏览器打开 `http://localhost:5173`

输入 App Store 链接（如 `https://apps.apple.com/us/app/workout-for-women-home-gym/id839285684`），点击"开始分析"。

## 功能模块

### 数据采集
- 来源：Apple RSS Feed API（美区 App Store）
- 方式：分页抓取，每页 50 条，最多 10 页 = 500 条
- 限流：每页间隔 ≥ 1.2 秒
- 局限性：仅获取最近评论，内容可能被截断（在报告中标注）

### 数据清洗（规则驱动）
- 重复检测：同 author + 同 rating + 日期差 ≤ 3d + Jaccard 相似度 > 0.9
- 无效过滤：< 5 字符 / 纯标点 / 纯 emoji / 纯数字 / 无意义词语
- 隐私脱敏：邮箱 → [EMAIL]、电话 → [PHONE]
- 质量评分：基于长度、有意义的词语、重复字符等

### AI 分析
- 框架：LangChain Agent + DeepSeek（可切换）
- 动态主题发现：非预定义分类，LLM 从评论中自动发现
- 证据评估：每个 finding 标注置信度（high/medium/low）
- 矛盾检测：记录相反观点的评论
- 溯源验证：Review → Finding → Requirement → TestCase 链

### 数据导入
- 支持 JSON/CSV 格式导入评论数据
- POST `/api/import` 接口 + `task_id` 参数

## 项目结构

```
app-review-insights/
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── components/          # UI 组件
│   │   │   ├── ui/              # shadcn/ui 组件
│   │   │   ├── AppInput.tsx     # 输入面板
│   │   │   ├── ProgressPanel.tsx# SSE 进度面板（含实时图表）
│   │   │   ├── StageCard.tsx    # 阶段卡片
│   │   │   ├── ReviewTable.tsx  # 评论表格 + ECharts 多维度图表
│   │   │   ├── FindingsView.tsx # AI 发现展示
│   │   │   ├── PrdView.tsx      # PRD 文档
│   │   │   └── TestCasesView.tsx# 测试用例
│   │   ├── hooks/useSSE.ts      # SSE 连接 Hook
│   │   ├── api/client.ts        # API 客户端
│   │   └── types/index.ts       # TypeScript 类型
│   └── ...
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 入口 + 路由
│   │   ├── config.py            # 环境配置
│   │   ├── database.py          # 数据库连接
│   │   ├── models/              # ORM + Pydantic
│   │   ├── services/            # 业务逻辑
│   │   │   ├── collectors/rss.py# RSS 采集
│   │   │   ├── cleaner.py       # 清洗去重
│   │   │   ├── sampler.py       # 采样/分块
│   │   │   ├── agent.py         # LangChain Agent
│   │   │   ├── planner.py       # 证据评估 + PRD
│   │   │   ├── testgen.py       # 测试用例
│   │   │   └── validator.py     # 溯源验证
│   │   ├── llm/                 # LLM 抽象层
│   │   ├── event_manager.py     # SSE 管理
│   │   └── pipeline.py          # 流水线编排
│   └── .env.example
├── demo/                        # 最小功能单元 demo
│   ├── rss_feed_demo.py         # RSS 采集
│   ├── cleaner_demo.py          # 清洗去重
│   ├── importer_demo.py         # 数据导入
│   └── sampler_demo.py          # 分层抽样
└── README.md
```

## 交付验证

| 功能 | 状态 | 说明 |
|------|------|------|
| App Store 链接输入 | ✅ | 支持任意有效美区链接 |
| RSS Feed 采集 | ✅ | 500 条真实评论 |
| 数据清洗去重 | ✅ | 规则驱动，确定性 |
| 采集进度可视化 | ✅ | SSE 实时推送 + ECharts 评分分布图 |
| 评论多维图表 | ✅ | 评分分布/时间趋势/版本分布/热力图 |
| 评论列表 | ✅ | 分页 + 星级筛选 + 关键词搜索 |
| Agent AI 分析 | ✅ | LangChain + DeepSeek，动态发现主题 |
| 证据评估 | ✅ | 置信度标注 + 矛盾检测 |
| PRD 生成 | ✅ | Markdown 格式，版本规划 |
| 测试用例生成 | ✅ | 关联需求和评论 |
| CSV/JSON 导入 | ✅ | POST /api/import |
| 断线重连 | ✅ | SSE since_id 回放 |
| 中文界面 | ✅ | 全部中文标签和注释 |

## 数据采集说明

- **数据源**：Apple RSS Feed API（`https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json`）
- **采集范围**：美区 App Store 评论
- **上限**：500 条（10 页 × 50 条/页）
- **官方接口**：Apple 提供的公共 RSS Feed，无需爬虫或逆向工程
- **局限性**：
  - 仅包含最近评论，无历史全量
  - 超长评论可能被截断
  - 超过 10 页后分页不稳定
  - 在局限性报告中自动标注

## 环境变量

参考 `backend/.env.example`：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DATABASE_URL=sqlite+aiosqlite:///data/app_reviews.db
```

不配置 API Key 时系统以 Mock 模式运行，LLM 分析阶段会跳过。
