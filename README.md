# Hermes Fast Chat

Start a new [Hermes Agent](https://github.com/NousResearch/hermes-agent) CLI or TUI
session with an explicit model and Fast mode, without changing your profile defaults.

[日本語](README.ja.md) · [MIT license](LICENSE)

```bash
hermes fast-chat --model gpt-6.1-sol --provider openai-codex
hermes fast-chat --tui --model gpt-6.1-sol --provider openai-codex
```

## Install

```bash
hermes plugins install iyoda/hermes-fast-chat --enable
```

For a named profile, add `-p <profile>` to both installation and launch commands.
The command requires the default `plugins.isolation: in_process`; Hermes skips
plugin CLI command registration in `host` mode.

If you previously copied this plugin into your home manually, keep a backup of
that directory before replacing it with a Git-based installation.

## Usage

```bash
hermes fast-chat --model <model> [--provider <provider>]
hermes fast-chat --tui --model <model> [--provider <provider>]
hermes -p <profile> fast-chat --model <model> --provider <provider>
```

| Option | Purpose |
| --- | --- |
| `-m`, `--model` | Required model override for the new session |
| `--provider` | Provider override; omission keeps your profile's provider |
| `--tui` | Open the Ink TUI; the default is the classic CLI |
| `--tier fast\|ultrafast` | Requested speed; defaults to `fast` |
| `--reasoning <level>` | Reasoning effort for this session |
| `--in <directory>` | Session working directory |
| `--hermes-bin <path>` | Hermes executable for gateway bootstrap and the TUI |

**Changing the model does not change the provider.** If your default provider is
Anthropic, specify `--provider openai-codex` to use your Codex subscription, or the
appropriate provider for your account. Model names and Fast availability depend on
that provider and your entitlement.

Fast can cost more. Hermes validates the requested tier before opening the
frontend; the provider determines the speed and billing actually served.

## How it works

1. Bootstrap an authenticated Gateway connection with
   `hermes gateway attach --start --json`.
2. Create a fresh session with the requested model, provider and `service_tier`.
3. Validate the tier using the same `config.set fast` route as the TUI.
4. Resume the session in the frontend. Classic CLI launch uses the published
   `cli.HermesCLI` API to carry the model and speed into the frontend instance.

On older macOS/Linux releases without `gateway attach`, the plugin uses
`gateway ensure --json` and the local same-user control socket. It checks path
ownership, permissions, peer UID, profile and Gateway instance identity before
using the single-use connection ticket. This compatibility path depends on the
Gateway's control wire protocol and may require updates when that protocol changes.

The plugin does not patch core functions, edit default model settings, or submit
an inference request during preparation. It is an independent community plugin.

## Compatibility and limits

- Python 3.11+ and `websockets>=15,<16` in the Hermes environment.
- Gateway support for `session.create` with `service_tier`, plus `config.set fast`.
  Windows also requires `gateway attach`; Windows has not been tested.
- Verified on macOS with Hermes v0.23.0, commit
  `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`: classic CLI and Ink TUI both opened
  with `gpt-6.1-sol`, provider `openai-codex`, and Fast enabled. No inference was
  submitted during verification.
- Each invocation creates a new session. Failed tier validation can leave an
  empty session; its ID is printed for inspection.
- Profile model/tool settings are respected. Extra shell-specific environment
  forwarding and temporary API-key arguments are not supported.
- Classic CLI runs in the invoking Hermes interpreter; `--hermes-bin` does not
  switch that interpreter.

## Development

With a Hermes source checkout and its test environment available:

```bash
HERMES_SOURCE=/path/to/hermes-agent bash scripts/test.sh
```

This delegates to Hermes's `scripts/run_tests.sh`. Tests cover real local
WebSocket transport, older same-user socket bootstrap, unavailable Fast tiers,
classic frontend state, and plugin discovery. They do not call a paid model API.

For linting with an existing Ruff installation:

```bash
ruff check .
```

Validate the plugin using your installed Hermes:

```bash
hermes plugins validate /path/to/hermes-fast-chat
```

Report issues at [GitHub Issues](https://github.com/iyoda/hermes-fast-chat/issues).
Include the Hermes version, operating system, command and error; omit credentials
and Gateway tickets.
