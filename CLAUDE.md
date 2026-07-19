## 开发规则

1. **开始任何开发前**读取 `.claude/rules/constraints.md` 技术约束
2. **不修改数据库模型** — 新增字段到 `models/db.py` + `main.py` API + 前端 types 即可
3. **所有提示词在代码中** — agent.py / planner.py / testgen.py / ai_cleaner.py 的 `PROMPT` 常量
4. **不硬编码** — 分类/finding/PRD/测试用例均动态生成
5. `.env` 包含 `DEEPSEEK_API_KEY`，不配置时自动走 Mock 模式

## 项目结构速查

| 路径 | 职责 |
|------|------|
| `backend/app/pipeline.py` | 8 阶段流水线编排（核心入口） |
| `backend/app/services/agent.py` | AI 主题发现（模型驱动） |
| `backend/app/services/planner.py` | 证据评估 + PRD 生成 |
| `backend/app/services/cleaner.py` | 规则清洗去重（规则驱动） |
| `backend/app/services/ai_cleaner.py` | AI 垃圾检测 |
| `backend/app/services/testgen.py` | 测试用例生成 |
| `backend/app/services/validator.py` | 溯源验证 |
| `backend/app/services/collectors/rss.py` | RSS 分页采集 |
| `backend/app/event_manager.py` | SSE 事件管理 |
| `backend/app/models/db.py` | 8 张 ORM 表 |
| `frontend/src/App.tsx` | 主应用入口 |
| `frontend/src/components/` | 12 个 UI 组件 |

## API 路由

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/analysis/start` | 启动分析任务 |
| GET | `/api/analysis/{id}/stream` | SSE 事件流 |
| GET | `/api/analysis/{id}/findings` | AI 发现 |
| GET | `/api/analysis/{id}/requirements` | PRD 需求 |
| GET | `/api/analysis/{id}/test-cases` | 测试用例 |
| POST | `/api/import` | JSON/CSV 导入 |
| GET | `/api/tasks` | 历史任务列表 |

## MCP 工具

- **LangChain 文档**：`docs-langchain` MCP 查询 Agent/工具链参考
- **UI 设计**：`pencil` MCP 进行网页设计和原型
