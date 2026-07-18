"""LLM 工厂：从配置创建 LLM 实例"""
import json
import logging
from typing import Type
from pydantic import BaseModel
from openai import AsyncOpenAI

from app import config
from app.llm.base import LLMClient

logger = logging.getLogger("llm_factory")


class DeepSeekClient(LLMClient):
    """DeepSeek LLM 适配器"""

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
        SYSTEM_JSON_PROMPT = (
            f"\n请以 JSON 格式输出，严格遵循以下 schema: {json.dumps(response_model.model_json_schema(), ensure_ascii=False)}"
        )
        msgs = messages.copy()
        msgs.append({"role": "system", "content": SYSTEM_JSON_PROMPT})
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=msgs,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = resp.choices[0].message.content or "{}"
        return response_model.model_validate_json(raw)


class MockClient(LLMClient):
    """Mock LLM（无 API Key 时使用，返回空结果）"""

    async def chat(self, messages: list, **kwargs) -> str:
        return "LLM 暂不可用，请在 .env 中配置 DEEPSEEK_API_KEY"

    async def chat_structured(self, messages: list, response_model: Type[BaseModel], **kwargs) -> BaseModel:
        # 返回空结构
        return response_model()


def create_llm() -> LLMClient:
    """根据配置创建 LLM 客户端"""
    if config.LLM_PROVIDER == "deepseek":
        if config.DEEPSEEK_API_KEY and config.DEEPSEEK_API_KEY != "sk-your-key-here":
            return DeepSeekClient()
        logger.warning("DEEPSEEK_API_KEY 未配置，使用 Mock LLM")
        return MockClient()
    raise ValueError(f"不支持的 LLM Provider: {config.LLM_PROVIDER}")
