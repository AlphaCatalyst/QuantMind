import hashlib
import json
from pathlib import Path


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def hash_payload(value): return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value): Path(path).write_bytes(canonical_bytes(value) + b"\n")
