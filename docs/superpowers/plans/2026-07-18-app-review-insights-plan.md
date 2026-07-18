# App Review Insights 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 Apple RSS Feed 构建 App Store 评论分析平台全栈应用，前端中文界面+ECharts 可视化

**架构:** 前后端分离。后端 FastAPI + SQLite + LangChain Agent + DeepSeek LLM；前端 React 19 + shadcn/ui + ECharts；SSE 实时进度通信

**Tech Stack:** React 19, Vite, TypeScript, shadcn/ui, ECharts, Python FastAPI, SQLAlchemy, SQLite, LangChain, DeepSeek

## Global Constraints

- 后端使用 uv 创建虚拟环境
- 评论数据全部来自美区 App Store (itunes.apple.com/us/rss)
- 清洗/去重使用确定性规则（复用 demo/cleaner_demo.py 逻辑）
- 至少一个核心语义任务必须 AI 模型驱动（agent.py 使用 LangChain Agent）
- 无 app-specific 硬编码
- 所有代码注释使用中文
- 内容编码统一 UTF-8
- LLM Provider 默认 DeepSeek，通过 .env 配置

---

## 阶段一：后端核心（RSS采集 → 清洗 → 数据库）

### Task 1: 后端项目初始化 + 依赖配置

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`

- [ ] **Step 1: 创建 requirements.txt**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
aiosqlite==0.20.0
pydantic==2.10.3
langchain==0.3.13
langchain-community==0.3.13
python-dotenv==1.0.1
httpx==0.28.1
openai==1.57.0
```

- [ ] **Step 2: 创建 .env.example**

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com

DATABASE_URL=sqlite+aiosqlite:///data/app_reviews.db
```

- [ ] **Step 3: 创建 config.py**

```python
"""环境配置"""
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/app_reviews.db")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
```

- [ ] **Step 4: 初始化 uv 虚拟环境**

```bash
cd backend && uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
```

验证: `python -c "import fastapi; print(fastapi.__version__)"` 输出版本号

- [ ] **Step 5: 确认**

```bash
git add backend/
git commit -m "feat: init backend project structure"
```

---

### Task 2: 数据库 ORM 模型

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/db.py`
- Create: `backend/data/`（目录）

- [ ] **Step 1: 创建 database.py**

```python
"""数据库连接配置"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        from app.models.db import Base
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 2: 创建 models/db.py —— 所有 ORM 表定义**

表清单：analysis_tasks, analysis_events, raw_reviews, cleaned_reviews, findings, data_limitations, requirements, test_cases

```python
"""SQLAlchemy ORM 模型"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON, Enum, ForeignKey
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)

def _uuid():
    return str(uuid.uuid4())


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    id = Column(String, primary_key=True, default=_uuid)
    app_url = Column(String, nullable=False)
    app_id = Column(String, nullable=False)
    goal = Column(Text, default="")
    data_source = Column(String, default="rss")
    parsed_scope = Column(JSON, nullable=True)
    status = Column(String, default="pending")
    progress_pct = Column(Integer, default=0)
    current_stage = Column(String, default="")
    error = Column(Text, nullable=True)
    limitations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class AnalysisEvent(Base):
    __tablename__ = "analysis_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    event = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class RawReview(Base):
    __tablename__ = "raw_reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    review_id = Column(String, nullable=False)
    source = Column(String, default="rss")
    title = Column(Text, default="")
    content = Column(Text, default="")
    rating = Column(Integer, nullable=False)
    author = Column(String, default="")
    version = Column(String, nullable=True)
    date = Column(String, nullable=True)
    country = Column(String, nullable=True)
    fetch_page = Column(Integer, default=0)


class CleanedReview(Base):
    __tablename__ = "cleaned_reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    review_id = Column(String, nullable=False)
    source = Column(String, default="rss")
    title = Column(Text, default="")
    content = Column(Text, default="")
    rating = Column(Integer, nullable=False)
    author = Column(String, default="")
    version = Column(String, nullable=True)
    date = Column(String, nullable=True)
    country = Column(String, nullable=True)
    duplicate_of = Column(Integer, nullable=True)
    quality_score = Column(Float, default=0.5)
    relevance_score = Column(Float, default=0.0)


class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    topic = Column(String, nullable=False)
    confidence = Column(String, default="medium")
    description = Column(Text, default="")
    supporting_review_ids = Column(JSON, default=list)
    sample_count = Column(Integer, default=0)
    representative_excerpts = Column(JSON, default=list)
    contradicting_evidence = Column(JSON, default=list)
    is_statistical = Column(Boolean, default=False)
    is_model_generated = Column(Boolean, default=True)
    was_downgraded = Column(Boolean, default=False)
    downgrade_reason = Column(Text, nullable=True)
    status = Column(String, default="approved")


class DataLimitation(Base):
    __tablename__ = "data_limitations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, default="")
    impact = Column(Text, default="")
    is_actionable = Column(Boolean, default=False)


class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    priority = Column(String, default="p2")
    version = Column(String, default="v1")
    source_finding_ids = Column(JSON, default=list)
    source_review_ids = Column(JSON, default=list)
    status = Column(String, default="approved")


class TestCase(Base):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=True)
    description = Column(Text, default="")
    steps = Column(JSON, default=list)
    expected = Column(Text, default="")
    source_review_ids = Column(JSON, default=list)
    verified = Column(Boolean, default=False)
```

- [ ] **Step 3: 创建 Pydantic schemas**

Create `backend/app/models/schemas.py` — 所有 ORM 模型对应的 Pydantic 响应/请求 schema

```python
"""Pydantic 数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskCreate(BaseModel):
    app_url: str
    goal: str = ""

