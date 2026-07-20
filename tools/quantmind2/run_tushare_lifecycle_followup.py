#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.services.engine.tushare_lifecycle_followup.engine import run_lifecycle_followup


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or exactly replay the Fixed-100 lifecycle follow-up")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--store-root", type=Path)
    args = parser.parse_args()
    result = run_lifecycle_followup(
        repository_root=REPOSITORY_ROOT,
        work_root=args.work_root,
        store_root=args.store_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
