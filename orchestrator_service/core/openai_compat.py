"""OpenAI parameter compatibility helper.

Modern OpenAI models (gpt-5 family, o1/o3/o4 series) reject the legacy
`max_tokens` parameter and require `max_completion_tokens` instead. The gpt-5
family also rejects any `temperature` other than the default (1).

This module centralizes the logic so call sites can build chat-completion
kwargs without hardcoding model-specific assumptions.

See: openspec/changes/openai-param-compat/spec.md
"""

from typing import Any, Optional

# Prefixes of OpenAI model families that use the modern Chat Completions API
# contract (max_completion_tokens, fixed temperature=1).
_MODERN_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def is_modern_openai_model(model: str) -> bool:
    """Return True if the model belongs to the modern OpenAI family."""
    if not model:
        return False
    name = model.strip().lower()
    return any(name.startswith(p) for p in _MODERN_PREFIXES)


def is_o_series(model: str) -> bool:
    """Return True if model is o-series (o1, o3, o4) - rejects temperature entirely."""
    if not model:
        return False
    name = model.strip().lower()
    return name.startswith(("o1", "o3", "o4", "o-"))


def build_openai_chat_kwargs(
    model: str,
    max_tokens: int,
    temperature: Optional[float] = None,
    **extra: Any,
) -> dict:
    """Build a chat-completion kwargs dict compatible with the given model.

    - Modern models receive `max_completion_tokens` and only get `temperature`
      when it is explicitly 1 (the only value gpt-5 accepts).
    - Legacy models receive `max_tokens` and `temperature` as-is.
    - Extra kwargs (messages, response_format, ...) are merged last.
    """
    kwargs: dict = {"model": model}

    if is_modern_openai_model(model):
        kwargs["max_completion_tokens"] = max_tokens
        if temperature is not None and temperature == 1:
            kwargs["temperature"] = 1
    else:
        kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

    # Reserved keys that the helper owns; ignore any caller attempt to inject them.
    reserved = {"model", "max_tokens", "max_completion_tokens", "temperature"}
    for key, value in extra.items():
        if key in reserved:
            continue
        kwargs[key] = value

    return kwargs


def get_chat_model(
    model_name: str,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
):
    """Factory that returns a ChatOpenAI instance with correct parameters for the model family.

    Families recognized:
    - gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo → temperature + max_tokens
    - gpt-5, gpt-5-mini → temperature only if 1, max_completion_tokens
    - o1, o1-mini, o3, o3-mini, o4-mini → no temperature, max_completion_tokens

    Args:
        model_name: OpenAI model name (e.g., 'gpt-4o-mini', 'o1-mini')
        temperature: Desired temperature. Ignored silently for o-series.
        max_tokens: Max tokens for response. Defaults to 4096 if not specified.
        **kwargs: Additional parameters passed to ChatOpenAI.

    Returns:
        ChatOpenAI instance configured correctly.
    """
    from langchain_openai import ChatOpenAI

    if max_tokens is None:
        max_tokens = 4096

    # Build kwargs compatible with model family
    chat_kwargs = build_openai_chat_kwargs(
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )

    # Remove temperature for o-series (they reject it entirely)
    if is_o_series(model_name) and "temperature" in chat_kwargs:
        del chat_kwargs["temperature"]

    return ChatOpenAI(**chat_kwargs)


async def safe_chat_completion(
    client: Any,
    model: str,
    messages: list[dict],
    **kwargs: Any,
) -> dict:
    """Call OpenAI API with correct params according to model family.

    Handles max_tokens vs max_completion_tokens and absence of temperature
    in o-series. Designed for direct calls (not LangChain) like health checks.

    Args:
        client: OpenAI client instance (sync or async)
        model: Model name
        messages: List of message dicts
        **kwargs: Additional parameters

    Returns:
        OpenAI response dict
    """
    # Build compatible kwargs
    max_tokens = kwargs.pop("max_tokens", 4096)
    temperature = kwargs.pop("temperature", None)

    api_kwargs = build_openai_chat_kwargs(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )

    # o-series don't accept temperature at all
    if is_o_series(model) and "temperature" in api_kwargs:
        del api_kwargs["temperature"]

    api_kwargs["messages"] = messages

    # Handle both sync and async clients
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        # Async client
        return await client.chat.completions.create(**api_kwargs)
    elif hasattr(client, "chat_completions"):
        # Sync client (legacy)
        return client.chat_completions.create(**api_kwargs)
    else:
        raise ValueError(f"Unknown client type: {type(client)}")
