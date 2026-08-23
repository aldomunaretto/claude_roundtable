"""Anthropic Claude API client for making LLM requests."""

import asyncio
from typing import List, Dict, Any, Optional, Tuple

from anthropic import AsyncAnthropic

from .config import ANTHROPIC_API_KEY, MODEL_EFFORT

MAX_TOKENS = 4096

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    effort: str = MODEL_EFFORT,
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via the Anthropic API.

    Args:
        model: Claude model identifier (e.g., "claude-opus-5")
        messages: List of message dicts with 'role' and 'content'
        effort: Effort level ("low", "medium", "high", "xhigh", "max")
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content', or None if failed
    """
    try:
        response = await _client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            output_config={"effort": effort},
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
) -> List[Tuple[str, Optional[Dict[str, Any]]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of Claude model identifiers (may contain duplicates,
            e.g. several council seats sharing the same model)
        messages: List of message dicts to send to each model

    Returns:
        List of (model identifier, response dict or None) pairs, in the same
        order as `models`
    """
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return list(zip(models, responses))
