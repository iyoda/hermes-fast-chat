"""Plugin launch contracts against a real local WebSocket transport; no inference."""
import argparse
import asyncio
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from websockets.asyncio.server import serve

PLUGIN = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fast_chat_test_plugin", PLUGIN / "__init__.py",
                                           submodule_search_locations=[str(PLUGIN)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
launcher = importlib.import_module("fast_chat_test_plugin.launcher")


@pytest.mark.parametrize("tui,tier,automatic", [(False, "fast", False), (True, "ultrafast", False),
                                              (False, "fast", True)])
def test_create_validate_and_resume_transport(tmp_path, monkeypatch, tui, tier, automatic):
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    flags = ["--model", "example-model", "--provider", "example-provider",
             "--tier", tier, "--in", str(tmp_path)]
    if automatic:
        from hermes_cli import config

        monkeypatch.setattr(config, "load_config", lambda: {
            "model": {"default": "opus", "provider": "anthropic"},
            "fallback_model": {"model": "example-model", "provider": "example-provider",
                               "base_url": "https://example.invalid/v1"},
        })
        flags = flags[4:]
    args = parser.parse_args(flags + (["--tui"] if tui else []))
    calls = []

    async def scenario():
        async def handler(ws):
            async for raw in ws:
                request = json.loads(raw)
                method, params = request["method"], request["params"]
                calls.append((method, params))
                if method == "runtime.describe":
                    result = {"session_create": {
                        "sources": ["cli", "tui"], "parameters": [
                            "request_id", "source", "model", "provider", "cwd", "service_tier", "base_url",
                        ],
                    }}
                elif method == "session.create":
                    result = {"session_id": "session-123"}
                else:
                    result = {"key": "fast", "value": tier}
                if automatic and method == "config.set" and len([c for c in calls if c[0] == "session.create"]) == 1:
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                              "error": {"message": "fast_unavailable"}}))
                    continue
                # Real gateways interleave notifications with RPC responses.
                await ws.send(json.dumps({"jsonrpc": "2.0", "method": "session.info", "params": {}}))
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}))

        async with serve(handler, "127.0.0.1", 0, subprotocols=["hermes-gateway-v1"]) as server:
            port = server.sockets[0].getsockname()[1]

            def attach(command, **kwargs):
                assert command == ["hermes", "gateway", "attach", "--start", "--json"]
                return subprocess.CompletedProcess(command, 0, json.dumps({
                    "url": f"ws://127.0.0.1:{port}", "protocol": "hermes-gateway-v1",
                    "protocols": ["hermes-gateway-v1"], "ticket": "never-print-this",
                }))

            monkeypatch.setattr(launcher.subprocess, "run", attach)
            return await launcher.create_session(args)

    session_id = asyncio.run(scenario())
    if automatic:
        assert [(p["model"], p["provider"]) for method, p in calls if method == "session.create"] == [
            ("opus", "anthropic"), ("example-model", "example-provider"),
        ]
        assert (args.model, args.provider) == ("example-model", "example-provider")
        assert args.base_url == "https://example.invalid/v1"
        assert dict(calls)["session.create"]["base_url"] == args.base_url
    created = dict(calls)["session.create"]
    assert created["model"] == "example-model"
    assert created["provider"] == "example-provider"
    assert created["service_tier"] == tier
    assert created["cwd"] == str(tmp_path.resolve())
    assert created["source"] == ("tui" if tui else "cli")
    assert dict(calls)["config.set"] == {"session_id": session_id, "key": "fast", "value": tier}
    assert launcher.frontend_command(args, session_id) == [
        "hermes", "--tui" if tui else "--cli", "--resume", "session-123",
    ]


def test_unavailable_tier_never_opens_frontend(tmp_path, monkeypatch, capsys):
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    args = parser.parse_args(["--model", "unsupported", "--cli", "--in", str(tmp_path)])

    async def create(args):
        class Socket:
            async def send(self, raw):
                self.request = json.loads(raw)

            async def recv(self):
                request = self.request
                if request["method"] == "runtime.describe":
                    return json.dumps({"id": request["id"], "result": {"session_create": {
                        "sources": ["cli"], "parameters": [
                            "request_id", "source", "model", "cwd", "service_tier",
                        ],
                    }}})
                if request["method"] == "session.create":
                    return json.dumps({"id": request["id"], "result": {"session_id": "empty-session"}})
                return json.dumps({"id": request["id"], "error": {"message": "fast_unavailable"}})

        return await launcher.prepare_session(Socket(), args)

    monkeypatch.setattr(launcher, "create_session", create)

    def forbidden(*args, **kwargs):
        pytest.fail("Frontend must not open after Fast is refused")

    monkeypatch.setattr(launcher.subprocess, "call", forbidden)
    with pytest.raises(SystemExit) as exc:
        launcher.launch(args)
    assert exc.value.code == 1
    assert "fast_unavailable" in capsys.readouterr().err
    assert not (tmp_path / "config.yaml").exists()


