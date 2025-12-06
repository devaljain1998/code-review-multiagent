"""Base provider protocol and factory function."""

from typing import AsyncIterator, Protocol, runtime_checkable

from ..models import Message, ModelResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract interface for LLM providers.

    This protocol enables swapping between different LLM backends
    (e.g., direct Bedrock API, Claude Agent SDK) without changing
    the agent implementation code.
    """

    async def invoke(
        self,
        messages: list[Message],
        system_prompt: str,
        model_tier: str = "fast",
    ) -> ModelResponse:
        """Invoke the model and return complete response.

        Args:
            messages: Conversation messages
            system_prompt: System prompt for the model
            model_tier: "fast" (Haiku) or "smart" (Sonnet)

        Returns:
            ModelResponse with the generated content
        """
        ...

    async def stream(
        self,
        messages: list[Message],
        system_prompt: str,
        model_tier: str = "fast",
    ) -> AsyncIterator[str]:
        """Stream response chunks for real-time output.

        Args:
            messages: Conversation messages
            system_prompt: System prompt for the model
            model_tier: "fast" (Haiku) or "smart" (Sonnet)

        Yields:
            String chunks of the response
        """
        ...


def get_provider(provider_type: str = "bedrock") -> LLMProvider:
    """Factory function to get a provider instance.

    Args:
        provider_type: Type of provider - "bedrock" or "agent-sdk"

    Returns:
        An instance implementing LLMProvider protocol

    Raises:
        ValueError: If provider_type is unknown
    """
    if provider_type == "bedrock":
        from .bedrock import BedrockProvider

        return BedrockProvider()
    elif provider_type == "agent-sdk":
        from .agent_sdk import AgentSDKProvider

        return AgentSDKProvider()
    else:
        raise ValueError(
            f"Unknown provider: {provider_type}. "
            f"Available providers: bedrock, agent-sdk"
        )
