"""Start Pulsar AI UI from local workspace sources.

This script avoids relying on an installed `pulsar` entrypoint, so the running
server always uses code from the current repository checkout.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pulsar_ai.ui.app import start_ui_server


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Pulsar AI UI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18088)
    parser.add_argument("--env-file", default="", help="Path to env profile file")
    parser.add_argument("--stand-mode", default="", help="PULSAR_STAND_MODE value")
    parser.add_argument("--cors-origins", default="", help="PULSAR_CORS_ORIGINS value")
    parser.add_argument(
        "--auth-enabled",
        action="store_true",
        help="Enable API key auth (PULSAR_AUTH_ENABLED=true)",
    )
    parser.add_argument(
        "--auth-disabled",
        action="store_true",
        help="Disable API key auth (PULSAR_AUTH_ENABLED=false)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.env_file:
        os.environ["PULSAR_ENV_FILE"] = str(Path(args.env_file).resolve())
    if args.stand_mode:
        os.environ["PULSAR_STAND_MODE"] = args.stand_mode
    if args.cors_origins:
        os.environ["PULSAR_CORS_ORIGINS"] = args.cors_origins

    if args.auth_enabled and args.auth_disabled:
        raise SystemExit("Use only one of --auth-enabled/--auth-disabled")
    if args.auth_enabled:
        os.environ["PULSAR_AUTH_ENABLED"] = "true"
    if args.auth_disabled:
        os.environ["PULSAR_AUTH_ENABLED"] = "false"

    start_ui_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
