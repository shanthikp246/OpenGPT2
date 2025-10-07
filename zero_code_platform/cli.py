"""Command line utilities for running the zero-code platform."""

from __future__ import annotations

import argparse
import sys
from typing import List

import uvicorn

from .config import PlatformConfig
from .manager import ZeroCodePlatform


def _print_summary(config: PlatformConfig) -> None:
    lines: List[str] = ["Loaded configuration summary:"]
    if config.rag:
        rag = config.rag
        lines.append(
            f"  • RAG service -> mode={rag.mode}, host={rag.host}, port={rag.port}, index={rag.index_path}"
        )
    else:
        lines.append("  • RAG service -> not configured")

    if config.fine_tune:
        ft = config.fine_tune
        lines.append(
            "  • Fine-tune service -> "
            f"host={ft.host}, port={ft.port}, documents={ft.documents_path}, auto_start={ft.generate_on_startup}"
        )
    else:
        lines.append("  • Fine-tune service -> not configured")

    print("\n".join(lines))


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Zero-code AI platform controller")
    parser.add_argument(
        "--config",
        default="platform.config.yaml",
        help="Path to the platform configuration file (YAML).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-config", help="Create a starter configuration file")
    init_parser.add_argument(
        "--path",
        default="platform.config.yaml",
        help="Destination path for the generated template.",
    )

    subparsers.add_parser("validate", help="Validate the configuration file")

    run_parser = subparsers.add_parser("run", help="Run one of the platform services")
    run_parser.add_argument("service", choices=["rag", "fine_tune"], help="Service to run")
    run_parser.add_argument("--host", help="Override the configured host")
    run_parser.add_argument("--port", type=int, help="Override the configured port")

    args = parser.parse_args(argv)

    if args.command == "init-config":
        destination = PlatformConfig.write_example(args.path)
        print(f"Example configuration written to {destination}")
        return

    config = PlatformConfig.load(args.config)

    if args.command == "validate":
        _print_summary(config)
        return

    platform = ZeroCodePlatform(config)

    if args.command == "run":
        if args.service == "rag":
            if not config.rag:
                parser.error("RAG service is not configured in the provided config file.")
            app = platform.build_rag_app()
            host = args.host or config.rag.host
            port = args.port or config.rag.port
            uvicorn.run(app, host=host, port=port, log_level="info")
        elif args.service == "fine_tune":
            if not config.fine_tune:
                parser.error("Fine-tune service is not configured in the provided config file.")
            app = platform.build_finetune_app()
            host = args.host or config.fine_tune.host
            port = args.port or config.fine_tune.port
            uvicorn.run(app, host=host, port=port, log_level="info")
        return

    parser.print_help()


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    main(sys.argv[1:])
