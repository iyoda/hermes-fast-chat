# Hermes Fast Chat

Start a new Hermes CLI/TUI session in Fast mode with one command.
A small community bridge until Hermes itself makes Fast startup easier.
It does not modify Hermes core or your profile defaults.

[日本語](README.ja.md) · [Plugin catalog](https://hermes-agent.nousresearch.com/marketplace/fast-chat) · [MIT license](LICENSE)

## Install

```bash
hermes plugins install iyoda/hermes-fast-chat --enable
```

## Start

```bash
hermes fast-chat
```

Uses your profile's model and CLI/TUI preference. If Fast is unavailable for the
model, tries configured fallback routes; stops if none support Fast, rather than
silently starting at normal speed. Each launch creates a new session.

Optional overrides:

```bash
hermes fast-chat --tui
hermes fast-chat --model <model> --provider <provider>
hermes -p <profile> fast-chat
```

Requires Hermes >=0.23.0 and the default `plugins.isolation: in_process`.
Fast availability and billing depend on your provider and entitlement;
additional charges may apply.

## Scope

Only a launcher: no separate configuration, model tools, or core patches.
When Hermes provides an equivalent startup flow, prefer the built-in one.

Launch preparation can start a Gateway that remains running, and saves a new
session. It does not submit inference or read provider credential stores.
Failed validation may leave an empty session.

See the [technical reference](docs/technical-reference.md) for all options,
route selection, compatibility, security disclosures, and development checks.
Report problems at [GitHub Issues](https://github.com/iyoda/hermes-fast-chat/issues).
