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

    # eval
    p_eval = sub.add_parser("eval", help="Run an eval dataset against an LLM (Q8).")
    p_eval_sub = p_eval.add_subparsers(dest="eval_command", required=True)
    p_eval_run = p_eval_sub.add_parser("run", help="Run an eval dataset.")
    p_eval_run.add_argument("dataset_path", help="Path to JSONL dataset.")
    p_eval_run.add_argument("--output", "-o", default=None,
                             help="Where to write results JSONL.")
    p_eval_run.add_argument("--model", default="nova-micro",
                             help="LLM alias for the target (default: nova-micro).")
    p_eval_run.add_argument("--region", default="us-east-1")

    # logs
    p_logs = sub.add_parser("logs", help="Stream a deployed agent's CloudWatch logs.")
    p_logs.add_argument("agent_name")
    p_logs.add_argument("--region", default="us-east-1")
    p_logs.add_argument("--since", default="10m", help="e.g. 10m, 1h, 24h, 7d")
    p_logs.add_argument("--follow", "-f", action="store_true")
    p_logs.add_argument("--endpoint", default="DEFAULT")

    # versions
    p_ver = sub.add_parser("versions", help="List versions + endpoint aliases for an agent.")
    p_ver.add_argument("agent_name")
    p_ver.add_argument("--region", default="us-east-1")

    # rollback
    p_rb = sub.add_parser("rollback", help="Roll an endpoint alias back to a prior version.")
    p_rb.add_argument("agent_name")
    p_rb.add_argument("--to", dest="to_version", default=None,
                      help="Target version (default: 2nd-most-recent).")
    p_rb.add_argument("--endpoint", default="DEFAULT")
    p_rb.add_argument("--region", default="us-east-1")

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

    if args.command == "eval":
        if args.eval_command == "run":
            from cloudless.cli import eval as eval_cmd
            return eval_cmd.run(
                dataset_path=args.dataset_path,
                output_path=args.output,
                model=args.model,
                region=args.region,
            )

    if args.command == "logs":
        from cloudless.cli import ops
        return ops.logs_command(
            agent_name=args.agent_name, region=args.region,
            since=args.since, follow=args.follow, endpoint=args.endpoint,
        )

    if args.command == "versions":
        from cloudless.cli import ops
        return ops.versions_command(agent_name=args.agent_name, region=args.region)

    if args.command == "rollback":
        from cloudless.cli import ops
        return ops.rollback_command(
            agent_name=args.agent_name, to_version=args.to_version,
            endpoint=args.endpoint, region=args.region,
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
