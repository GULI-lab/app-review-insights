# App Review Insights —— Demo 最小功能单元

## 概述

`demo/` 目录包含 App Review Insights 平台的最小功能单元演示脚本。
每个脚本是**自包含、可独立运行**的 Python 程序，仅依赖 Python 标准库。
代码注释全部使用中文，详细说明设计理由和实现细节。

## Demo 列表

| 脚本 | 功能 | 前置依赖 |
|------|------|----------|
| `rss_feed_demo.py` | 通过 Apple RSS Feed API 分页抓取 App Store 真实评论 | 无 |
| `cleaner_demo.py` | 评论清洗去重（规则驱动，无需 LLM） | demo 1 的输出 |
| `importer_demo.py` | 从 JSON/CSV 导入评论，自动字段映射 | 用户提供数据 |
| `sampler_demo.py` | 分层抽样 + 高危关键词扫描 | demo 2 的输出 |

## 数据流

```
rss_feed_demo.py ──→ raw_reviews.json ──→ cleaner_demo.py ──→ cleaned_reviews.json ──→ sampler_demo.py ──→ sampled_reviews.json

                  importer_demo.py ──→ imported_reviews.json ──┘
                  (独立，用户提供 JSON/CSV)
```

所有输出文件保存在 `demo/data/` 目录，格式为 JSON。

## 运行顺序

### 第 1 步：采集评论

```bash
# 快速测试（只抓 1 页，约 50 条）
python demo/rss_feed_demo.py --max-pages 1

# 完整抓取（10 页，约 500 条）
python demo/rss_feed_demo.py --app-id 839285684

# 按最有帮助排序
python demo/rss_feed_demo.py --app-id 839285684 --sort mosthelpful
```

输出：`demo/data/raw_reviews_{app_id}_{timestamp}.json`

### 第 2 步：清洗去重

```bash
# 自动查找最新的原始评论文件
python demo/cleaner_demo.py

# 或指定输入文件
python demo/cleaner_demo.py --input demo/data/raw_reviews_839285684_20260718T133408.json
```

输出：`demo/data/cleaned_reviews_{app_id}_{timestamp}.json`

### 第 3a 步：导入外部数据（可选）

```bash
# 导入 CSV 文件
python demo/importer_demo.py --input path/to/reviews.csv

# 导入 JSON 文件，带自定义字段映射
python demo/importer_demo.py --input reviews.json --mapping '{"content":"my_text","rating":"score"}'
```

输出：`demo/data/imported_reviews_{timestamp}.json`

### 第 3b 步：分层抽样

```bash
# 对清洗后的评论执行抽样
python demo/sampler_demo.py --input demo/data/cleaned_reviews_*.json

# 指定目标样本量
python demo/sampler_demo.py --input demo/data/cleaned_reviews_*.json --target 100
```

输出：`demo/data/sampled_reviews_{app_id}_{timestamp}.json`

### 一键串联执行

```bash
python demo/rss_feed_demo.py --max-pages 3 && \
python demo/cleaner_demo.py && \
python demo/sampler_demo.py --input demo/data/cleaned_reviews_*.json
```

## 设计原则

1. **仅标准库**：所有 demo 使用 Python 标准库（urllib、json、csv、re 等），不依赖第三方包
2. **确定性规则**：清洗、采样阶段使用 100% 规则驱动，不涉及 LLM 调用
3. **自包含**：每个脚本独立可运行，`python xxx.py` 即可执行
4. **输出可串联**：前一个脚本的输出可直接作为下一个脚本的输入
5. **边缘情况处理**：SSL 证书降级、网络超时重试、编码自动检测、编码回退等

## 数据格式

### 输入格式（JSON/CSV 导入）

支持字段别名自动映射：

| 规范字段  | 支持别名 |
|-----------|----------|
| review_id | id, reviewId, entry_id |
| author    | user, username, name, reviewer |
| title     | subject, headline |
| content   | body, text, review, description |
| rating    | score, stars, star_rating |
| version   | app_version, appVersion |
| date      | created, timestamp, updated, review_date |

必需字段：`content`（评论内容）、`rating`（评分）

### 输出格式

所有 demo 输出统一为：

```json
{
  "meta": {
    "app_id": "839285684",
    "source": "Apple RSS Feed",
    "output_count": 50,
    ...
  },
  "reviews": [
    {
      "review_id": "...",
      "author": "user123",
      "title": "标题",
      "content": "评论正文",
      "rating": 5,
      "version": "8.4.26",
      "date": "2026-07-18T06:25:09-07:00",
      ...
    }
  ]
}
```

## 注意事项

- Windows 环境 SSL 证书验证可能失败，脚本会自动降级处理
- RSS Feed 每页间隔 ≥ 1 秒，避免触发 Apple 限流
- 输出 JSON 使用 UTF-8 编码（含中文评论）
- 所有输出文件在 `.gitignore` 中排除，不提交到仓库
