"""
============================================================
演示 1: Apple RSS Feed 评论采集
============================================================

功能:
  通过 Apple RSS Feed API 分页抓取 App Store 的真实用户评论，
  保存为结构化的 JSON 文件。

为什么用 RSS Feed:
  - Apple 官方提供的接口，无需爬虫/逆向工程
  - 返回结构化 JSON，解析成本低
  - 遵守 Apple 服务条款，合规风险最小

数据流:
  RSS Feed API → 分页抓取(每页50条，最多10页=500条) → raw_reviews.json

采集地址:
  https://itunes.apple.com/us/rss/customerreviews/page={page}
                                    /id={app_id}
                                    /sortby={sort}
                                    /json

用法:
  # 快速测试(只抓1页，约50条)
  python demo/rss_feed_demo.py --max-pages 1

  # 完整抓取(10页，约500条)
  python demo/rss_feed_demo.py --app-id 839285684

  # 按最有帮助排序
  python demo/rss_feed_demo.py --sort mosthelpful

注意事项:
  - Windows 上可能出现 SSL 证书验证失败，脚本会自动降级处理
  - 每页间隔 >= 1 秒，避免触发限流
  - 如果某页失败会自动重试 3 次
"""

import argparse
import json
import logging
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ------------------------------------------------------------------
# 日志配置：同时输出到控制台，方便观察进度
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rss_feed_demo")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="通过 Apple RSS Feed 采集 App Store 真实评论"
    )
    parser.add_argument(
        "--app-id",
        default="839285684",  # Workout for Women - Lose Weight
        help="App Store 应用 ID（纯数字），默认: 839285684",
    )
    parser.add_argument(
        "--sort",
        default="mostrecent",
        choices=["mostrecent", "mosthelpful"],
        help="排序方式: mostrecent(最新) / mosthelpful(最有帮助)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="最大抓取页数(每页50条)，默认 10 页 = 500 条",
    )
    parser.add_argument(
        "--output-dir",
        default="demo/data",
        help="输出目录，默认: demo/data",
    )
    parser.add_argument(
        "--storefront",
        default="us",
        help="App Store 国家代码（us/cn/jp 等），默认 us",
    )
    return parser.parse_args()


def validate_app_id(app_id: str) -> bool:
    """验证 app_id 是否为纯数字（Apple 的 app_id 格式）"""
    return bool(re.fullmatch(r"\d+", app_id))


def build_rss_url(app_id: str, page: int, sort: str, storefront: str = "us") -> str:
    """构建 RSS Feed API URL

    Apple RSS Feed 端点说明:
      - page: 页码，从 1 开始
      - id:   App Store 应用 ID（纯数字）
      - sort: mostrecent(最新) / mosthelpful(最有帮助)
      - storefront: 国家代码（us/cn/jp 等），默认 us，通过 cc 查询参数指定
      - 响应格式: json

    注意: Apple 在 2026 年 7 月静默变更了路由，旧路径 /{storefront}/rss/...
    返回空 200 响应，需改用 /rss/...?cc={storefront} 格式。
    """
    return (
        f"https://itunes.apple.com/rss/customerreviews/"
        f"page={page}/id={app_id}/sortby={sort}/json"
        f"?cc={storefront}"
    )


# 宽松的 SSL 上下文（在 Windows 某些环境证书验证会失败）
PERMISSIVE_SSL_CTX = ssl.create_default_context()
PERMISSIVE_SSL_CTX.check_hostname = False
PERMISSIVE_SSL_CTX.verify_mode = ssl.CERT_NONE


def create_ssl_context(strict: bool = True) -> ssl.SSLContext:
    """创建 SSL 上下文

    在某些 Windows + Python 3.12 环境中，默认的 SSL 证书验证
    可能失败（CERTIFICATE_VERIFY_FAILED），此时用非严格模式降级。
    """
    if strict:
        return ssl.create_default_context()
    return PERMISSIVE_SSL_CTX


