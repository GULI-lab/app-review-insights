"""LLM 抽象基类"""
from abc import ABC, abstractmethod
from typing import Type
from pydantic import BaseModel


class LLMClient(ABC):
    """所有 LLM Provider 的统一接口"""

    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> str:
        """纯文本对话"""
        pass

    @abstractmethod
    async def chat_structured(self, messages: list, response_model: Type[BaseModel], **kwargs) -> BaseModel:
        """结构化输出"""
        pass