class TaskResponse(BaseModel):
    id: str
    app_url: str
    app_id: str
    goal: str
    status: str
    progress_pct: int
    current_stage: str
    error: Optional[str] = None
    created_at: datetime

class EventResponse(BaseModel):
    id: int
    task_id: str
    event: str
    stage: str
    data: Optional[dict] = None
    created_at: datetime

class ReviewResponse(BaseModel):
    id: int
    review_id: str
    source: str
    title: Optional[str] = ""
    content: str
    rating: int
    author: str
    version: Optional[str] = None
    date: Optional[str] = None
    quality_score: Optional[float] = None

class FindingResponse(BaseModel):
    id: int
    topic: str
    confidence: str
    description: str
    supporting_review_ids: list
    sample_count: int
    representative_excerpts: list
    contradicting_evidence: list
    is_statistical: bool
    is_model_generated: bool
    status: str

class RequirementResponse(BaseModel):
    id: int
    title: str
    description: str
    priority: str
    version: str
    source_finding_ids: list
    source_review_ids: list
    status: str

class TestCaseResponse(BaseModel):
    id: int
    requirement_id: Optional[int]
    description: str
    steps: list
    expected: str
    source_review_ids: list
    verified: bool
```

- [ ] **Step 4: 测试数据库初始化**

```bash
cd backend && python -c "
import asyncio
from app.database import init_db
asyncio.run(init_db())
print('DB initialized')
"
```

验证: `data/app_reviews.db` 文件创建成功

- [ ] **Step 5: 确认**

```bash
git add backend/ && git commit -m "feat: add database models and ORM"
```

---

### Task 3: RSS Feed 采集服务（复用 demo 逻辑）

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/collectors/__init__.py`
- Create: `backend/app/services/collectors/rss.py`
- Create: `backend/app/services/cleaner.py`

- [ ] **Step 1: 创建 rss.py**

复用 `demo/rss_feed_demo.py` 的 fetch_page / extract_reviews 逻辑，改造为异步服务：

```python
"""RSS Feed 评论采集服务"""
import json, logging, re, ssl, time
import urllib.error, urllib.request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import RawReview

logger = logging.getLogger("rss_collector")

PERMISSIVE_SSL_CTX = ssl.create_default_context()
PERMISSIVE_SSL_CTX.check_hostname = False
PERMISSIVE_SSL_CTX.verify_mode = ssl.CERT_NONE

RSS_BASE = "https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app_id}/sortby={sort}/json"

async def fetch_reviews(app_id: str, db: AsyncSession, task_id: str, max_pages: int = 10, on_progress=None):
    """分页抓取 RSS Feed 并写入 DB，每页完成后回调 on_progress"""
    # 实现同 demo/rss_feed_demo.py 的 fetch_page + extract_reviews
    # 不同点：写入 SQLite 而非 JSON 文件
    ...

async def _fetch_page(url: str, timeout=15):
    """抓取单页 RSS（同步 urllib 包装为异步）"""
    ...
```

详细实现直接复制 demo 的 fetch_page + extract_reviews 函数（同步），用 `asyncio.to_thread` 包装

- [ ] **Step 2: 创建 cleaner.py**

复用 `demo/cleaner_demo.py` 的清洗逻辑，改造为函数式：

```python
"""评论清洗去重服务（规则驱动）"""
from typing import List, Tuple
from app.models.db import RawReview, CleanedReview

def clean_reviews(raw_reviews: List[RawReview]) -> Tuple[List[CleanedReview], dict]:
    """确定性清洗: 去重->无效过滤->字段规范化->隐私脱敏->质量评分
    复用 demo/cleaner_demo.py 中的:
      - jaccard_similarity(), find_duplicates()
      - is_invalid_review(), is_advertisement()
      - sanitize_pii(), compute_quality_score()
    """
    ...

def _jaccard_similarity(t1, t2): ...
def _find_duplicates(reviews, time_threshold_days=3, similarity_threshold=0.9): ...
def _is_invalid(review): ...
def _is_ad(review): ...
def _sanitize_pii(text): ...
def _compute_quality(review): ...
```

- [ ] **Step 3: 验证**

```python
# 测试采集+清洗串联
import asyncio
from app.services.collectors.rss import fetch_reviews
from app.services.cleaner import clean_reviews
from app.database import async_session, init_db
asyncio.run(init_db())

async def test():
    async with async_session() as db:
        reviews = await fetch_reviews("839285684", db, "test-task-1", max_pages=1)
        print(f"Fetched: {len(reviews)}")
        # 验证 DB 中有数据
        from sqlalchemy import select
        from app.models.db import RawReview
        result = await db.execute(select(RawReview))
        rows = result.scalars().all()
        print(f"DB rows: {len(rows)}")

asyncio.run(test())
```