def test_real_plugin_discovery_registers_cli(tmp_path, monkeypatch):
    from hermes_cli.plugins import PluginManager

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    shutil.copytree(PLUGIN, home / "plugins" / "fast-chat", ignore=shutil.ignore_patterns("__pycache__"))
    (home / "config.yaml").write_text("plugins:\n  enabled: [fast-chat]\n", encoding="utf-8")
    manager = PluginManager(scope_key=str(home))
    manager.discover_and_load()
    command = manager._cli_commands["fast-chat"]
    parser = argparse.ArgumentParser()
    command["setup_fn"](parser)
    args = parser.parse_args(["--model", "my-model", "--tui"])
    assert args.model == "my-model"
    assert args.tui is True
    assert command["handler_fn"] is not None


@pytest.mark.parametrize("interface,flags,expected", [
    ("tui", [], True),
    ("cli", [], False),
    (None, [], False),
    ("tui", ["--cli"], False),
    ("cli", ["--tui"], True),
])
def test_launch_resolves_interface_before_creating_session(monkeypatch, interface, flags, expected):
    from hermes_cli import config

    monkeypatch.setattr(config, "load_config", lambda: {"display": {"interface": interface}})
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    args = parser.parse_args(["--model", "example-model", *flags])
    created = []
    opened = []

    async def create(args):
        created.append(args.tui)
        return "session-interface"

    monkeypatch.setattr(launcher, "create_session", create)
    monkeypatch.setattr(launcher, "run_classic", lambda *args: opened.append("cli"))
    monkeypatch.setattr(launcher.subprocess, "call", lambda command: opened.append(command) or 0)
    if expected:
        with pytest.raises(SystemExit) as exc:
            launcher.launch(args)
        assert exc.value.code == 0
    else:
        launcher.launch(args)
    assert created == [expected]
    assert opened == ([["hermes", "--tui", "--resume", "session-interface"]] if expected else ["cli"])


def test_classic_receives_route_and_fast_before_opening(tmp_path, monkeypatch):
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    args = parser.parse_args(["--model", "selected-model", "--provider", "selected-provider",
                              "--in", str(tmp_path)])
    opened = []

    class Client:
        def __init__(self, **kwargs):
            self.route = kwargs

        def run(self):
            opened.append((self.route, self.service_tier, Path.cwd()))

    monkeypatch.setitem(sys.modules, "cli", SimpleNamespace(HermesCLI=Client))
    original_cwd = Path.cwd()
    launcher.run_classic(args, "empty-session")
    assert opened == [({"model": "selected-model", "provider": "selected-provider", "reasoning": None,
                       "resume": "empty-session"}, "priority", tmp_path.resolve())]
    assert Path.cwd() == original_cwd


@pytest.mark.platforms("posix")
def test_older_hermes_bootstraps_with_same_user_socket(tmp_path, monkeypatch, capsys):
    # A short path also exercises macOS's 104-byte sockaddr_un bound.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="fc-", dir="/tmp") as directory:
        home = Path(directory)
        endpoint = {"profile_id": str(home), "instance_id": "owner-123", "runtime_protocol": 1,
                    "api_origin": "http://127.0.0.1:12345", "control_home": None}
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if "attach" in command:
                return subprocess.CompletedProcess(command, 2, "", "hermes gateway: 'attach' is not a `hermes gateway` command.")
            return subprocess.CompletedProcess(command, 0, json.dumps({"state": "ready", "endpoint": endpoint}))

        monkeypatch.setattr(launcher.subprocess, "run", run)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            path = home / "gateway.sock"
            listener.bind(str(path))
            path.chmod(0o600)
            listener.listen(1)
            listener.settimeout(5)

            def owner():
                with listener.accept()[0] as peer:
                    peer.settimeout(5)
                    with peer.makefile("rb") as stream:
                        request = json.loads(stream.readline(65536))
                    assert request["verb"] == "session-ticket"
                    assert request["params"]["profile_id"] == str(home)
                    peer.sendall(json.dumps({"ok": True, "protocol": 1, "id": 1, "result": {
                        "profile_id": str(home), "instance_id": "owner-123", "runtime_protocol": 1,
                        "ticket": "secret-ticket",
                    }}).encode() + b"\n")

            with ThreadPoolExecutor(max_workers=1) as pool:
                served = pool.submit(owner)
                grant = launcher.bootstrap("hermes")
                served.result(timeout=5)
        assert commands[-1] == ["hermes", "gateway", "ensure", "--json"]
        assert grant["protocols"][-1] == "hermes-gateway-ticket.secret-ticket"
        assert "secret-ticket" not in capsys.readouterr().out
