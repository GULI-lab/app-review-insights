"""目标解析（LLM 驱动）

将用户的自然语言 goal 解析为结构化筛选条件。
此文件已不再使用（pipeline.py 内联实现），保留以兼容旧引用。
"""
from app.config import get_llm


async def parse_goal(goal: str) -> dict:
    """解析分析目标，返回 parsed_scope"""
    if not goal:
        return {"focus_keywords": [], "focus_ratings": []}

    llm = get_llm()
    from langchain_core.prompts import ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个 App Store 评论分析目标解析器。从用户输入的分析目标中提取关键维度，输出 JSON。"),
        ("human", "分析目标: {goal}"),
    ])
    try:
        result = await (prompt | llm).ainvoke({"goal": goal})
        import json
        content = result.content if hasattr(result, 'content') else str(result)
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {"focus_keywords": [], "focus_ratings": []}
