"""AWS Bedrock provider implementation."""

import asyncio
import os
from typing import AsyncIterator

import boto3
from botocore.config import Config

from ..models import Message, ModelResponse


class BedrockProvider:
    """AWS Bedrock provider using the Converse API.

    Uses Claude models via AWS Bedrock:
    - fast tier: Claude Haiku (cost-effective for sub-agents)
    - smart tier: Claude Sonnet (more capable for orchestration)
    """

    MODEL_MAP = {
        "fast": "us.anthropic.claude-haiku-4-5-20251001-v1:0",   # Haiku 4.5 (inference profile)
        "smart": "us.anthropic.claude-sonnet-4-5-20250929-v1:0", # Sonnet 4.5 (inference profile)
    }

    def __init__(
        self,
        region: str | None = None,
        profile: str | None = None,
    ):
        """Initialize the Bedrock provider.

        Args:
            region: AWS region (defaults to AWS_REGION env var or us-west-2)
            profile: AWS profile name (defaults to AWS_PROFILE env var)
        """
        self.region = region or os.getenv("AWS_REGION", "us-west-2")
        self.profile = profile or os.getenv("AWS_PROFILE")

        # Configure boto3 with retries
        config = Config(
            region_name=self.region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        session_kwargs = {}
        if self.profile:
            session_kwargs["profile_name"] = self.profile

        session = boto3.Session(**session_kwargs)
        self.client = session.client("bedrock-runtime", config=config)

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Convert Message objects to Bedrock format."""
        return [
            {
                "role": msg.role,
                "content": [{"text": msg.content}],
            }
            for msg in messages
        ]

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
        model_id = self.MODEL_MAP.get(model_tier)
        if not model_id:
            raise ValueError(f"Unknown model tier: {model_tier}")

        # Run synchronous boto3 call in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=self._format_messages(messages),
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.3,
                },
            ),
        )

        content = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})

        return ModelResponse(
            content=content,
            model_id=model_id,
            usage={
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
            },
        )

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
        model_id = self.MODEL_MAP.get(model_tier)
        if not model_id:
            raise ValueError(f"Unknown model tier: {model_tier}")

        # Run synchronous boto3 call in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.converse_stream(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=self._format_messages(messages),
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.3,
                },
            ),
        )

        # Process the event stream
        stream = response.get("stream")
        if stream:
            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "text" in delta:
                        yield delta["text"]
