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
hermes fast-chat --help
```

For a named profile, also use `-p <profile>` when installing. An explicit
`--model` disables automatic fallback; specify `--provider` if route selection
is ambiguous. Inline fallback credential overrides are unsupported; use a named provider.

Requires Hermes >=0.23.0, Python 3.11+, `websockets>=15,<16`, and the default
`plugins.isolation: in_process` (CLI registration is skipped in `host` mode).
Gateway must support session creation with `service_tier` and `config.set fast`.
Windows requires `gateway attach` and is untested.
Fast availability and billing depend on your provider and entitlement;
additional charges may apply.

## Scope

Only a launcher: no separate configuration, model tools, or core patches.
When Hermes provides an equivalent startup flow, prefer the built-in one.

## Safety and side effects

- Registers only the `fast-chat` CLI command; no tools, hooks, middleware, or Desktop UI.
- Runs the selected Hermes executable directly, without a shell, for Gateway
  bootstrap and the TUI. Use a trusted executable. The Gateway may keep running after exit.
- Reads the active profile configuration and connects to its authenticated Gateway
  WebSocket. Older macOS/Linux versions use a loopback Gateway and same-user Unix
  control socket, checking ownership, permissions, peer UID, and Gateway identity;
  this path may read the profile’s `gateway.sock.path` pointer.
- Keeps a single-use connection grant in memory, without persisting it. Does not
  read `.env`, `auth.json`, keychains, or provider credential stores; Hermes handles authentication.
- Saves a new session and its launch settings through Hermes, not profile defaults.
  Preparation submits no inference; failed validation may leave an empty session.
  After launch, normal Hermes/provider communication and approved tools apply.
- No telemetry, self-updater, approval bypass, or unattended mode. Intended for
  interactive terminals, not cron or agent-tool execution.

## Development

```bash
HERMES_SOURCE=/path/to/hermes-agent bash scripts/test.sh
ruff check .
hermes plugins validate .
```

Tests use local transports and do not call paid model APIs.
Report problems at [GitHub Issues](https://github.com/iyoda/hermes-fast-chat/issues).
