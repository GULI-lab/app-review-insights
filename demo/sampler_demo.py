"""
============================================================
演示 4: 分层抽样 + 高危关键词扫描
============================================================

功能:
  对清洗后的评论执行以下策略（模拟 LLM 上下文管理）:
    1. 高危关键词扫描 → 强制保留（优先级最高）
    2. 基于目标关键词的相关性评分
    3. 按相关性分三层抽样（高80% / 中15% / 低5%）
    4. 确保评分分布的代表性

设计背景(设计文档):
  当评论数量超出 LLM 单次窗口时，需要采样。
  抽样策略兼顾:
  - 覆盖关键问题（高危词强制保留）
  - 目标相关性（与用户设定的分析目标匹配）
  - 统计代表性（各评分层都有样本）

用法:
  # 对清洗后的评论执行抽样
  python demo/sampler_demo.py --input demo/data/cleaned_reviews_*.json

  # 指定目标样本量和自定义关键词
  python demo/sampler_demo.py --input demo/data/cleaned_reviews_*.json --target 100
"""

import argparse
import json
import logging
import random
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
logger = logging.getLogger("sampler_demo")


# ----------------------------------------------------------
# 默认高危关键词列表
# ----------------------------------------------------------
# 这些关键词表示用户遇到了严重影响使用的问题。
# 匹配任意一个即强制保留到待分析集。
# 来源: 设计文档 "异常关键词预筛选" 章节
DEFAULT_HIGH_RISK_KEYWORDS = [
    # 英文关键词
    "crash", "crashes", "crashed",
    "bug", "bugs",
    "refund",
    "broken",
    "error", "errors",
    "can't", "cannot",
    "freeze", "freezes", "frozen",
    "lost", "lose",
    "subscription",
    "paid", "charge", "charges", "billing",
    "glitch", "glitches",
    "unusable",
    "waste",
    "not working", "doesn't work", "dont work",
    # 中文关键词
    "闪退", "崩溃", "卡死",
    "付费", "扣费", "退款",
    "bug", "错误",
    "无法使用", "用不了",
    "垃圾", "骗人",
]

# 默认目标关键词（用于相关性评分）
# 当用户没有明确分析目标时使用通用关键词
DEFAULT_TARGET_KEYWORDS = [
    # 用户体验
    "interface", "ui", "design", "layout", "navigation",
    "slow", "fast", "performance", "loading", "lag",
    "界面", "设计", "卡顿", "流畅",
    # 功能需求
    "feature", "need", "want", "please", "would like",
    "希望", "建议", "能不能", "增加", "添加",
    # 订阅/付费
    "price", "cost", "expensive", "cheap", "free", "trial",
    "价格", "贵", "便宜", "免费", "订阅",
    # 内容
    "workout", "exercise", "training", "plan", "program",
    "课程", "训练", "运动", "教练",
]


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="评论分层抽样 - 模拟LLM上下文管理")
    parser.add_argument(
        "--input",
        required=True,
        help="清洗后的评论 JSON 文件路径",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=200,
        help="目标样本数量，默认 200（设计文档中指定的采样上限）",
    )
    parser.add_argument(
        "--keywords-file",
        help="自定义高危关键词文件（每行一个）",
    )
    parser.add_argument(
        "--output-dir",
        default="demo/data",
        help="输出目录，默认: demo/data",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（确保结果可复现），默认 42",
    )
    return parser.parse_args()


