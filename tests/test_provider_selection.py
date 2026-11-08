"""Provider selection never rewrites an explicit model identifier."""
import argparse
import asyncio

import pytest
from test_fast_chat import launcher


@pytest.mark.parametrize("model,provider,fallbacks,expected", [
    ("gpt-sol-6.1", None, [{"model": "gpt-6.1-sol-900k", "provider": "openai-codex"}], "openai-codex"),
    ("gpt-6.1-sol-900k", None, [{"model": "gpt-6.1-sol-900k", "provider": "openai-codex"}], "openai-codex"),
    ("opus", None, [], "anthropic"),
    ("gpt-sol-6.1", "openai", [], "openai"),
    ("gpt-new", None, [{"model": "gpt-a", "provider": "openai", "base_url": "https://example.invalid/v1"},
                        {"model": "gpt-b", "provider": "openai", "base_url": "https://example.invalid/v1/"}], "openai"),
    ("gpt-new", None, [{"provider": "openai-codex"}], "anthropic"),
    ("unknown-model", None, [], "anthropic"),
])
def test_explicit_model_provider(monkeypatch, model, provider, fallbacks, expected):
    from hermes_cli import config

    monkeypatch.setattr(config, "load_config", lambda: {
        "model": {"default": "opus", "provider": "anthropic"},
        "fallback_providers": fallbacks,
    })
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    args = parser.parse_args(["--model", model] + (["--provider", provider] if provider else []))
    received = []

    async def prepare(ws, selected):
        received.append((selected.model, selected.provider))
        return "selected-session"

    monkeypatch.setattr(launcher, "prepare_session", prepare)
    assert asyncio.run(launcher.prepare_selected_session(None, args)) == "selected-session"
    assert received == [(model, expected)]


def test_ambiguous_gpt_provider_requires_override(monkeypatch):
    from hermes_cli import config

    monkeypatch.setattr(config, "load_config", lambda: {
        "model": {"default": "opus", "provider": "anthropic"},
        "fallback_providers": [{"model": "gpt-a", "provider": "openai"},
                               {"model": "gpt-b", "provider": "openai-codex"}],
    })
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    args = parser.parse_args(["--model", "gpt-sol-6.1"])
    with pytest.raises(launcher.LaunchError, match="--provider"):
        asyncio.run(launcher.prepare_selected_session(None, args))