def fetch_page(url: str, timeout: int = 15) -> dict | None:
    """抓取单页 RSS Feed 数据

    参数:
      url: RSS Feed 完整 URL
      timeout: 请求超时秒数

    返回:
      解析后的 JSON 字典，失败返回 None

    重试策略:
      - SSL 证书错误: 降级验证后立即重试
      - 网络超时: 等待后重试（最多 3 次）
      - HTTP 429(限流): 等待后重试
      - 其他 HTTP 错误: 放弃并记录
    """
    last_error = None

    for attempt in range(3):
        try:
            # 第一次用严格 SSL，第二次开始用宽松 SSL
            use_strict = (attempt == 0)
            ctx = create_ssl_context(strict=use_strict)
            if not use_strict:
                logger.info("使用宽松 SSL 模式（跳过证书验证）")

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "AppReviewInsightsDemo/1.0 "
                        "(RSS Feed collector; educational project)"
                    ),
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                status = resp.status
                if status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data
                elif status == 429:
                    wait = 5 * (attempt + 1)  # 5秒、10秒、15秒 指数退避
                    logger.warning("HTTP 429 限流，等待 %d 秒后重试...", wait)
                    time.sleep(wait)
                    last_error = f"HTTP 429 (attempt {attempt + 1})"
                    continue
                else:
                    logger.error("HTTP %d: %s", status, url)
                    return None

        except ssl.CertificateError as e:
            # SSL 证书验证失败 → 下次用宽松模式
            logger.warning("SSL 证书验证失败: %s，降级重试...", e)
            last_error = str(e)
            continue

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (attempt + 1)
                logger.warning("HTTP 429 限流，等待 %d 秒后重试...", wait)
                time.sleep(wait)
                last_error = f"HTTP 429 (attempt {attempt + 1})"
                continue
            logger.error("HTTP %d: %s", e.code, url)
            return None

        except urllib.error.URLError as e:
            last_error = str(e)
            if attempt < 2:
                wait = 2 ** attempt  # 1秒、2秒
                logger.warning("网络错误(%s)，%d 秒后重试...", last_error, wait)
                time.sleep(wait)
                continue

        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败: %s", e)
            return None

    logger.error("重试 3 次后仍然失败: %s", last_error)
    return None


def extract_reviews(entries: list, fetch_page_num: int) -> list[dict]:
    """从 RSS Feed 的 entry 列表中提取评论数据

    RSS Feed 返回的结构:
      feed.entry[] 包含两类条目:
        - 应用元数据（im:contentType.attributes.term == "Application"，
          且没有 im:rating 字段）→ 跳过
        - 用户评论（有 im:rating 字段）→ 提取

    每个评论条目提取的字段:
      - review_id:   Apple 分配的评论 ID（entry.id.label）
      - author:      用户名
      - title:       评论标题
      - content:     评论正文（RSS 可能截断长评论）
      - rating:      评分 1-5
      - version:     用户评论时的 App 版本（可能缺失）
      - date:        ISO 8601 格式日期
      - vote_count:  有用投票数
      - vote_sum:    投票总分
      - fetch_page:  抓取时的页码（便于溯源）
    """
    reviews = []

    for entry in entries:
        # 跳过应用元数据条目（没有评分的就不是评论）
        rating_label = (
            entry.get("im:rating", {})
            .get("label", None)
        )
        if rating_label is None:
            continue

        # 提取各字段，缺失的用 None 填充
        def safe_get(obj, *keys):
            """安全地从嵌套字典中取值"""
            current = obj
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
            return current

        review = {
            "review_id": safe_get(entry, "id", "label"),
            "author": safe_get(entry, "author", "name", "label"),
            "title": safe_get(entry, "title", "label"),
            "content": safe_get(entry, "content", "label"),
            "rating": int(rating_label) if rating_label else None,
            "version": safe_get(entry, "im:version", "label"),
            "date": safe_get(entry, "updated", "label"),
            "vote_count": safe_get(entry, "im:voteCount", "label"),
            "vote_sum": safe_get(entry, "im:voteSum", "label"),
            "fetch_page": fetch_page_num,
        }

        # 字段规范化：rating 必须是 1-5 的整数
        if review["rating"] is not None and not (1 <= review["rating"] <= 5):
            logger.warning("异常评分 %s，跳过", review["rating"])
            continue

        # vote_count 和 vote_sum 转为整数
        for field in ["vote_count", "vote_sum"]:
            if review[field] is not None:
                try:
                    review[field] = int(review[field])
                except (ValueError, TypeError):
                    review[field] = None

        reviews.append(review)

    return reviews


