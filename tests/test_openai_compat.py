"""Tests for core.openai_compat helper."""

from orchestrator_service.core.openai_compat import (
    build_openai_chat_kwargs,
    is_modern_openai_model,
)


def test_legacy_models_detected():
    assert is_modern_openai_model("gpt-4o-mini") is False
    assert is_modern_openai_model("gpt-4o") is False
    assert is_modern_openai_model("gpt-3.5-turbo") is False
    assert is_modern_openai_model("") is False


def test_modern_models_detected():
    assert is_modern_openai_model("gpt-5") is True
    assert is_modern_openai_model("gpt-5-mini") is True
    assert is_modern_openai_model("o1-preview") is True
    assert is_modern_openai_model("o3-mini") is True
    assert is_modern_openai_model("o4-mini") is True


def test_legacy_kwargs_use_max_tokens_and_temperature():
    kw = build_openai_chat_kwargs("gpt-4o-mini", 500, temperature=0)
    assert kw == {"model": "gpt-4o-mini", "max_tokens": 500, "temperature": 0}


def test_legacy_kwargs_omit_temperature_when_none():
    kw = build_openai_chat_kwargs("gpt-4o", 300)
    assert kw == {"model": "gpt-4o", "max_tokens": 300}


def test_modern_kwargs_use_max_completion_tokens_and_drop_temperature():
    kw = build_openai_chat_kwargs("gpt-5-mini", 500, temperature=0)
    assert kw == {"model": "gpt-5-mini", "max_completion_tokens": 500}


def test_modern_kwargs_keep_temperature_when_one():
    kw = build_openai_chat_kwargs("gpt-5-mini", 500, temperature=1)
    assert kw == {
        "model": "gpt-5-mini",
        "max_completion_tokens": 500,
        "temperature": 1,
    }


def test_extra_kwargs_are_merged():
    kw = build_openai_chat_kwargs(
        "gpt-5-mini",
        500,
        temperature=0,
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    assert kw["messages"] == [{"role": "user", "content": "hi"}]
    assert kw["response_format"] == {"type": "json_object"}
    assert kw["max_completion_tokens"] == 500
    assert "max_tokens" not in kw
    assert "temperature" not in kw


def test_reserved_extras_are_dropped_via_dict_spread():
    # Callers spreading a dict that contains a reserved token key (via the
    # response_format / messages payload merge pattern) must not be able to
    # override the helper-owned token parameter.
    extras = {"max_completion_tokens": 999}
    kw = build_openai_chat_kwargs("gpt-5-mini", 500, temperature=0, **extras)
    assert kw["max_completion_tokens"] == 500
