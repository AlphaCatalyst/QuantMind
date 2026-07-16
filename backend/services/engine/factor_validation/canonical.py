import hashlib
import json
from pathlib import Path


CANONICALIZATION_VERSION = "factor-validation-canonical-json-v1"


def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def hash_payload(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_bytes(canonical_json_bytes(value) + b"\n")
