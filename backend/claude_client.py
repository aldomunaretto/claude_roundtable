"""Anthropic Claude API client for making LLM requests."""

import asyncio
from typing import List, Dict, Any, Optional

from anthropic import AsyncAnthropic

from .config import ANTHROPIC_API_KEY

MAX_TOKENS = 4096

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via the Anthropic API.

    Args:
        model: Claude model identifier (e.g., "claude-sonnet-4-5-20250929")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content', or None if failed
    """
    try:
        response = await _client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            timeout=timeout,
        )

        content = "".join(
            block.text for block in response.content if block.type == "text"
        )

        return {"content": content}

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of Claude model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
