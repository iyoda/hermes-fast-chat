"""Automatic Fast route selection without inference or profile writes."""
import asyncio

import pytest
from plugin_support import launcher, parse_args


@pytest.mark.parametrize("explicit,provider,failures,expected", [
    (False, None, [], [("opus", "anthropic")]),
    (False, None, ["opus"], [("opus", "anthropic"), ("gpt-sol-6.1", "openai-codex")]),
    (True, None, ["opus"], [("opus", "anthropic")]),
    (False, "anthropic", ["opus"], [("opus", "anthropic")]),
    (False, None, ["opus", "gpt-sol-6.1"], [("opus", "anthropic"), ("gpt-sol-6.1", "openai-codex")]),
])
def test_default_then_configured_fallback(monkeypatch, capsys, explicit, provider, failures, expected):
    from hermes_cli import config

    settings = {"model": {"default": "opus", "provider": "anthropic"},
                "fallback_model": {"model": "gpt-sol-6.1", "provider": "openai-codex"}}
    monkeypatch.setattr(config, "load_config", lambda: settings)
    flags = ["--model", "opus"] if explicit else []
    if provider:
        flags += ["--provider", provider]
    args = parse_args(flags)
    attempted = []

    async def prepare(ws, candidate):
        attempted.append((candidate.model, candidate.provider))
        if candidate.model in failures:
            raise launcher.FastUnavailable("fast_unavailable")
        return "selected-session"

    monkeypatch.setattr(launcher, "prepare_session", prepare)
    if all(model in failures for model, _ in expected):
        with pytest.raises(launcher.LaunchError, match="fast_unavailable"):
            asyncio.run(launcher.prepare_selected_session(None, args))
    else:
        assert asyncio.run(launcher.prepare_selected_session(None, args)) == "selected-session"
        assert (args.model, args.provider) == expected[-1]
        assert expected[-1][0] in capsys.readouterr().err
    assert attempted == expected
    assert settings["model"]["default"] == "opus"


def test_other_errors_do_not_trigger_fallback(monkeypatch):
    from hermes_cli import config

    monkeypatch.setattr(config, "load_config", lambda: {
        "model": {"default": "primary-model", "provider": "openai"},
        "fallback_providers": [{"model": "gpt-sol-6.1", "provider": "openai-codex"}],
    })
    args = parse_args([])
    attempted = []

    async def prepare(ws, candidate):
        attempted.append(candidate.model)
        raise launcher.LaunchError("session.create: storage_unavailable")

    monkeypatch.setattr(launcher, "prepare_session", prepare)
    with pytest.raises(launcher.LaunchError, match="storage_unavailable"):
        asyncio.run(launcher.prepare_selected_session(None, args))
    assert attempted == ["primary-model"]