def save_checkpoint(
    reviews: list[dict],
    meta: dict,
    output_dir: str,
    app_id: str,
    timestamp: str,
) -> str:
    """增量保存已抓取的评论到 JSON 文件

    每抓取一页就保存一次，即使脚本中途中断也能保留部分数据。
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"raw_reviews_{app_id}_{timestamp}.json"
    filepath = output_dir_path / filename

    output = {
        "meta": meta,
        "reviews": reviews,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return str(filepath)


def print_summary(reviews: list[dict], total_pages: int) -> None:
    """在控制台打印采集结果摘要"""
    if not reviews:
        print("\n[WARN] 未获取到任何评论。")
        return

    ratings = {}
    for r in reviews:
        rating = r.get("rating")
        ratings[rating] = ratings.get(rating, 0) + 1

    print(f"\n{'=' * 50}")
    print(f"[OK] 采集完成摘要")
    print(f"{'=' * 50}")
    print(f"  抓取页数:    {total_pages}")
    print(f"  评论总数:    {len(reviews)}")
    print(f"  评分分布:")
    for star in sorted(ratings.keys(), reverse=True):
        count = ratings[star]
        bar = "#" * (count // 5)
        print(f"    {star}星: {count:>4}条 {bar}")
    print(f"{'=' * 50}\n")


def main():
    """主流程: 解析参数 → 逐页抓取 → 增量保存 → 打印摘要"""
    args = parse_args()

    # ----------------------------------------------------------
    # 步骤 1: 验证参数
    # ----------------------------------------------------------
    if not validate_app_id(args.app_id):
        logger.error("无效的 app_id: %s（必须是纯数字）", args.app_id)
        sys.exit(1)

    # ----------------------------------------------------------
    # 步骤 2: 初始化
    # ----------------------------------------------------------
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    all_reviews: list[dict] = []
    total_entries = 0

    meta = {
        "app_id": args.app_id,
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "sort_by": args.sort,
        "pages_fetched": 0,
        "total_reviews": 0,
        "source": "Apple RSS Feed",
        "url_template": (
            "https://itunes.apple.com/cn/rss/customerreviews/"
            "page={page}/id={app_id}/sortby={sort}/json"
        ),
    }

    logger.info("=" * 50)
    logger.info("开始采集 App ID: %s", args.app_id)
    logger.info("排序方式: %s", args.sort)
    logger.info("目标页数: %d（约 %d 条）", args.max_pages, args.max_pages * 50)
    logger.info("=" * 50)

    # ----------------------------------------------------------
    # 步骤 3: 逐页抓取
    # ----------------------------------------------------------
    for page in range(1, args.max_pages + 1):
        url = build_rss_url(args.app_id, page, args.sort, args.storefront)
        logger.info("正在抓取第 %d/%d 页...", page, args.max_pages)

        data = fetch_page(url)

        if data is None:
            logger.warning("第 %d 页抓取失败，跳过继续下一页", page)
            continue

        # 从 feed.entry 中提取评论
        feed = data.get("feed", {})
        entries = feed.get("entry", [])

        if not entries:
            logger.info("第 %d 页无评论数据，提前结束分页", page)
            break

        page_reviews = extract_reviews(entries, page)
        all_reviews.extend(page_reviews)
        total_entries += len(entries)

        # 更新 meta 并保存检查点
        meta["pages_fetched"] = page
        meta["total_reviews"] = len(all_reviews)
        saved_path = save_checkpoint(
            all_reviews, meta, args.output_dir, args.app_id, timestamp
        )

        logger.info(
            "第 %d 页完成: 提取 %d 条评论（累计 %d 条）→ %s",
            page,
            len(page_reviews),
            len(all_reviews),
            saved_path,
        )

        # ----------------------------------------------------------
        # 限流控制：每页间隔至少 1 秒
        # 避免触发 Apple 的请求频率限制
        # ----------------------------------------------------------
        if page < args.max_pages:
            time.sleep(1.2)

    # ----------------------------------------------------------
    # 步骤 4: 打印摘要
    # ----------------------------------------------------------
    print_summary(all_reviews, meta["pages_fetched"])

    logger.info("最终输出文件: %s", saved_path)
    return all_reviews


if __name__ == "__main__":
    main()
