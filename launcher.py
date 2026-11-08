"""Launch through gateway JSON-RPC and Hermes's published classic CLI API."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import uuid
from contextlib import chdir
from pathlib import Path


class LaunchError(Exception):
    """A launch failed before handing control to the frontend."""


class FastUnavailable(LaunchError):
    """The gateway refused the requested tier for this route."""


def setup_parser(parser):
    parser.add_argument("-m", "--model", help="Model override (default: profile, then configured fallbacks)")
    parser.add_argument("--provider", help="Provider override for this session")
    parser.add_argument("--reasoning", help="Reasoning effort for this session")
    interface = parser.add_mutually_exclusive_group()
    interface.add_argument("--tui", dest="tui", action="store_const", const=True, default=None,
                           help="Open the Ink TUI (default: display.interface from config)")
    interface.add_argument("--cli", dest="tui", action="store_const", const=False,
                           help="Open the classic CLI, overriding display.interface")
    parser.add_argument("--tier", choices=("fast", "ultrafast"), default="fast")
    parser.add_argument("--in", dest="cwd", default=None, help="Session working directory")
    parser.add_argument("--hermes-bin", default="hermes", help="Hermes executable to launch")


def bootstrap(executable):
    # attach's stdout contains a single-use credential: capture it, never echo it.
    result = subprocess.run(
        [executable, "gateway", "attach", "--start", "--json"],
        capture_output=True, text=True, timeout=90, check=False,
    )
    if result.returncode:
        if result.returncode == 2 and "'attach'" in result.stderr and "not a `hermes gateway` command" in result.stderr:
            if __package__:
                from .legacy_bootstrap import attach_legacy
            else:
                from legacy_bootstrap import attach_legacy
            return attach_legacy(executable)
        raise LaunchError("Gateway attach failed; run `hermes gateway status` for details.")
    try:
        grant = json.loads(result.stdout)
        if (not isinstance(grant.get("url"), str)
                or not isinstance(grant.get("protocol"), str)
                or not isinstance(grant.get("protocols"), list)
                or not all(isinstance(p, str) for p in grant["protocols"])):
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise LaunchError("Gateway attach returned an invalid connection grant.") from exc
    return grant


async def rpc(ws, method, params):
    request_id = uuid.uuid4().hex
    await ws.send(json.dumps({"jsonrpc": "2.0", "id": request_id,
                              "method": method, "params": params}))
    async with asyncio.timeout(60):
        while True:
            frame = json.loads(await ws.recv())
            if frame.get("id") != request_id:
                continue
            if "error" in frame:
                # Only print bounded reason codes, never arbitrary remote content or credentials.
                reason = frame["error"].get("message", "request_failed")
                if not isinstance(reason, str) or len(reason) > 80 or not reason.replace("_", "").isalnum():
                    reason = "request_failed"
                raise LaunchError(f"{method}: {reason}")
            return frame.get("result", {})


async def prepare_session(ws, args):
    contract = (await rpc(ws, "runtime.describe", {})).get("session_create", {})
    params = {
        "request_id": uuid.uuid4().hex,
        "source": "tui" if args.tui else "cli",
        "model": args.model,
        "cwd": str(Path(args.cwd or os.getcwd()).expanduser().resolve(strict=True)),
        # Pin the launch tier as well as checking availability below. The creation receipt
        # keeps this choice across daemon restarts; config.set alone is a live override.
        "service_tier": args.tier,
    }
    if not Path(params["cwd"]).is_dir():
        raise LaunchError("Session working directory must be a directory.")
    for key in ("provider", "reasoning"):
        if value := getattr(args, key):
            params[key] = value
    if base_url := getattr(args, "base_url", None):
        params["base_url"] = base_url
    missing = set(params) - set(contract.get("parameters", []))
    if missing or params["source"] not in contract.get("sources", []):
        raise LaunchError("Gateway lacks the required session creation contract; update/restart Hermes.")
    snapshot = await rpc(ws, "session.create", params)
    session_id = snapshot["session_id"]
    print(f"Session: {session_id}", file=sys.stderr, flush=True)
    # The same route/entitlement check the TUI's /fast uses. Never open a frontend
    # with silently downgraded speed when the chosen model cannot use this tier.
    try:
        answer = await rpc(ws, "config.set", {
            "session_id": session_id, "key": "fast", "value": args.tier,
        })
    except LaunchError as exc:
        if str(exc) == "config.set: fast_unavailable":
            raise FastUnavailable(
                "fast_unavailable: check the model, --provider and your Fast entitlement. "
                "Specify --provider to override automatic route selection."
            ) from exc
        raise
    if answer.get("value") != args.tier:
        raise LaunchError("Gateway did not confirm the requested Fast tier.")
    return session_id


def configured_routes(config):
    model = config.get("model") or {}
    if not isinstance(model, dict):
        model = {"default": model}
    routes = [{"model": model.get("default"), "provider": model.get("provider"),
               "base_url": model.get("base_url")}]
    for key in ("fallback_providers", "fallback_model"):
        entries = config.get(key) or []
        if isinstance(entries, dict):
            entries = [entries]
        if isinstance(entries, list):
            routes.extend(entry for entry in entries if isinstance(entry, dict)
                          and all(isinstance(entry.get(k), str) and entry[k].strip()
                                  for k in ("model", "provider")))
    return routes


def route_identity(entry):
    return entry.get("provider"), (entry.get("base_url") or "").strip().rstrip("/")


def infer_model_route(args):
    from hermes_cli.config import load_config

    routes = configured_routes(load_config())
    matches = [e for e in routes if e.get("model") == args.model and e.get("provider")]
    if not matches and args.model.startswith("gpt-"):
        matches = [e for e in routes if e.get("provider") in ("openai", "openai-codex")]
    if len({route_identity(e) for e in matches}) > 1:
        raise LaunchError("Multiple configured routes match this model; specify --provider.")
    selected = matches[0] if matches else routes[0]
    if any(selected.get(k) for k in ("api_key", "key_env", "api_key_env")):
        raise LaunchError("Fallback credential overrides are not supported; specify --provider.")
    args.provider = selected.get("provider")
    args.base_url = selected.get("base_url")


async def prepare_selected_session(ws, args):
    if args.model is not None:
        if args.provider is None:
            infer_model_route(args)
        session_id = await prepare_session(ws, args)
        print(f"Fast route: {args.provider or 'profile provider'} / {args.model}", file=sys.stderr)
        return session_id

    from hermes_cli.config import load_config
    candidates = configured_routes(load_config())
    if args.provider is not None:
        candidates = [{**candidates[0], "provider": args.provider, "base_url": None},
                      *(entry for entry in candidates[1:] if entry["provider"] == args.provider)]
    seen = set()
    for entry in candidates:
        route = (entry.get("model"), entry.get("provider"))
        identity = (route[0], *route_identity(entry))
        if not route[0] or identity in seen:
            continue
        seen.add(identity)
        if any(entry.get(key) for key in ("api_key", "key_env", "api_key_env")):
            raise LaunchError("Fallback credential overrides are not supported; use a named provider.")
        candidate = argparse.Namespace(**vars(args))
        candidate.model, candidate.provider = route
        candidate.base_url = entry.get("base_url")
        try:
            session_id = await prepare_session(ws, candidate)
        except FastUnavailable:
            print(f"Fast unavailable: {route[1] or 'profile provider'} / {route[0]}; checking fallback.",
                  file=sys.stderr)
            continue
        args.model, args.provider = route
        args.base_url = candidate.base_url
        print(f"Fast route: {route[1] or 'profile provider'} / {route[0]}", file=sys.stderr)
        return session_id
    raise FastUnavailable("fast_unavailable: no configured default/fallback route supports the requested tier.")


async def create_session(args):
    from websockets.asyncio.client import connect
    from websockets.exceptions import WebSocketException

    grant = await asyncio.to_thread(bootstrap, args.hermes_bin)
    try:
        async with connect(grant["url"], subprotocols=grant["protocols"],
                           proxy=None, open_timeout=10, max_size=8 * 1024 * 1024) as ws:
            if ws.subprotocol != grant["protocol"]:
                raise LaunchError("Gateway WebSocket protocol mismatch.")
            return await prepare_selected_session(ws, args)
    except WebSocketException as exc:
        raise LaunchError("Gateway connection failed; no frontend was opened.") from exc


def frontend_command(args, session_id):
    # Do not repeat model/provider flags on resume: the session already owns its route.
    return [args.hermes_bin, "--tui" if args.tui else "--cli", "--resume", session_id]


def run_classic(args, session_id):
    # The public cli module is in Hermes's published plugin API. Older classic
    # frontends do not adopt route/tier fields from an empty resumed session;
    # pass the route explicitly and seed this instance's tier before run().
    from cli import HermesCLI

    with chdir(Path(args.cwd or os.getcwd()).expanduser().resolve(strict=True)):
        route_options = {}
        if base_url := getattr(args, "base_url", None):
            route_options["base_url"] = base_url
        client = HermesCLI(model=args.model, provider=args.provider, reasoning=args.reasoning,
                           resume=session_id, **route_options)
        client.service_tier = {"fast": "priority", "ultrafast": "ultrafast"}[args.tier]
        client.run()


def launch(args):
    try:
        if args.tui is None:
            from hermes_cli.config import load_config

            interface = (load_config().get("display", {}) or {}).get("interface", "cli")
            args.tui = isinstance(interface, str) and interface.strip().lower() == "tui"
        session_id = asyncio.run(create_session(args))
        if args.tui:
            raise SystemExit(subprocess.call(frontend_command(args, session_id)))
        run_classic(args, session_id)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except ImportError:
        print("fast-chat: requires websockets>=15,<16 in the Hermes environment.", file=sys.stderr)
        raise SystemExit(1) from None
    except (LaunchError, OSError, TimeoutError, ValueError, KeyError) as exc:
        print(f"fast-chat: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    setup_parser(parser)
    launch(parser.parse_args())
