"""目标解析（LLM 驱动）

将用户的自然语言 goal 解析为结构化筛选条件。
"""
from app.llm.factory import create_llm


async def parse_goal(goal: str) -> dict:
    """解析分析目标，返回 parsed_scope"""
    if not goal:
        return {"focus_keywords": [], "focus_ratings": []}

    llm = create_llm()
    prompt = (
        "你是一个 App Store 评论分析目标解析器。\n"
        "从用户输入的分析目标中提取关键维度，输出 JSON：\n"
        '{"focus_keywords": [...], "focus_ratings": [1,5], "analysis_focus": "..."}\n'
        f"分析目标: {goal}"
    )
    try:
        result = await llm.chat([{"role": "user", "content": prompt}])
        import json
        parsed = json.loads(result)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {"focus_keywords": [], "focus_ratings": []}
