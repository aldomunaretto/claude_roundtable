"""Anthropic Claude API client for making LLM requests."""

import asyncio
from typing import List, Dict, Any, Optional, Tuple

from anthropic import AsyncAnthropic

from .config import ANTHROPIC_API_KEY, MODEL_EFFORT, FALLBACK_MODELS

MAX_TOKENS = 4096

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    effort: Optional[str] = MODEL_EFFORT,
    system: Optional[str] = None,
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via the Anthropic API.

    Args:
        model: Claude model identifier (e.g., "claude-opus-5")
        messages: List of message dicts with 'role' and 'content'
        effort: Effort level ("low", "medium", "high", "xhigh", "max"), or
            None to omit it (required for models that don't support it, e.g. Haiku)
        system: Optional system prompt, e.g. to give the model a persona
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content', or None if failed
    """
    extra_kwargs = {}
    if effort:
        extra_kwargs["output_config"] = {"effort": effort}
    if system:
        extra_kwargs["system"] = system

    try:
        response = await _client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            timeout=timeout,
            **extra_kwargs,
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
    messages: List[Dict[str, str]],
    systems: Optional[List[Optional[str]]] = None,
    efforts: Optional[List[Optional[str]]] = None,
) -> List[Tuple[str, Optional[Dict[str, Any]]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of Claude model identifiers (may contain duplicates,
            e.g. several council seats sharing the same model)
        messages: List of message dicts to send to each model
        systems: Optional list of per-seat system prompts, aligned with `models`
            (e.g. one persona per council seat). Defaults to no system prompt.
        efforts: Optional list of per-seat effort levels, aligned with `models`.
            Defaults to MODEL_EFFORT for every seat (previous behavior).

    Returns:
        List of (model identifier, response dict or None) pairs, in the same
        order as `models`
    """
    if systems is None:
        systems = [None] * len(models)
    if efforts is None:
        efforts = [MODEL_EFFORT] * len(models)

    tasks = [
        query_model(model, messages, effort=effort, system=system)
        for model, system, effort in zip(models, systems, efforts)
    ]
    responses = await asyncio.gather(*tasks)
    return list(zip(models, responses))


async def list_available_models() -> List[Dict[str, str]]:
    """
    List Claude models available to this API key, for the role editor's model
    dropdown.

    Returns:
        List of {'id', 'display_name'} dicts. Falls back to FALLBACK_MODELS on
        any error (invalid API key, network issue, etc.) so the dropdown is
        never left empty.
    """
    try:
        models = []
        async for m in _client.models.list(limit=100):
            models.append({"id": m.id, "display_name": m.display_name})
            if len(models) >= 100:
                break
        return models or FALLBACK_MODELS
    except Exception as e:
        print(f"Error listing models: {e}")
        return FALLBACK_MODELS
