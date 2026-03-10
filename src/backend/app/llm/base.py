from abc import ABC, abstractmethod
from .types import Message, LLMResponse


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[Message], max_tokens: int = 2000) -> LLMResponse:
        ...

    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
