from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, BinaryIO


CHUNK_SIZE = 1024 * 1024


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def hash_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def hash_stream(handle: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def hash_file(path: Path) -> tuple[str, int]:
    with Path(path).open("rb") as handle:
        return hash_stream(handle)


def media_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".parquet": "application/vnd.apache.parquet",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }.get(suffix, "application/octet-stream")
