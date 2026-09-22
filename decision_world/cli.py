"""Offline planning command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .planner import plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="decision-world")
    parser.add_argument("world", type=Path)
    parser.add_argument("--audience-result", type=Path, help="Optional Audience Swarm Lab synthetic result")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        world = json.loads(args.world.read_text(encoding="utf-8"))
        audience = json.loads(args.audience_result.read_text(encoding="utf-8")) if args.audience_result else None
        result = plan(world, audience)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
