"""LLM 降级实现：API Key 缺失时返回空结构化结果"""

from typing import Any, Type
from pydantic import BaseModel
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import AIMessage


class MockChain:
    """模拟 Chain，返回对应 Pydantic 模型的空实例"""

    def __init__(self, schema: Type[BaseModel]):
        self.schema = schema

    async def ainvoke(self, inputs: dict) -> BaseModel:
        return self.schema()


class MockChatDeepSeek(ChatDeepSeek):
    """当未配置 API Key 时使用，所有调用返回空结果"""

    def __init__(self):
        super().__init__(
            model="deepseek-v4-flash",
            api_key="sk-mock",
            base_url="https://api.deepseek.com/v1",
        )

    async def ainvoke(self, *args, **kwargs) -> AIMessage:
        return AIMessage(content="{}")

    def with_structured_output(self, schema: Type[BaseModel], **kwargs) -> MockChain:
        return MockChain(schema)
