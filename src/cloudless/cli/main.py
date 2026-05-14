"""cloudless CLI dispatcher (Q30 command catalog).

M1 ships: `init`, `version`, `--help`.
Later milestones add: dev, deploy, rollback, logs, cost, eval, etc.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from cloudless._version import __version__
from cloudless.cli import init as init_cmd


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudless",
        description='cloudless — "Write your agent once. Ship it to any cloud."',
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"cloudless {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # dev
    p_dev = sub.add_parser(
        "dev",
        help="Run an agent locally (Q13) with real LLM + in-memory ctx.",
    )
    p_dev.add_argument("agent_name", help="Agent name as declared in cloudless.yaml.")
    p_dev.add_argument(
        "--host", default="127.0.0.1",
        help="Bind host (default: 127.0.0.1).",
    )
    p_dev.add_argument(
        "--port", type=int, default=8080,
        help="Bind port (default: 8080; matches AgentCore HTTP contract).",
    )

    # deploy
    p_deploy = sub.add_parser(
        "deploy",
        help="Deploy an agent to AgentCore (Q4 + Q6).",
    )
    p_deploy.add_argument("agent_name", help="Agent name as declared in cloudless.yaml.")
    p_deploy.add_argument(
        "--region", default="us-east-1",
        help="AWS region for the deploy (default: us-east-1).",
    )
    p_deploy.add_argument(
        "--build-dir", default=None,
        help="Where to materialize the artifact (default: .cloudless/build/<name>).",
    )

    # init
    p_init = sub.add_parser(
        "init",
        help="Scaffold a new cloudless project (Q24 project layout).",
    )
    p_init.add_argument("project_name", help="Project directory to create.")
    p_init.add_argument(
        "--framework",
        choices=["langgraph", "strands"],
        default="langgraph",
        help="Agent framework for the scaffolded example (default: langgraph).",
    )
    p_init.add_argument(
        "--cloud",
        choices=["aws", "gcp"],
        default="aws",
        help="Default deploy cloud (M1: aws only).",
    )
    p_init.add_argument(
        "--force", action="store_true",
        help="Overwrite project directory if it exists.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns 0 on success, non-zero on failure."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return init_cmd.run(
            project_name=args.project_name,
            framework=args.framework,
            cloud=args.cloud,
            force=args.force,
        )

    if args.command == "dev":
        from cloudless.cli import dev as dev_cmd
        return dev_cmd.run(
            agent_name=args.agent_name,
            host=args.host,
            port=args.port,
        )

    if args.command == "deploy":
        from cloudless.cli import deploy as deploy_cmd
        return deploy_cmd.run(
            agent_name=args.agent_name,
            region=args.region,
            build_dir=Path(args.build_dir) if args.build_dir else None,
        )

    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable; parser.error sys.exits


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