- [ ] **Step 4: 确认**

```bash
git add backend/app/services/ && git commit -m "feat: add RSS collector and cleaner services"
```

---

### Task 4: FastAPI 入口 + 分析任务 API

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/analysis.py`

- [ ] **Step 1: 创建 main.py**

```python
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import analysis

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="App Review Insights", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

app.include_router(analysis.router, prefix="/api")
```

- [ ] **Step 2: 创建 analysis.py（分析任务 CRUD + 启动分析 API）**

```python
"""分析任务 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.db import AnalysisTask
from app.models.schemas import TaskCreate, TaskResponse

router = APIRouter()

@router.post("/analysis/start", response_model=TaskResponse)
async def start_analysis(task: TaskCreate, db: AsyncSession = Depends(get_db)):
    """创建并启动分析任务"""
    # 1. 解析 app_id（从 URL 中提取）
    # 2. 创建 DB 记录
    # 3. 异步启动流水线（background task）
    ...

@router.get("/analysis/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    ...

@router.get("/analysis/{task_id}/reviews")
async def get_reviews(task_id: str, page: int = 1, rating: int = None, db: AsyncSession = Depends(get_db)):
    """获取评论列表（分页+筛选）"""
    ...

@router.get("/analysis/{task_id}/reviews/stats")
async def get_review_stats(task_id: str, db: AsyncSession = Depends(get_db)):
    """评论统计（评分分布、时间趋势、版本分布）"""
    ...

@router.get("/analysis/{task_id}/findings")
async def get_findings(task_id: str, db: AsyncSession = Depends(get_db)):
    ...

@router.get("/analysis/{task_id}/requirements")
async def get_requirements(task_id: str, db: AsyncSession = Depends(get_db)):
    ...

@router.get("/analysis/{task_id}/test-cases")
async def get_test_cases(task_id: str, db: AsyncSession = Depends(get_db)):
    ...
```

- [ ] **Step 3: 验证 API 可启动**

```bash
cd backend && uvicorn app.main:app --reload --port 8000 &
curl http://localhost:8000/docs
```

验证: 浏览器打开 http://localhost:8000/docs 看到 Swagger 文档

- [ ] **Step 4: 确认**

```bash
git add backend/app/main.py backend/app/routers/ && git commit -m "feat: add FastAPI entry and analysis API routes"
kill %1 2>/dev/null
```

---

### Task 5: SSE 事件管理器

**Files:**
- Create: `backend/app/event_manager.py`

- [ ] **Step 1: 创建 event_manager.py**

```python
"""SSE 事件管理 + 持久化"""
import asyncio, json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import AnalysisEvent

class EventManager:
    """每个任务一个 EventManager，管理 SSE 流和持久化"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._subscribers: list[asyncio.Queue] = []
        self._event_id = 0

    def subscribe(self) -> asyncio.Queue:
        """新 SSE 连接订阅"""
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def emit(self, event: str, stage: str, data: dict | None = None, db: AsyncSession | None = None):
        """广播事件到所有订阅者 + 持久化到 DB"""
        self._event_id += 1
        payload = {
            "id": self._event_id,
            "event": event,
            "stage": stage,
            "data": data or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # 广播到所有订阅者
        for q in self._subscribers:
            await q.put(payload)
        # 持久化非 progress 事件
        if event != "stage_progress" and db:
            db_event = AnalysisEvent(
                task_id=self.task_id, event=event, stage=stage, data=data
            )
            db.add(db_event)
            await db.commit()

    async def replay(self, db: AsyncSession, since_id: int = 0):
        """回放历史事件（断线重连用）"""
        from sqlalchemy import select
        result = await db.execute(
            select(AnalysisEvent)
            .where(AnalysisEvent.task_id == self.task_id, AnalysisEvent.id > since_id)
            .order_by(AnalysisEvent.id)
        )
        return result.scalars().all()


# 全局管理器注册表
_managers: dict[str, EventManager] = {}

def get_event_manager(task_id: str) -> EventManager:
    if task_id not in _managers:
        _managers[task_id] = EventManager(task_id)
    return _managers[task_id]
```

- [ ] **Step 2: 验证**

```python
import asyncio
em = EventManager("test")
async def test():
    await em.emit("stage_start", "scoping", {"detail": "start"})
em2 = EventManager("test")
print(f"Same instance: {em is em2}")  # True
```

- [ ] **Step 3: 确认**

```bash
git add backend/app/event_manager.py && git commit -m "feat: add SSE event manager"
```

---

### Task 6: 导入 API

**Files:**
- Create: `backend/app/routers/import_.py`

- [ ] **Step 1: 创建 import_.py**

复用 `demo/importer_demo.py` 的逻辑（CSV 解析、字段映射），保存为 endpoint。

```python
"""数据导入 API"""
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

router = APIRouter()

@router.post("/import")
async def import_reviews(file: UploadFile = File(...), task_id: str = None, db: AsyncSession = Depends(get_db)):
    """导入 JSON/CSV 评论数据"""
    content = await file.read()
    fmt = "csv" if file.filename.endswith(".csv") else "json"
    # 复用 importer_demo.py 的字段映射逻辑
    ...
```

- [ ] **Step 2: 验证**

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@demo/data/test_reviews.csv" \
  -F "task_id=test-import-1"
```

- [ ] **Step 3: 确认**
```bash
git add backend/app/routers/import_.py && git commit -m "feat: add data import API"
```

---

## 阶段二：前端框架 + SSE 实时展示

### Task 7: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`

- [ ] **Step 1: 初始化 Vite + React + TypeScript 项目**

```bash
cd frontend && npm create vite@latest . -- --template react-ts
npm install
```

- [ ] **Step 2: 安装 shadcn/ui 和 ECharts**

```bash
cd frontend && npx shadcn@latest init -d
npx shadcn@latest add button card tabs select progress badge separator
npm install echarts echarts-for-react
```

- [ ] **Step 3: 配置 Vite 代理（解决前后端跨域）**

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 4: 创建 types/index.ts**

```typescript
// TypeScript 类型定义
export interface AnalysisTask {
  id: string;
  app_url: string;
  app_id: string;
  goal: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_pct: number;
  current_stage: string;
  error?: string;
  created_at: string;
}

export interface ReviewItem {
  id: number;
  review_id: string;
  source: string;
  title?: string;
  content: string;
  rating: number;
  author: string;
  version?: string;
  date?: string;
  quality_score?: number;
}

export interface ReviewStats {
  rating_distribution: { rating: number; count: number }[];
  daily_trend: { date: string; count: number }[];
  version_distribution: { version: string; count: number }[];
}

export interface Finding {
  id: number;
  topic: string;
  confidence: 'high' | 'medium' | 'low';
  description: string;
  supporting_review_ids: number[];
  sample_count: number;
  representative_excerpts: string[];
  contradicting_evidence: any[];
  is_statistical: boolean;
  is_model_generated: boolean;
  status: string;
}

export interface SSEEvent {
  id: number;
  event: string;
  stage: string;
  data: any;
  created_at: string;
}

export interface Requirement {
  id: number;
  title: string;
  description: string;
  priority: string;
  version: string;
  status: string;
}

export interface TestCase {
  id: number;
  requirement_id: number;
  description: string;
  steps: string[];
  expected: string;
  verified: boolean;
}
```

- [ ] **Step 5: 确认**

```bash
cd frontend && npm run dev &
# 浏览器访问 http://localhost:5173 看到 Vite 默认页面
kill %1 2>/dev/null
git add frontend/ && git commit -m "feat: init frontend project with shadcn/ui and ECharts"
```

---

### Task 8: API 客户端 + SSE Hook

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useSSE.ts`

- [ ] **Step 1: 创建 api/client.ts**

```typescript
import type { AnalysisTask, ReviewItem, ReviewStats, Finding, Requirement, TestCase } from '../types';

const BASE = '/api';

export async function startAnalysis(app_url: string, goal: string): Promise<AnalysisTask> {
  const res = await fetch(`${BASE}/analysis/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_url, goal }),
  });
  return res.json();
}

export async function getTask(taskId: string): Promise<AnalysisTask> {
  const res = await fetch(`${BASE}/analysis/${taskId}`);
  return res.json();
}

export async function getReviews(taskId: string, page = 1, rating?: number): Promise<{ items: ReviewItem[]; total: number }> {
  const params = new URLSearchParams({ page: String(page) });
  if (rating) params.set('rating', String(rating));
  const res = await fetch(`${BASE}/analysis/${taskId}/reviews?${params}`);
  return res.json();
}

export async function getReviewStats(taskId: string): Promise<ReviewStats> {
  const res = await fetch(`${BASE}/analysis/${taskId}/reviews/stats`);
  return res.json();
}

export async function getFindings(taskId: string): Promise<Finding[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/findings`);
  return res.json();
}

export async function getRequirements(taskId: string): Promise<Requirement[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/requirements`);
  return res.json();
}

export async function getTestCases(taskId: string): Promise<TestCase[]> {
  const res = await fetch(`${BASE}/analysis/${taskId}/test-cases`);
  return res.json();
}
```

- [ ] **Step 2: 创建 useSSE.ts**

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import type { SSEEvent } from '../types';

interface UseSSEOptions {
  taskId: string | null;
  sinceId?: number;
}

export function useSSE({ taskId, sinceId = 0 }: UseSSEOptions) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!taskId) return;
    const es = new EventSource(`/api/analysis/${taskId}/stream?since_id=${sinceId}`);
    eventSourceRef.current = es;
    setConnected(true);

    es.addEventListener('message', (e) => {
      try {
        const event = JSON.parse(e.data) as SSEEvent;
        setEvents(prev => [...prev, event]);
      } catch { /* ignore parse errors */ }
    });

    es.onerror = () => {
      setConnected(false);
      es.close();
      // 3秒后自动重连
      setTimeout(connect, 3000);
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [taskId, sinceId]);

  useEffect(() => {
    const cleanup = connect();
    return () => cleanup?.();
  }, [connect]);

  return { events, connected };
}
```

- [ ] **Step 3: 确认**

```bash
git add frontend/src/api/ frontend/src/hooks/ && git commit -m "feat: add API client and SSE hook"
```

---

### Task 9: 主页面布局 + 输入面板

**Files:**
- Create: `frontend/src/components/AppInput.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 AppInput.tsx**

