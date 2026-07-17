from __future__ import annotations

from pathlib import Path

from .descriptor import descriptor_from_dict
from .enums import IntegrityStatus
from .models import IntegrityIssue, IntegrityReport


def scan_store_integrity(store) -> IntegrityReport:
    issues: list[IntegrityIssue] = []
    try:
        store.validate_format()
    except Exception as exc:
        issues.append(IntegrityIssue("INVALID_FORMAT", "FORMAT.json", type(exc).__name__))
    descriptors = []
    artifact_ids: dict[str, str] = {}
    referenced: dict[str, int] = {}
    for path in sorted((store.root / "artifacts").glob("*/*/descriptor.json")):
        if path.parent.name.startswith("."):
            continue
        try:
            import json
            descriptor = descriptor_from_dict(json.loads(path.read_text(encoding="utf-8")))
            descriptors.append(descriptor)
            previous = artifact_ids.setdefault(descriptor.artifact_id, descriptor.descriptor_id)
            if previous != descriptor.descriptor_id:
                issues.append(IntegrityIssue("DUPLICATE_ARTIFACT_ID", descriptor.artifact_id, "multiple descriptors"))
            for item in descriptor.files:
                referenced.setdefault(item.sha256, item.size_bytes)
                try:
                    if not store.blobs.verify(item.sha256, item.size_bytes):
                        issues.append(IntegrityIssue("MISSING_BLOB", item.sha256, descriptor.artifact_id))
                except Exception:
                    issues.append(IntegrityIssue("CORRUPT_BLOB", item.sha256, descriptor.artifact_id))
        except Exception as exc:
            issues.append(IntegrityIssue("INVALID_DESCRIPTOR", path.parent.name, type(exc).__name__))
    actual: dict[str, int] = {}
    for path in (store.root / "objects" / "sha256").glob("*/*"):
        if path.is_file():
            actual[path.name] = path.stat().st_size
    unreferenced = tuple(
        {"sha256": digest, "size_bytes": size, "first_discovered_inventory_id": None,
         "referenced": False}
        for digest, size in sorted(actual.items()) if digest not in referenced
    )
    corrupt = any(item.code in {"INVALID_FORMAT", "CORRUPT_BLOB", "MISSING_BLOB", "INVALID_DESCRIPTOR", "DUPLICATE_ARTIFACT_ID"} for item in issues)
    status = IntegrityStatus.CORRUPT.value if corrupt else (
        IntegrityStatus.DEGRADED.value if unreferenced else IntegrityStatus.HEALTHY.value
    )
    return IntegrityReport(status, len(descriptors), len(actual), tuple(issues), unreferenced)


def list_unreferenced_blobs(store) -> tuple[dict, ...]:
    return scan_store_integrity(store).unreferenced_blobs
