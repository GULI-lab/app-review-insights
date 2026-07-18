"""
============================================================
演示 3: JSON/CSV 外部数据导入
============================================================

功能:
  从 JSON 或 CSV 文件导入评论数据，自动将输入列/字段
  映射到规范的评论 schema，输出为统一的 JSON 格式。

  导入的数据可以和 cleaner_demo 串联使用。

为什么需要这个功能(设计文档要求):
  - 支持 CSV/JSON 导入，始终可用，不受网络限制
  - 面试官可以提供任意的有效评论数据集进行测试
  - 确保系统不依赖于特定的数据源格式

用法:
  # 导入 JSON 文件（自动检测格式）
  python demo/importer_demo.py --input path/to/reviews.json

  # 导入 CSV 文件，指定列映射
  python demo/importer_demo.py --input reviews.csv --mapping '{"content":"review_text","rating":"score"}'

  # 创建测试 CSV 后导入
  python -c "import csv; open('demo/data/test.csv','w',newline='').write('content,rating\\n\"Great app!\",5\\n\"Too buggy\",1\\n')"
  python demo/importer_demo.py --input demo/data/test.csv
"""

import argparse
import csv
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("importer_demo")

# ----------------------------------------------------------
# 规范字段定义
# ----------------------------------------------------------
# 输出的评论必须包含这些字段
CANONICAL_FIELDS = [
    "review_id",
    "author",
    "title",
    "content",
    "rating",
    "version",
    "date",
]

# 必需字段（缺失则该行跳过）
REQUIRED_FIELDS = ["content", "rating"]

