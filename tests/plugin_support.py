"""Load the plugin and parse real launcher arguments for tests."""
import argparse
import importlib.util
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fast_chat_test_plugin", PLUGIN / "__init__.py",
                                           submodule_search_locations=[str(PLUGIN)])
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
launcher = importlib.import_module("fast_chat_test_plugin.launcher")


def parse_args(flags):
    parser = argparse.ArgumentParser()
    launcher.setup_parser(parser)
    return parser.parse_args(flags)
