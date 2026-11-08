#!/usr/bin/env bash
set -euo pipefail

plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${HERMES_SOURCE:?Set HERMES_SOURCE to a Hermes Agent source checkout}"
hermes_source="$(cd "$HERMES_SOURCE" && pwd)"
cd "$hermes_source"
exec bash scripts/run_tests.sh "$plugin_root/tests" "$@"