```tsx
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface AppInputProps {
  onStart: (url: string, goal: string) => void;
  loading: boolean;
}

export function AppInput({ onStart, loading }: AppInputProps) {
  const [url, setUrl] = useState('');
  const [goal, setGoal] = useState('');

  return (
    <Card className="p-6 mb-6">
      <h2 className="text-xl font-bold mb-4">App Store 评论分析</h2>
      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium mb-1 block">App Store 链接</label>
          <Input
            placeholder="https://apps.apple.com/us/app/.../id839285684"
            value={url}
            onChange={e => setUrl(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium mb-1 block">分析目标（可选）</label>
          <Textarea
            placeholder="例如：关注订阅转化和低评分评论"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            rows={2}
          />
        </div>
        <Button onClick={() => onStart(url, goal)} disabled={loading || !url}>
          {loading ? '分析中...' : '开始分析'}
        </Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: 更新 App.tsx**

```tsx
import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AppInput } from './components/AppInput';
import { ProgressPanel } from './components/ProgressPanel';
import { useSSE } from './hooks/useSSE';
import { startAnalysis, getTask } from './api/client';
import type { AnalysisTask } from './types';

export default function App() {
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [loading, setLoading] = useState(false);
  const { events, connected } = useSSE({ taskId: task?.id ?? null });

  const handleStart = async (url: string, goal: string) => {
    setLoading(true);
    try {
      const t = await startAnalysis(url, goal);
      setTask(t);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">App Review Insights</h1>
        <AppInput onStart={handleStart} loading={loading} />

        {task && (
          <ProgressPanel task={task} events={events} connected={connected} />
        )}

        {task?.status === 'completed' && (
          <Tabs defaultValue="reviews" className="mt-6">
            <TabsList>
              <TabsTrigger value="reviews">评论</TabsTrigger>
              <TabsTrigger value="findings">发现</TabsTrigger>
              <TabsTrigger value="prd">PRD</TabsTrigger>
              <TabsTrigger value="tests">测试</TabsTrigger>
            </TabsList>
            <TabsContent value="reviews">...</TabsContent>
            <TabsContent value="findings">...</TabsContent>
            <TabsContent value="prd">...</TabsContent>
            <TabsContent value="tests">...</TabsContent>
          </Tabs>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 确认**
```bash
git add frontend/src/ && git commit -m "feat: add main layout and input panel"
```

---

### Task 10: 进度面板 + 采集可视化

**Files:**
- Create: `frontend/src/components/ProgressPanel.tsx`
- Create: `frontend/src/components/StageCard.tsx`

- [ ] **Step 1: 创建 StageCard.tsx**

```tsx
import { Badge } from '@/components/ui/badge';

interface StageCardProps {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
}

const stageLabels: Record<string, string> = {
  scoping: '目标解析',
  collecting: '数据采集',
  cleaning: '清洗裁剪',
  analyzing: 'AI 分析',
  planning: '证据评估',
  prd: 'PRD 生成',
  testgen: '测试用例生成',
};

export function StageCard({ name, status, progress }: StageCardProps) {
  const label = stageLabels[name] || name;
  const statusMap = {
    pending: { icon: '○', color: 'text-gray-400' },
    running: { icon: '◌', color: 'text-blue-500 animate-pulse' },
    completed: { icon: '✓', color: 'text-green-500' },
    failed: { icon: '✕', color: 'text-red-500' },
  };
  const s = statusMap[status];
  return (
    <div className="flex items-center gap-3 p-3 border rounded-lg">
      <span className={`text-lg font-bold ${s.color}`}>{s.icon}</span>
      <span className="flex-1">{label}</span>
      {status === 'running' && progress !== undefined && (
        <span className="text-sm text-blue-500">{progress}%</span>
      )}
      {status === 'running' && <Badge variant="outline">进行中</Badge>}
      {status === 'completed' && <Badge className="bg-green-100 text-green-700">完成</Badge>}
      {status === 'failed' && <Badge variant="destructive">失败</Badge>}
    </div>
  );
}
```

- [ ] **Step 2: 创建 ProgressPanel.tsx**

进度面板：实时展示各阶段状态 + 采集进度条 + 实时评分分布图

```tsx
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { StageCard } from './StageCard';
import ReactECharts from 'echarts-for-react';
import type { SSEEvent, AnalysisTask } from '../types';

interface ProgressPanelProps {
  task: AnalysisTask;
  events: SSEEvent[];
  connected: boolean;
}

export function ProgressPanel({ task, events, connected }: ProgressPanelProps) {
  // 从 events 推导各阶段状态
  const stages = ['scoping', 'collecting', 'cleaning', 'analyzing', 'planning', 'prd', 'testgen'];
  const stageStatus: Record<string, string> = {};
  for (const s of stages) stageStatus[s] = 'pending';

  events.forEach(e => {
    if (e.event === 'stage_start') stageStatus[e.stage] = 'running';
    if (e.event === 'stage_complete') stageStatus[e.stage] = 'completed';
    if (e.event === 'stage_error') stageStatus[e.stage] = 'failed';
  });

  // 从 events 提取采集进度数据用于评分分布图
  const collectEvents = events.filter(e => e.stage === 'collecting' && e.data?.rating_distribution);
  const latestRatingData = collectEvents[collectEvents.length - 1]?.data?.rating_distribution || [];

  const ratingChartOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['5星', '4星', '3星', '2星', '1星'] },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: [5,4,3,2,1].map(r => {
        const found = latestRatingData.find((d: any) => d.rating === r);
        return found?.count || 0;
      }),
      itemStyle: {
        color: (params: any) => ['#22c55e','#86efac','#facc15','#f97316','#ef4444'][params.dataIndex],
      },
    }],
  };

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">分析进度</h3>
        <span className={`text-sm ${connected ? 'text-green-500' : 'text-red-500'}`}>
          {connected ? '已连接' : '断线重连中...'}
        </span>
      </div>

      <Progress value={task.progress_pct} className="mb-4" />

      <div className="space-y-2 mb-4">
        {stages.map(s => (
          <StageCard key={s} name={s} status={stageStatus[s] as any} />
        ))}
      </div>

      {/* 采集实时评分分布 */}
      {task.current_stage === 'collecting' && latestRatingData.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2">实时评分分布</h4>
          <ReactECharts option={ratingChartOption} style={{ height: 200 }} />
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 3: 确认**
```bash
git add frontend/src/components/ && git commit -m "feat: add progress panel with real-time visualization"
```

---

## 阶段三：AI Agent 分析流水线

### Task 11: LLM 抽象层（DeepSeek 适配）

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/base.py`
- Create: `backend/app/llm/factory.py`

- [ ] **Step 1: 创建 base.py**

```python
"""LLM 抽象基类"""
from abc import ABC, abstractmethod
from typing import Type
from pydantic import BaseModel

class LLMClient(ABC):
    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> str:
        """纯文本对话"""
        pass

    @abstractmethod
    async def chat_structured(self, messages: list, response_model: Type[BaseModel], **kwargs) -> BaseModel:
        """结构化输出（用于 LangChain function calling）"""
        pass
```

- [ ] **Step 2: 创建 factory.py**

```python
"""LLM 工厂"""
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Type
import json

from app import config
from app.llm.base import LLMClient

class DeepSeekClient(LLMClient):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
        self.model = "deepseek-chat"

    async def chat(self, messages: list, **kwargs) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages, **kwargs
        )
        return resp.choices[0].message.content or ""

    async def chat_structured(self, messages: list, response_model: Type[BaseModel], **kwargs) -> BaseModel:
        messages.append({
            "role": "system",
            "content": f"请以 JSON 格式输出，严格遵循以下 schema: {response_model.model_json_schema()}"
        })
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages, response_format={"type": "json_object"}, **kwargs
        )
        raw = resp.choices[0].message.content or "{}"
        return response_model.model_validate_json(raw)

def create_llm() -> LLMClient:
    if config.LLM_PROVIDER == "deepseek":
        return DeepSeekClient()
    raise ValueError(f"Unsupported provider: {config.LLM_PROVIDER}")
```

- [ ] **Step 3: 验证 LLM 连接**

```bash
cd backend && python -c "
import asyncio
from app.llm.factory import create_llm
llm = create_llm()
async def test():
    r = await llm.chat([{'role':'user','content':'hello'}])
    print(r)
asyncio.run(test())
"
```

- [ ] **Step 4: 确认**
```bash
git add backend/app/llm/ && git commit -m "feat: add LLM abstraction layer with DeepSeek"
```

---

### Task 12: LangChain Agent 分析

**Files:**
- Create: `backend/app/services/agent.py`
- Create: `backend/app/services/sampler.py`

- [ ] **Step 1: 创建 agent.py**

```python
"""LangChain Agent 分析服务"""
from typing import List
from pydantic import BaseModel

class Topic(BaseModel):
    topic: str
    description: str
    confidence: str  # high/medium/low

class FindingResult(BaseModel):
    findings: List[Topic]

class Evidence(BaseModel):
    topic: str
    supporting_review_ids: List[str]
    sample_count: int
    representative_excerpts: List[str]
    contradicting_evidence: List[str]

async def analyze_reviews(reviews: list[dict], llm, goal: str = "") -> list[dict]:
    """使用 LangChain Agent 分析评论，动态发现主题

    流程:
    1. topic_discovery: LLM 从评论中发现主题
    2. evidence_gathering: 对每个主题收集证据
    3. contradiction_check: 检查矛盾评论
    4. reflection: 自检（是否有≥2条支撑、是否记录矛盾）
    """
    # 构建 prompt
    reviews_text = "\n---\n".join(
        f"[{r['rating']}★] {r.get('title','')} {r.get('content','')}"
        for r in reviews[:50]  # 分批处理
    )
    messages = [
        {"role": "system", "content": "你是一个 App Store 评论分析师..."},
        {"role": "user", "content": f"分析目标: {goal}\n\n评论数据:\n{reviews_text}"},
    ]
    result = await llm.chat_structured(messages, FindingResult)
    # 转换为 dict 写入 DB
    return [f.model_dump() for f in result.findings]
```

- [ ] **Step 2: 创建 sampler.py**

复用 `demo/sampler_demo.py` 逻辑：高危关键词扫描 + 分层抽样

```python
"""评论采样/分块服务"""
def high_risk_scan(reviews, risk_keywords=None):
    """高危关键词扫描"""
    ...

def stratified_sample(reviews, target_count=200, seed=42):
    """三层抽样（高80%/中15%/低5%）"""
    ...

def split_blocks(reviews, block_size=100):
    """拆分为 100 条/块"""
    return [reviews[i:i+block_size] for i in range(0, len(reviews), block_size)]
```

- [ ] **Step 3: 验证**

```python
from app.services.sampler import high_risk_scan
reviews = [{"content": "This app crashes a lot", "rating": 1}]
risky, normal = high_risk_scan(reviews)
print(f"High risk: {len(risky)}")  # 1
```

- [ ] **Step 4: 确认**
```bash
git add backend/app/services/agent.py backend/app/services/sampler.py && git commit -m "feat: add LangChain Agent and sampler"
```

---

### Task 13: 证据评估 + PRD 生成 + 测试用例

**Files:**
- Create: `backend/app/services/planner.py`
- Create: `backend/app/services/testgen.py`

- [ ] **Step 1: 创建 planner.py**

```python
"""证据评估 + 版本规划 + PRD 生成"""
async def evaluate(findings: list[dict], llm) -> list[dict]:
    """三级标签：充分/有限/不足，按 frequency+severity 排序"""
    ...

async def plan_versions(findings: list[dict], llm) -> dict:
    """版本规划：V1 高置信度低成本 / V2 核心 / V3 探索"""
    ...

async def generate_prd(findings: list[dict], versions: dict, llm) -> str:
    """生成 Markdown 格式 PRD"""
    ...
```

- [ ] **Step 2: 创建 testgen.py**

```python
"""测试用例生成"""
async def generate_test_cases(requirements: list[dict], llm) -> list[dict]:
    """基于 PRD requirements 生成测试用例"""
    ...
```

- [ ] **Step 3: 确认**
```bash
git add backend/app/services/planner.py backend/app/services/testgen.py && git commit -m "feat: add planner and test generator"
```

---

### Task 14: 溯源性验证

**Files:**
- Create: `backend/app/services/validator.py`

- [ ] **Step 1: 创建 validator.py**

```python
"""溯源性验证"""
async def validate_traceability(task_id: str, db) -> dict:
    """验证 Review→Finding→Requirement→TestCase 链

    检查:
      - Finding→Review < 2 → pending_review
      - Requirement←Finding 缺失 → pending_review
      - TestCase←Requirement 缺失 → pending_review
      - 需求无用户问题支撑 → pending_review
    """
    ...
    return {"checked": count, "pending": pending_count, "passed": passed_count}
```

- [ ] **Step 2: 确认**
```bash
git add backend/app/services/validator.py && git commit -m "feat: add traceability validator"
```

---

### Task 15: 流水线编排

**Files:**
- Create: `backend/app/pipeline.py`

- [ ] **Step 1: 创建 pipeline.py**

```python
"""分析流水线编排"""
import asyncio, logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.event_manager import get_event_manager
from app.config import DATABASE_URL

logger = logging.getLogger("pipeline")

async def run_pipeline(task_id: str, app_id: str, goal: str, max_pages: int = 10):
    """按顺序执行所有阶段：scope→collect→clean→analyze→plan→prd→testgen→validate

    每个阶段:
      1. emit stage_start
      2. 执行服务
      3. emit stage_complete（或 stage_error）
    """
    em = get_event_manager(task_id)

    async with async_session() as db:
        try:
            # 阶段 1: 目标解析
            await em.emit("stage_start", "scoping", {}, db)
            await _update_task(db, task_id, current_stage="scoping", progress_pct=5)
            from app.services.scoper import parse_goal
            scope = await parse_goal(goal)
            await em.emit("scope_defined", "scoping", scope, db)
            await em.emit("stage_complete", "scoping", {}, db)

            # 阶段 2: 采集
            await em.emit("stage_start", "collecting", {}, db)
            await _update_task(db, task_id, current_stage="collecting", progress_pct=20)
            from app.services.collectors.rss import fetch_reviews
            rating_history = []
            async def on_page(page, page_reviews, total):
                dist = {r: sum(1 for rv in page_reviews if rv.rating == r) for r in range(1,6)}
                rating_history.append(dist)
                await em.emit("stage_progress", "collecting", {
                    "page": page, "total_pages": max_pages,
                    "count": total, "rating_distribution": [
                        {"rating": r, "count": sum(d.get(r, 0) for d in rating_history)}
                        for r in range(1, 6)
                    ],
                }, db)
            reviews = await fetch_reviews(app_id, db, task_id, max_pages, on_progress=on_page)
            await em.emit("stage_complete", "collecting",
                {"total": len(reviews), "pages": max_pages}, db)

            # 阶段 3: 清洗
            await em.emit("stage_start", "cleaning", {}, db)
            await _update_task(db, task_id, current_stage="cleaning", progress_pct=40)
            from app.services.cleaner import clean_reviews
            cleaned, stats = clean_reviews(reviews)
            # 写入 cleaned_reviews 表
            for cr in cleaned:
                db.add(cr)
            await db.commit()
            await em.emit("stage_complete", "cleaning", stats, db)

            # 阶段 4: AI 分析
            await em.emit("stage_start", "analyzing", {}, db)
            await _update_task(db, task_id, current_stage="analyzing", progress_pct=60)
            from app.services.sampler import split_blocks
            from app.services.agent import analyze_reviews
            from app.llm.factory import create_llm
            llm = create_llm()
            all_findings = []
            # 分块分析
            blocks = split_blocks([{
                "review_id": r.review_id, "content": r.content,
                "title": r.title, "rating": r.rating,
            } for r in cleaned], block_size=100)
            for i, block in enumerate(blocks):
                await em.emit("stage_progress", "analyzing",
                    {"block": i+1, "total_blocks": len(blocks)}, db)
                findings = await analyze_reviews(block, llm, goal)
                all_findings.extend(findings)
            await em.emit("stage_complete", "analyzing",
                {"findings_count": len(all_findings)}, db)

            # 阶段 5: 证据评估 + 版本规划 + PRD
            await em.emit("stage_start", "planning", {}, db)
            await _update_task(db, task_id, current_stage="planning", progress_pct=80)
            from app.services.planner import evaluate, plan_versions, generate_prd
            from app.models.db import Finding
            for f in all_findings:
                db.add(Finding(task_id=task_id, **f))
            await db.commit()
            await em.emit("stage_complete", "planning", {}, db)

            # 阶段 6: 标记完成
            await _update_task(db, task_id, status="completed", progress_pct=100, current_stage="done")
            await em.emit("analysis_complete", "done", {"task_id": task_id}, db)

        except Exception as e:
            logger.exception("Pipeline failed")
            await _update_task(db, task_id, status="failed", error=str(e))
            await em.emit("stage_error", "pipeline", {"error": str(e)}, db)


async def _update_task(db, task_id: str, **kwargs):
    from sqlalchemy import update
    from app.models.db import AnalysisTask
    await db.execute(update(AnalysisTask).where(AnalysisTask.id == task_id).values(**kwargs))
    await db.commit()
```

- [ ] **Step 2: 验证全流程串联**

```bash
cd backend && python -c "
import asyncio
from app.pipeline import run_pipeline
asyncio.run(run_pipeline('test-pipeline-1', '839285684', '关注订阅转化', max_pages=2))
"
```

- [ ] **Step 3: 确认**
```bash
git add backend/app/pipeline.py && git commit -m "feat: add analysis pipeline orchestrator"
```

---

## 阶段四：前端全量结果展示 + 收尾

### Task 16: 评论表格 + ECharts 多维可视化

**Files:**
- Create: `frontend/src/components/ReviewTable.tsx`
- Create: `frontend/src/components/ReviewCharts.tsx`

(具体代码略，按设计文档可视化方案实现：评分分布柱状图、时间趋势折线图、版本分布环形图、评分×时间热力图、评论数据表格分页+排序+搜索)

### Task 17: 分析结果展示

**Files:**
- Create: `frontend/src/components/FindingsView.tsx`
- Create: `frontend/src/components/PrdView.tsx`
- Create: `frontend/src/components/TestCasesView.tsx`

### Task 18: SSE 流路由 + 断线重连

**Files:**
- Modify: `backend/app/main.py`（添加 SSE 端点）
- Modify: `frontend/src/hooks/useSSE.ts`（完善重连逻辑）

```python
# main.py 添加 SSE 端点
from fastapi.responses import StreamingResponse
from app.event_manager import get_event_manager
import asyncio

@app.get("/api/analysis/{task_id}/stream")
async def stream_events(task_id: str, since_id: int = 0, db=Depends(get_db)):
    em = get_event_manager(task_id)
    # 先回放历史事件
    history = await em.replay(db, since_id)
    async def event_stream():
        for ev in history:
            yield f"data: {json.dumps({'id': ev.id, 'event': ev.event, 'stage': ev.stage, 'data': ev.data, 'created_at': ev.created_at.isoformat()})}\n\n"
        # 切换到实时流
        q = em.subscribe()
        try:
            while True:
                payload = await q.get()
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            em.unsubscribe(q)
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Task 19: 收尾与验证

- [ ] 前后端联调测试（完整跑通输入→采集→分析→展示流程）
- [ ] 数据库初始化脚本
- [ ] README 更新（运行说明、环境配置、技术栈说明）
- [ ] 最终验证：输入 app id 839285684 → 采集 500 条评论 → 清洗 →Agent 分析 → 展示
