#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.momentum_alpha_diagnostics.engine import execute_audit, replay_audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Momentum signal semantic audit and alpha decomposition v1")
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-004"))
    parser.add_argument("command", choices=("execute", "validate"))
    args = parser.parse_args(argv)
    try:
        function = execute_audit if args.command == "execute" else replay_audit
        result = function(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