# 输入字段到规范字段的自动映射字典
# 每个规范字段对应一组可能的输入别名
FIELD_ALIASES: dict[str, list[str]] = {
    "review_id": ["review_id", "reviewId", "review-id", "id", "entry_id", "entryId"],
    "author": ["author", "user", "username", "user_name", "name", "reviewer", "reviewer_name"],
    "title": ["title", "subject", "headline"],
    "content": ["content", "body", "text", "review", "description", "message", "review_text", "reviewText"],
    "rating": ["rating", "score", "stars", "star_rating", "starRating", "im:rating", "im_rating"],
    "version": ["version", "app_version", "appVersion", "app-version", "im:version", "im_version"],
    "date": ["date", "created", "created_at", "createdAt", "timestamp", "updated",
             "review_date", "reviewDate", "review-date"],
}


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="从 JSON/CSV 导入评论数据")
    parser.add_argument("--input", required=True, help="输入文件路径（JSON 或 CSV）")
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        help="输入格式（不指定则从文件扩展名自动检测）",
    )
    parser.add_argument(
        "--mapping",
        help=(
            "自定义字段映射 JSON，例如: "
            '{"content":"review_text","rating":"star_rating"}'
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="demo/data",
        help="输出目录，默认: demo/data",
    )
    return parser.parse_args()


def detect_format(filepath: str) -> str:
    """根据文件扩展名检测格式"""
    ext = Path(filepath).suffix.lower()
    if ext == ".csv":
        return "csv"
    elif ext == ".json":
        return "json"
    else:
        logger.error("无法检测格式，请使用 --format 指定（json/csv）")
        sys.exit(1)


def read_file_with_encoding(filepath: str) -> str:
    """读取文件内容，自动检测编码

    优先 UTF-8（含 BOM），回退 GBK。
    这是为了兼容中文字符集的 CSV 文件。
    """
    path = Path(filepath)
    if not path.exists():
        logger.error("文件不存在: %s", filepath)
        sys.exit(1)

    # 尝试 UTF-8（处理 BOM）
    for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue

    logger.error("无法解码文件（尝试了 UTF-8、GBK、GB18030）: %s", filepath)
    sys.exit(1)


def build_field_mapping(
    available_fields: list[str],
    custom_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    """构建输入字段到规范字段的映射

    策略:
      1. 优先使用用户提供的 --mapping 覆盖
      2. 然后遍历 FIELD_ALIASES 进行别名匹配
      3. 未匹配的规范字段保留为 None，不影响导入
    """
    mapping: dict[str, str] = {}
    used_input_fields = set()

    # 步骤 1: 应用自定义映射
    if custom_mapping:
        for canonical, input_field in custom_mapping.items():
            if input_field in available_fields:
                mapping[input_field] = canonical
                used_input_fields.add(input_field)
                logger.info("自定义映射: %s → %s", input_field, canonical)

    # 步骤 2: 自动别名匹配
    for canonical, aliases in FIELD_ALIASES.items():
        if canonical in (custom_mapping or {}):
            continue  # 已通过自定义映射处理

        for alias in aliases:
            if alias in available_fields and alias not in used_input_fields:
                mapping[alias] = canonical
                used_input_fields.add(alias)
                logger.debug("自动映射: %s → %s", alias, canonical)
                break

    # 输出映射结果
    if mapping:
        logger.info(
            "字段映射: %s",
            ", ".join(f"{v}={k}" for k, v in sorted(mapping.items())),
        )
    else:
        logger.warning("未能自动映射任何字段")

    # 未映射的输入字段
    unmapped = set(available_fields) - used_input_fields
    if unmapped:
        logger.info("未映射字段(忽略): %s", ", ".join(sorted(unmapped)))

    return mapping


def normalize_value(value: str, canonical_field: str) -> str | int | None:
    """将导入的值转换为规范类型"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    value_str = str(value).strip()

    if canonical_field == "rating":
        # 评分需要转为整数 1-5
        try:
            rating = int(float(value_str))
            if 1 <= rating <= 5:
                return rating
            logger.warning("评分值 %s 超出范围 1-5，设为 None", value_str)
            return None
        except (ValueError, TypeError):
            logger.warning("评分值 %s 无法转换为整数，设为 None", value_str)
            return None

    return value_str


def import_json(
    content: str,
    field_mapping: dict[str, str],
) -> list[dict]:
    """从 JSON 导入评论

    支持三种 JSON 结构:
      1. 顶层数组: [{"content": "...", "rating": 5}, ...]
      2. 字典嵌套: {"reviews": [...], "data": {"items": [...]}}
      3. 单条评论: {"content": "...", "rating": 5}
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析错误: %s", e)
        return []

    # 确保是列表
    if isinstance(data, dict):
        # 尝试常见的嵌套键
        for key in ["reviews", "data", "items", "results", "entries", "feed"]:
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # 假设字典本身就是一条评论
            data = [data]

    if not isinstance(data, list):
        logger.error("JSON 结构无法识别（既不是数组也不是已知键的数组）")
        return []

    reviews = []
    skipped = 0

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            skipped += 1
            continue

        review = {}
        has_required = True

        for input_field, canonical in field_mapping.items():
            # 支持点分隔路径（如 "attributes.rating"）
            value = item
            for part in input_field.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break

            try:
                normalized = normalize_value(value, canonical)
            except (ValueError, TypeError):
                normalized = None

            review[canonical] = normalized

            # 检查必需字段
            if canonical in REQUIRED_FIELDS and normalized is None:
                has_required = False

        if has_required:
            # 填充缺失的规范字段
            for field in CANONICAL_FIELDS:
                if field not in review:
                    review[field] = None
            review["_source_row"] = i
            reviews.append(review)
        else:
            skipped += 1

    if skipped:
        logger.warning("跳过了 %d 行（缺少必需字段 content/rating）", skipped)

    return reviews


def import_csv(
    content: str,
    field_mapping: dict[str, str],
) -> list[dict]:
    """从 CSV 导入评论

    使用 csv.DictReader 逐行读取，避免大文件一次性加载内存。
    """
    lines = content.splitlines()
    if not lines:
        logger.error("CSV 文件为空")
        return []

    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        logger.error("CSV 文件没有表头行")
        return []

    # 确保请求的映射字段在 CSV 列中存在
    available = set(reader.fieldnames)
    for input_field in field_mapping:
        if input_field not in available:
            logger.warning("映射字段 '%s' 在 CSV 列中不存在", input_field)

    reviews = []
    skipped = 0

    for row_idx, row in enumerate(reader):
        review = {}
        has_required = True

        for input_field, canonical in field_mapping.items():
            value = row.get(input_field, "")
            try:
                normalized = normalize_value(value, canonical)
            except (ValueError, TypeError):
                normalized = None

            review[canonical] = normalized

            if canonical in REQUIRED_FIELDS and normalized is None:
                has_required = False

        if has_required:
            for field in CANONICAL_FIELDS:
                if field not in review:
                    review[field] = None
            review["_source_row"] = row_idx + 1  # +1 跳过表头
            reviews.append(review)
        else:
            skipped += 1

    if skipped:
        logger.warning("跳过了 %d 行（缺少必需字段 content/rating）", skipped)

    return reviews


def print_summary(reviews: list[dict], filepath: str, fmt: str) -> None:
    """打印导入摘要"""
    print(f"\n{'=' * 50}")
    print("[OK] 导入完成报告")
    print(f"{'=' * 50}")
    print(f"  源文件:     {filepath}")
    print(f"  格式:       {fmt}")
    print(f"  导入评论:   {len(reviews)} 条")

    if not reviews:
        print(f"{'=' * 50}\n")
        return

    ratings = {}
    for r in reviews:
        rating = r.get("rating")
        if rating:
            ratings[rating] = ratings.get(rating, 0) + 1

    print(f"  评分分布:")
    for star in sorted(ratings.keys(), reverse=True):
        count = ratings[star]
        bar = "#" * (count // 3)
        print(f"    {star}星: {count:>4}条 {bar}")

    # 显示前3条预览
    print(f"\n  预览(前3条):")
    for r in reviews[:3]:
        content_preview = (r.get("content") or "")[:50]
        print(f"    [{r.get('rating')}星] {content_preview}...")
    print(f"{'=' * 50}\n")


def main():
    """主流程"""
    args = parse_args()

    # 检测文件格式
    fmt = args.format or detect_format(args.input)
    logger.info("检测到格式: %s", fmt)

    # 读取文件内容
    content = read_file_with_encoding(args.input)

    # 解析自定义映射
    custom_mapping = None
    if args.mapping:
        try:
            custom_mapping = json.loads(args.mapping)
        except json.JSONDecodeError as e:
            logger.error("自定义映射 JSON 解析失败: %s", e)
            sys.exit(1)

    # 检测可用的输入字段
    if fmt == "json":
        try:
            sample = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败: %s", e)
            sys.exit(1)

        if isinstance(sample, list) and len(sample) > 0 and isinstance(sample[0], dict):
            available_fields = list(sample[0].keys())
        elif isinstance(sample, dict):
            # 尝试查找嵌套数组
            for key in ["reviews", "data", "items", "results", "entries"]:
                if key in sample and isinstance(sample[key], list) and len(sample[key]) > 0:
                    available_fields = list(sample[key][0].keys()) if isinstance(sample[key][0], dict) else []
                    break
            else:
                available_fields = list(sample.keys())
        else:
            available_fields = []
    else:
        # CSV: 从第一行解析列名
        first_line = content.splitlines()[0]
        # 尝试用 csv 解析器读取表头
        import io
        try:
            sample_reader = csv.DictReader(io.StringIO(content))
            available_fields = sample_reader.fieldnames or []
        except Exception:
            available_fields = first_line.split(",")

    if not available_fields:
        logger.error("无法从文件中检测到字段列")
        sys.exit(1)

    logger.info("检测到输入字段: %s", ", ".join(available_fields))

    # 构建字段映射
    field_mapping = build_field_mapping(available_fields, custom_mapping)

    if not field_mapping:
        logger.error("无法映射任何字段，请使用 --mapping 手动指定")
        sys.exit(1)

    # 执行导入
    if fmt == "json":
        reviews = import_json(content, field_mapping)
    else:
        reviews = import_csv(content, field_mapping)

    if not reviews:
        logger.warning("未导入任何有效评论（检查数据格式和必需字段）")
        return

    # 保存输出
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_file = output_dir / f"imported_reviews_{timestamp}.json"

    output = {
        "meta": {
            "source_file": str(Path(args.input).name),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "format": fmt,
            "field_mapping": field_mapping,
            "total_count": len(reviews),
        },
        "reviews": reviews,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("导入结果保存至: %s", output_file)
    print_summary(reviews, args.input, fmt)


if __name__ == "__main__":
    main()
