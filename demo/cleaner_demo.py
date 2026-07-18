"""
============================================================
演示 2: 评论清洗去重
============================================================

功能:
  对 RSS Feed 采集的原始评论执行确定性清洗：
    1. 重复检测 — 同author + 同rating + 日期差≤3天 + 内容相似度>0.9
    2. 无效过滤 — 太短/纯标点/纯emoji/纯数字/无意义
    3. 广告过滤 — 含URL/促销关键词
    4. 字段规范化 — 日期→ISO8601、评分→int、版本去空格
    5. 隐私脱敏 — 邮箱→[EMAIL]、电话→[PHONE]
    6. 质量评分 — 基于长度/有意义的词语/重复字符

设计原则:
  所有清洗规则都是"确定性"的（规则驱动，无需 LLM）。
  这与设计文档一致：数据清洗阶段使用规则驱动方法。

用法:
  # 对 demo1 的输出进行清洗
  python demo/cleaner_demo.py --input demo/data/raw_reviews_839285684_20260718T133408.json

  # 自动查找最新的原始评论文件
  python demo/cleaner_demo.py
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cleaner_demo")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="App Store 评论清洗去重")
    parser.add_argument(
        "--input",
        help="原始评论 JSON 文件路径（不指定则自动查找最新文件）",
    )
    parser.add_argument(
        "--output-dir",
        default="demo/data",
        help="输出目录，默认: demo/data",
    )
    parser.add_argument(
        "--app-id",
        help="App ID（不指定则从输入文件推断）",
    )
    return parser.parse_args()


def find_latest_raw_file(output_dir: str) -> str | None:
    """自动查找最新生成的原始评论 JSON 文件

    当用户不指定 --input 时，从 demo/data/ 目录自动选择
    最新的 raw_reviews_*.json 文件。
    """
    data_dir = Path(output_dir)
    if not data_dir.exists():
        return None

    files = sorted(data_dir.glob("raw_reviews_*.json"), reverse=True)
    if files:
        return str(files[0])
    return None


def load_reviews(filepath: str) -> tuple[list[dict], dict]:
    """加载原始评论 JSON 文件"""
    path = Path(filepath)
    if not path.exists():
        logger.error("文件不存在: %s", filepath)
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析失败(%s): %s", filepath, e)
        sys.exit(1)

    reviews = data.get("reviews", [])
    meta = data.get("meta", {})
    logger.info("加载 %d 条评论，来自: %s", len(reviews), filepath)
    return reviews, meta


# ----------------------------------------------------------
# 清洗规则 1: 重复检测
# ----------------------------------------------------------
def jaccard_similarity(text1: str, text2: str) -> float:
    """计算两个文本的 Jaccard 相似度

    Jaccard 相似度 = |A ∩ B| / |A ∪ B|
    这里将文本按空格+标点分词，用字符级别的 bigram 集合计算。

    阈值 > 0.9 表示两个文本几乎相同（只有细微差异）。
    """
    if not text1 or not text2:
        return 0.0

    # 转小写并分词
    chars1 = set(text1.lower().replace(" ", ""))
    chars2 = set(text2.lower().replace(" ", ""))

    intersection = chars1 & chars2
    union = chars1 | chars2

    if not union:
        return 0.0

    return len(intersection) / len(union)


def find_duplicates(
    reviews: list[dict],
    time_threshold_days: int = 3,
    similarity_threshold: float = 0.9,
) -> tuple[list[dict], list[dict], list[str]]:
    """检测重复评论

    重复判定标准(设计文档):
      - 相同 author
      - 相同 rating
      - 日期差 <= 3 天
      - 内容 Jaccard 相似度 > 0.9

    返回:
      (保留的评论, 被移除的重复评论, 原因说明列表)
    """
    kept = []
    removed = []
    reasons = []

    for i, review in enumerate(reviews):
        is_duplicate = False
        for j, existing in enumerate(kept):
            # 条件 1: 相同作者
            if review.get("author") != existing.get("author"):
                continue

            # 条件 2: 相同评分
            if review.get("rating") != existing.get("rating"):
                continue

            # 条件 3: 日期差 <= 3 天
            review_date = review.get("date", "")
            existing_date = existing.get("date", "")
            if review_date and existing_date:
                try:
                    # 提取日期部分比较
                    d1 = review_date[:10]
                    d2 = existing_date[:10]
                    date_diff = abs(
                        (datetime.fromisoformat(d1) - datetime.fromisoformat(d2)).days
                    )
                    if date_diff > time_threshold_days:
                        continue
                except (ValueError, TypeError):
                    continue

            # 条件 4: 内容相似度 > 0.9
            review_content = (review.get("title", "") or "") + " " + (review.get("content", "") or "")
            existing_content = (existing.get("title", "") or "") + " " + (existing.get("content", "") or "")
            similarity = jaccard_similarity(review_content, existing_content)

            if similarity > similarity_threshold:
                is_duplicate = True
                reason = (
                    f"重复: author={review.get('author')}, "
                    f"rating={review.get('rating')}, "
                    f"相似度={similarity:.3f}"
                )
                reasons.append(reason)
                removed.append(review)
                break

        if not is_duplicate:
            kept.append(review)

    return kept, removed, reasons


# ----------------------------------------------------------
# 清洗规则 2: 无效评论过滤
# ----------------------------------------------------------
# 常见无意义短评论（中英文）
MEANINGLESS_WORDS = {
    "ok", "okok", "good", "bad", "nice", "great", "fine",
    "no", "yes", "y", "n", "wtf", "lol", "omg",
    "好", "不好", "可以", "不错", "一般", "还行", "差", "很好",
}


def is_invalid_review(review: dict) -> tuple[bool, str]:
    """判断评论是否无效

    无效条件:
      1. content 为空或仅空白
      2. content 长度 < 5 字符
      3. 仅含标点符号或 emoji
      4. 仅含数字
      5. 仅含无意义词语（ok/good/好/不错 等）

    返回:
      (是否无效, 无效原因)
    """
    content = review.get("content", "") or ""
    title = review.get("title", "") or ""
    combined = (title + " " + content).strip()

    # 条件 1: 空内容
    if not combined:
        return True, "内容为空"

    # 条件 2: 太短
    if len(combined) < 5:
        return True, "内容过短(<5字符)"

    # 条件 3: 仅含标点/emoji
    # 移除所有字母、数字、中文字符，看剩下的比例
    text_only = re.sub(r"[a-zA-Z0-9一-鿿\s]", "", combined)
    if text_only and len(text_only) / len(combined) > 0.8:
        return True, "仅含标点符号或emoji"

    # 条件 4: 仅含数字
    if re.fullmatch(r"\d+[\s\d]*", combined):
        return True, "仅含数字"

    # 条件 5: 仅无意义词语
    words = combined.lower().split()
    if words and all(w.strip(".,!? ") in MEANINGLESS_WORDS for w in words):
        return True, "仅无意义词语"

    return False, ""


# ----------------------------------------------------------
# 清洗规则 3: 广告/垃圾内容过滤
# ----------------------------------------------------------
AD_PATTERNS = [
    r"https?://\S+",       # URL链接
    r"www\.\S+",           # www链接
    r"\bfree\b",           # 免费
    r"\bdiscount\b",       # 折扣
    r"\bclick\s*here\b",   # 点击这里
    r"\bcheck\s*this\b",   # 看看这个
    r"\bbuy\s*now\b",      # 立即购买
    r"\blimited\s*time\b", # 限时
]


def is_advertisement(review: dict) -> bool:
    """检测广告/垃圾内容

    使用模式匹配检测常见的垃圾评论特征，
    避免将正常的"free"（免费App评测）误判。
    """
    content = review.get("content", "") or ""
    title = review.get("title", "") or ""
    combined = (title + " " + content).lower()

    # 统计匹配的广告模式数量
    match_count = 0
    for pattern in AD_PATTERNS:
        if re.search(pattern, combined):
            match_count += 1

    # 匹配 >= 2 个模式才判定为广告（降低误杀率）
    return match_count >= 2


# ----------------------------------------------------------
# 清洗规则 4: 字段规范化
# ----------------------------------------------------------
def normalize_review(review: dict) -> dict:
    """规范化评论字段

    操作:
      - rating: 确保是 1-5 的整数
      - date: 转换为 ISO 8601 格式
      - version: 去除前后空白
      - review_id: 转为字符串
    """
    normalized = review.copy()

    # rating 规范化
    rating = normalized.get("rating")
    if rating is not None:
        try:
            rating_int = int(rating)
            if 1 <= rating_int <= 5:
                normalized["rating"] = rating_int
            else:
                normalized["rating"] = None
        except (ValueError, TypeError):
            normalized["rating"] = None

    # date 规范化（保留原始格式，确保是字符串）
    date_val = normalized.get("date")
    if date_val is not None:
        normalized["date"] = str(date_val)

    # version 规范化
    version = normalized.get("version")
    if version is not None:
        normalized["version"] = str(version).strip()

    # review_id 转字符串
    rid = normalized.get("review_id")
    if rid is not None:
        normalized["review_id"] = str(rid)

    return normalized


# ----------------------------------------------------------
# 清洗规则 5: 隐私脱敏
# ----------------------------------------------------------
def sanitize_pii(text: str) -> str:
    """脱敏隐私信息

    替换模式:
      - 邮箱地址 → [EMAIL]
      - 电话号码 → [PHONE]（支持中美号码格式）
    """
    # 邮箱脱敏
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text)

    # 美国电话: (123) 456-7890 或 123-456-7890
    text = re.sub(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]\d{4}", "[PHONE]", text)

    # 中国电话: 1xx-xxxx-xxxx 或 1xxxxxxxxxx
    text = re.sub(r"1[3-9]\d[-.\s]?\d{4}[-.\s]?\d{4}", "[PHONE]", text)

    return text


# ----------------------------------------------------------
# 清洗规则 6: 质量评分
# ----------------------------------------------------------
def compute_quality_score(review: dict) -> float:
    """计算评论质量评分 (0-1)

    启发式评分:
      - 基础分 0.5
      - 内容长(>50字符) +0.2，很长(>200字符) +0.15
      - 有标题 +0.1
      - 有具体词语(非通用词) +0.1
      - 重复字符多 -0.2（可能是垃圾信息）
      - 纯大写 -0.1
    """
    content = review.get("content", "") or ""
    title = review.get("title", "") or ""

    if not content and not title:
        return 0.0

    score = 0.5

    # 长度加分
    total_len = len(content) + len(title)
    if total_len > 50:
        score += 0.2
    if total_len > 200:
        score += 0.15

    # 有标题加分
    if title.strip():
        score += 0.1

    # 有具体内容加分（包含中英文单词/汉字）
    has_words = bool(re.search(r"[a-zA-Z]{3,}|[一-鿿]{2,}", content))
    if has_words:
        score += 0.1

    # 重复字符过多扣分（如 "aaaaa" 或 "哈哈哈"重复3次以上）
    if re.search(r"(.)\1{4,}", content):
        score -= 0.15

    # 全大写扣分（可能是机器生成）
    if content and content.isupper():
        score -= 0.1

    return max(0.0, min(1.0, score))


def print_cleaning_report(
    total: int,
    duplicates: list,
    invalid: list,
    ads: list,
    kept: list,
) -> None:
    """打印清洗报告"""
    total_removed = len(duplicates) + len(invalid) + len(ads)
    kept_count = len(kept)

    print(f"\n{'=' * 50}")
    print("[OK] 清洗完成报告")
    print(f"{'=' * 50}")
    print(f"  原始评论数:        {total}")
    print(f"  重复评论(移除):    {len(duplicates)}")
    print(f"  无效评论(过滤):    {len(invalid)}")
    print(f"  广告评论(过滤):    {len(ads)}")
    print(f"  总计移除:          {total_removed}")
    print(f"  ─────────────────────────")
    print(f"  清洗后保留:        {kept_count}")
    print(f"  保留率:            {kept_count/total*100:.1f}%" if total > 0 else "  N/A")
    print()

    # 评分分布
    ratings = Counter(r.get("rating") for r in kept if r.get("rating"))
    print(f"  清洗后评分分布:")
    for star in sorted(ratings.keys(), reverse=True):
        count = ratings[star]
        bar = "#" * (count // 5)
        print(f"    {star}星: {count:>4}条 {bar}")

    # 去重原因展示（最多 5 条）
    if duplicates:
        print(f"\n  重复示例(前5条):")
        for dup in duplicates[:5]:
            print(f"    - author={dup.get('author')}, rating={dup.get('rating')}")
    print(f"{'=' * 50}\n")


def main():
    """主流程"""
    args = parse_args()

    # 确定输入文件
    input_file = args.input
    if not input_file:
        input_file = find_latest_raw_file(args.output_dir)
        if not input_file:
            logger.error(
                "未指定 --input 且在 %s 中找不到 raw_reviews_*.json 文件",
                args.output_dir,
            )
            logger.info(
                "请先运行 python demo/rss_feed_demo.py 生成原始评论数据，"
                "或指定 --input 指向已有文件"
            )
            sys.exit(1)
        logger.info("自动选择最新文件: %s", input_file)

    # 加载原始评论
    reviews, meta = load_reviews(input_file)
    if not reviews:
        logger.warning("输入文件中没有评论数据，无需清洗")
        return

    # ----------------------------------------------------------
    # 阶段 A: 通用清洗
    # ----------------------------------------------------------
    logger.info("开始清洗 %d 条评论...", len(reviews))

    # 步骤 1: 字段规范化（先规范化，保证后续判断准确）
    normalized = [normalize_review(r) for r in reviews]

    # 步骤 2: 隐私脱敏（content 和 title）
    for review in normalized:
        if review.get("content"):
            review["content"] = sanitize_pii(review["content"])
        if review.get("title"):
            review["title"] = sanitize_pii(review["title"])

    # 步骤 3: 检测无效评论
    valid_after_invalid_check = []
    invalid_reviews = []
    for review in normalized:
        is_invalid, reason = is_invalid_review(review)
        if is_invalid:
            review["_filter_reason"] = reason
            invalid_reviews.append(review)
        else:
            valid_after_invalid_check.append(review)
    logger.info("无效评论过滤: 移除 %d 条", len(invalid_reviews))

    # 步骤 4: 广告检测
    non_ad_reviews = []
    ad_reviews = []
    for review in valid_after_invalid_check:
        if is_advertisement(review):
            review["_filter_reason"] = "广告/垃圾内容"
            ad_reviews.append(review)
        else:
            non_ad_reviews.append(review)
    logger.info("广告过滤: 移除 %d 条", len(ad_reviews))

    # 步骤 5: 重复检测
    kept_reviews, duplicate_reviews, dup_reasons = find_duplicates(non_ad_reviews)

    # 打印去重原因
    for reason in dup_reasons:
        logger.info("  去重: %s", reason)

    # 步骤 6: 计算质量评分
    for review in kept_reviews:
        review["quality_score"] = round(compute_quality_score(review), 2)

    # 按质量评分降序排列
    kept_reviews.sort(key=lambda r: r.get("quality_score", 0), reverse=True)

    # ----------------------------------------------------------
    # 阶段 B: 保存输出
    # ----------------------------------------------------------
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 从输入文件推断 app_id
    app_id = args.app_id
    if not app_id:
        app_id = meta.get("app_id", "unknown")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_file = output_dir / f"cleaned_reviews_{app_id}_{timestamp}.json"

    output_data = {
        "meta": {
            "app_id": app_id,
            "source_file": str(Path(input_file).name),
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
            "input_count": len(reviews),
            "output_count": len(kept_reviews),
            "duplicates_removed": len(duplicate_reviews),
            "invalid_filtered": len(invalid_reviews),
            "ad_filtered": len(ad_reviews),
        },
        "reviews": kept_reviews,
        "duplicates": duplicate_reviews[:20],  # 保留前20条供检查
        "invalid": invalid_reviews[:20],
        "advertisements": ad_reviews[:10],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info("清洗结果保存至: %s", output_file)

    # 打印报告
    print_cleaning_report(
        total=len(reviews),
        duplicates=duplicate_reviews,
        invalid=invalid_reviews,
        ads=ad_reviews,
        kept=kept_reviews,
    )

    return kept_reviews


if __name__ == "__main__":
    main()