def load_high_risk_keywords(filepath: str | None) -> list[str]:
    """加载高危关键词

    支持从外部文件加载，也提供默认列表。
    """
    if filepath:
        path = Path(filepath)
        if not path.exists():
            logger.warning("关键词文件不存在: %s，使用默认列表", filepath)
            return DEFAULT_HIGH_RISK_KEYWORDS
        with open(path, "r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip()]
        logger.info("加载了 %d 个自定义高危关键词", len(keywords))
        return keywords

    return DEFAULT_HIGH_RISK_KEYWORDS


def build_risk_pattern(keywords: list[str]) -> re.Pattern:
    """将关键词列表编译为正则表达式

    按长度降序排列关键词，优先匹配长词组（避免"not working"
    被"working"部分匹配）。
    """
    # 按长度降序排列，避免短词干扰长词匹配
    sorted_kw = sorted(keywords, key=len, reverse=True)
    # 转义特殊字符，用单词边界限制
    escaped = [re.escape(kw) for kw in sorted_kw]
    pattern = r"(?:" + "|".join(escaped) + r")"
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


def scan_high_risk(
    reviews: list[dict],
    risk_pattern: re.Pattern,
    max_capture_ratio: float = 0.3,
) -> tuple[list[dict], list[dict]]:
    """扫描评论中的高危关键词

    高危关键词匹配的评论会被强制保留到待分析集。
    防止因随机抽样遗漏关键 Bug 反馈。

    参数:
      reviews: 输入评论列表
      risk_pattern: 编译后的高危关键词正则
      max_capture_ratio: 高风险评论最大占比（防止过度偏向异常）

    返回:
      (高风险评论列表, 普通评论列表)
    """
    high_risk = []
    normal = []
    max_capture = int(len(reviews) * max_capture_ratio)

    for review in reviews:
        content = (review.get("content") or "") + " " + (review.get("title") or "")
        if risk_pattern.search(content):
            if len(high_risk) < max_capture:
                # 标记匹配到的关键词（便于调试）
                matches = risk_pattern.findall(content)
                review["_matched_risk_keywords"] = list(set(matches))[:5]
                high_risk.append(review)
            else:
                # 超过上限的也放回普通池
                normal.append(review)
        else:
            normal.append(review)

    if high_risk:
        logger.info(
            "高危关键词扫描: 捕获 %d 条（上限 %d 条）",
            len(high_risk),
            max_capture,
        )

    return high_risk, normal


def compute_relevance_score(
    review: dict,
    target_keywords: list[str],
) -> float:
    """计算评论与目标关键词的相关性评分 (0-1)

    基于简单关键词出现频率（确定性方法，不涉及 LLM）。

    评分方法:
      - 标题中每匹配一个关键词 +0.2
      - 内容中每匹配一个关键词 +0.1
      - 重复词不计分（只计唯一匹配）
      - 超过 1.0 的上限为 1.0
    """
    title = (review.get("title") or "").lower()
    content = (review.get("content") or "").lower()
    combined = title + " " + content

    # 统计匹配到的唯一关键词数量
    matched = set()
    for kw in target_keywords:
        if kw.lower() in combined:
            matched.add(kw.lower())

    if not matched:
        return 0.0

    # 加权: 标题匹配权重更高
    title_matches = sum(1 for kw in matched if kw in title)
    content_matches = len(matched) - title_matches

    score = title_matches * 0.2 + content_matches * 0.1
    return min(1.0, score)


def stratified_sample(
    high_risk: list[dict],
    normal: list[dict],
    target_count: int,
    target_keywords: list[str],
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """分层抽样

    分层策略（设计文档）:
      - 高风险评论: 100% 保留（但已在上一步筛选）
      - 高相关性(>0.7): 保留 80%
      - 中相关性(0.3-0.7): 保留 15%
      - 低相关性(<0.3): 保留 5%

    最终限制: max(50, min(target_count, N))

    参数:
      high_risk: 高风险评论（已保留）
      normal: 其余评论
      target_count: 目标样本数
      seed: 随机种子

    返回:
      (样本列表, 被丢弃的评论列表)
    """
    random.seed(seed)

    # 计算每层相关性
    stratified = {"high": [], "medium": [], "low": []}
    for review in normal:
        score = compute_relevance_score(review, target_keywords)
        review["_relevance_score"] = round(score, 3)
        if score > 0.7:
            stratified["high"].append(review)
        elif score >= 0.3:
            stratified["medium"].append(review)
        else:
            stratified["low"].append(review)

    # 计算各层保留比例和数量
    remaining = target_count - len(high_risk)
    if remaining <= 0:
        return high_risk[:target_count], normal

    # 确保各层不空时至少保留1条
    def sample_layer(layer: list[dict], ratio: float, max_count: int) -> tuple[list[dict], list[dict]]:
        if not layer:
            return [], []
        target = max(1, min(len(layer), int(len(layer) * ratio), max_count))
        sampled = random.sample(layer, min(target, len(layer)))
        dropped = [r for r in layer if r not in sampled]
        return sampled, dropped

    high_layer, high_dropped = sample_layer(stratified["high"], 0.8, remaining)
    remaining -= len(high_layer)

    medium_layer, medium_dropped = sample_layer(stratified["medium"], 0.15, remaining)
    remaining -= len(medium_layer)

    low_layer, low_dropped = sample_layer(stratified["low"], 0.05, remaining)
    remaining -= len(low_layer)

    # 如果还没满 target，从已丢弃中尽可能补充
    not_sampled = high_dropped + medium_dropped + low_dropped
    if remaining > 0 and not_sampled:
        extra = random.sample(not_sampled, min(remaining, len(not_sampled)))
        sampled_all = high_risk + high_layer + medium_layer + low_layer + extra
    else:
        sampled_all = high_risk + high_layer + medium_layer + low_layer

    # 最终限制在 [50, target_count] 范围
    min_count = max(50, min(target_count, len(sampled_all)))
    final_sample = sampled_all[:min_count]

    # 被丢弃的 = 不在 final_sample 中的
    dropped = [r for r in normal if r not in final_sample]

    # 收集分层统计信息
    logger.info(
        "分层抽样: high=%d(80%%目标), medium=%d(15%%), low=%d(5%%)",
        len(high_layer), len(medium_layer), len(low_layer),
    )

    return final_sample, dropped


def print_sampling_report(
    input_count: int,
    final_sample: list[dict],
    high_risk: list[dict],
    dropped: list[dict],
) -> None:
    """打印抽样报告"""
    print(f"\n{'=' * 50}")
    print("[OK] 抽样完成报告")
    print(f"{'=' * 50}")
    print(f"  输入评论数:   {input_count}")
    print(f"  高风险捕获:   {len(high_risk)}（强制保留）")
    print(f"  抽样输出:     {len(final_sample)}")
    print(f"  丢弃评论:     {len(dropped)}")
    print(f"  抽样率:       {len(final_sample)/input_count*100:.1f}%")

    if not final_sample:
        print(f"{'=' * 50}\n")
        return

    # 评分分布
    before = Counter()
    after = Counter()
    for r in (final_sample + dropped):
        if r.get("rating"):
            before[r["rating"]] += 1
    for r in final_sample:
        if r.get("rating"):
            after[r["rating"]] += 1

    # 评分分布对比基数修正
    total_count = len(final_sample) + len(dropped) if dropped else len(final_sample)
    print(f"\n  评分分布对比(前→后):")
    for star in sorted(set(list(before.keys()) + list(after.keys())), reverse=True):
        b = before.get(star, 0)
        a = after.get(star, 0)
        b_pct = b / total_count * 100 if total_count else 0
        a_pct = a / len(final_sample) * 100 if final_sample else 0
        bar = "#" * (a // 3)
        print(f"    {star}星: {b}条({b_pct:.0f}%) → {a}条({a_pct:.0f}%) {bar}")

    # 高风险关键词分布
    if high_risk:
        all_keywords = []
        for r in high_risk:
            all_keywords.extend(r.get("_matched_risk_keywords", []))
        keyword_counts = Counter(all_keywords).most_common(10)
        print(f"\n  高频风险关键词(Top10):")
        for kw, cnt in keyword_counts:
            print(f"    [{kw}] × {cnt}")

    # 相关性分布
    relevance_scores = [
        r.get("_relevance_score", 0)
        for r in final_sample
        if "_relevance_score" in r
    ]
    if relevance_scores:
        avg_score = sum(relevance_scores) / len(relevance_scores)
        print(f"\n  平均相关性评分: {avg_score:.3f}")

    print(f"{'=' * 50}\n")


def main():
    """主流程"""
    args = parse_args()

    # ----------------------------------------------------------
    # 步骤 1: 加载数据
    # ----------------------------------------------------------
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("文件不存在: %s", args.input)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    reviews = data.get("reviews", [])
    meta = data.get("meta", {})

    if not reviews:
        logger.warning("输入文件中没有评论数据")
        return

    logger.info("加载 %d 条评论", len(reviews))

    # ----------------------------------------------------------
    # 步骤 2: 加载关键词
    # ----------------------------------------------------------
    high_risk_keywords = load_high_risk_keywords(args.keywords_file)
    risk_pattern = build_risk_pattern(high_risk_keywords)

    # ----------------------------------------------------------
    # 步骤 3: 高危关键词扫描
    # ----------------------------------------------------------
    logger.info("执行高危关键词扫描（%d 个关键词）...", len(high_risk_keywords))
    high_risk, normal_reviews = scan_high_risk(reviews, risk_pattern)
    logger.info("高风险评论: %d 条", len(high_risk))

    # ----------------------------------------------------------
    # 步骤 4: 分层抽样
    # ----------------------------------------------------------
    target = max(50, args.target)  # 下限 50 条（设计文档规定）
    logger.info("目标样本数: %d 条", target)

    sample, dropped = stratified_sample(
        high_risk=high_risk,
        normal=normal_reviews,
        target_count=target,
        target_keywords=DEFAULT_TARGET_KEYWORDS,
        seed=args.seed,
    )

    # ----------------------------------------------------------
    # 步骤 5: 确保评分覆盖面
    # ----------------------------------------------------------
    # 检查 1-5 星是否都有代表，如果某星级被完全丢弃则补充
    sampled_ratings = set(r.get("rating") for r in sample if r.get("rating"))
    all_ratings = set(r.get("rating") for r in reviews if r.get("rating"))
    missing_ratings = all_ratings - sampled_ratings

    if missing_ratings:
        logger.info("补充缺失的评分层级: %s", missing_ratings)
        for missing in missing_ratings:
            candidates = [r for r in dropped if r.get("rating") == missing]
            if candidates:
                # 从该评分层选一条评论加入样本
                chosen = random.choice(candidates)
                sample.append(chosen)
                dropped.remove(chosen)
                logger.info("  补充 1 条 %d 星评论", missing)

    # ----------------------------------------------------------
    # 步骤 6: 保存输出
    # ----------------------------------------------------------
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    app_id = meta.get("app_id", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_file = output_dir / f"sampled_reviews_{app_id}_{timestamp}.json"

    # 准备输出
    high_risk_output = [
        {
            "review_id": r.get("review_id"),
            "rating": r.get("rating"),
            "content_preview": (r.get("content") or "")[:80],
            "matched_keywords": r.get("_matched_risk_keywords", []),
        }
        for r in high_risk
    ]

    output = {
        "meta": {
            "source_file": input_path.name,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
            "input_count": len(reviews),
            "output_count": len(sample),
            "target_count": target,
            "high_risk_captured": len(high_risk),
            "strata": {
                "high_relevance": sum(
                    1 for r in sample if r.get("_relevance_score", 0) > 0.7
                ),
                "medium_relevance": sum(
                    1 for r in sample if 0.3 <= r.get("_relevance_score", 0) <= 0.7
                ),
                "low_relevance": sum(
                    1 for r in sample if r.get("_relevance_score", 0) < 0.3
                ),
            },
        },
        "reviews": sample,
        "high_risk_reviews": high_risk_output,
        "dropped_count": len(dropped),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("抽样结果保存至: %s", output_file)

    # 打印报告
    print_sampling_report(
        input_count=len(reviews),
        final_sample=sample,
        high_risk=high_risk,
        dropped=dropped,
    )

    return sample


if __name__ == "__main__":
    main()
