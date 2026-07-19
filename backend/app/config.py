"""环境配置 + LLM 全局实例"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/app_reviews.db")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

_llm = None


def get_llm():
    """返回全局 ChatDeepSeek 实例（单例），无 API Key 时返回 Mock"""
    global _llm
    if _llm is not None:
        return _llm

    if not DEEPSEEK_API_KEY:
        from app.llm.mock import MockChatDeepSeek
        _llm = MockChatDeepSeek()
    else:
        from langchain_deepseek import ChatDeepSeek
        _llm = ChatDeepSeek(
            model="deepseek-v4-flash",
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.1,
            timeout=60,
            model_kwargs={"tool_choice": "auto"},
            # deepseek-v4-flash 默认开启思考模式，与 tool_choice/structured_output 不兼容
            # 关闭思考模式以支持 with_structured_output（AI 清洗等场景）
            extra_body={"thinking": {"type": "disabled"}},
        )
    return _llm
