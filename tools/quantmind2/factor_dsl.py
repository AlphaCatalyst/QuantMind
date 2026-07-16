#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.engine.factor_dsl import (compile_template, execute_compiled, parse_template,
                                                snapshot_contract, validate_values)
from backend.services.engine.factor_dsl.artifact import sha256_file
from backend.services.engine.factor_dsl.canonical import template_payload


def bindings(raw):
    return json.loads(raw) if raw else {}


def main(argv=None):
    parser = argparse.ArgumentParser(description="QuantMind Factor DSL v1 offline tool")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-template"); validate.add_argument("--template", required=True)
    for name in ("compile", "execute"):
        cmd = sub.add_parser(name); cmd.add_argument("--template", required=True); cmd.add_argument("--snapshot-root", required=True); cmd.add_argument("--snapshot-id", required=True); cmd.add_argument("--parameters", default="{}")
        if name == "execute": cmd.add_argument("--output-root", default="/tmp/quantmind2-factor-values")
    verify = sub.add_parser("validate-values"); verify.add_argument("--snapshot-root", required=True); verify.add_argument("--output-root", required=True); verify.add_argument("--factor-values-id", required=True)
    inspect = sub.add_parser("inspect"); inspect.add_argument("--output-root", required=True); inspect.add_argument("--factor-values-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-template":
            template = parse_template(Path(args.template)); result = {"status": "valid", "template": template_payload(template)}
        elif args.command in ("compile", "execute"):
            template = parse_template(Path(args.template)); contract = snapshot_contract(args.snapshot_root, args.snapshot_id); compiled = compile_template(template, contract, bindings(args.parameters))
            result = {"status": "compiled", "factor_template_id": compiled.template_id, "factor_instance_id": compiled.factor_instance_id,
                      "required_features": list(compiled.required_features), "bound_parameters": dict(compiled.bound_parameters), "node_count": compiled.node_count, "depth": compiled.depth, "warmup_periods": compiled.warmup_periods, "warnings": list(compiled.warnings)}
            if args.command == "execute":
                executed = execute_compiled(compiled, args.snapshot_root, args.output_root)
                result.update({"status": "executed", "factor_values_id": executed.factor_values_id, "artifact_path": executed.artifact_path, "replayed": executed.replayed})
        elif args.command == "validate-values":
            result = validate_values(args.snapshot_root, args.output_root, args.factor_values_id)
        else:
            path = Path(args.output_root) / args.factor_values_id
            manifest = json.loads((path / "manifest.json").read_text()); quality = json.loads((path / "quality.json").read_text())
            result = {"status": "inspected", "manifest": manifest, "quality": quality,
                      "artifact_hashes": {p.name: sha256_file(p) for p in path.iterdir() if p.is_file()}}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)); return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
