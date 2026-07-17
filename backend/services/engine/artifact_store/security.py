from __future__ import annotations

import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .canonical import hash_file, media_type
from .errors import SourceSecurityError
from .models import ArtifactFile


@dataclass(frozen=True)
class SourceInventory:
    files: tuple[ArtifactFile, ...]
    total_bytes: int


def validate_relative_path(value: str) -> str:
    if not value or "\\" in value:
        raise SourceSecurityError("artifact path must be non-empty POSIX text")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SourceSecurityError("artifact path escapes its logical root")
    return path.as_posix()


def _role(path: str) -> str:
    name = PurePosixPath(path).name
    if name == "manifest.json":
        return "manifest"
    if path.endswith(".parquet"):
        return "data"
    if name in {"quality.json", "summary.json", "result.json", "results.json"}:
        return "evidence"
    return "metadata"


def inspect_source(
    source_directory: Path,
    *,
    maximum_file_count: int,
    maximum_artifact_bytes: int,
) -> SourceInventory:
    root = Path(source_directory)
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise SourceSecurityError("source artifact is unavailable") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise SourceSecurityError("source artifact must be a real directory")

    rows: list[ArtifactFile] = []
    total = 0
    normalized: dict[str, str] = {}
    casefolded: dict[str, str] = {}
    stack = [(root, PurePosixPath())]
    while stack:
        directory, prefix = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise SourceSecurityError("source directory cannot be scanned") from exc
        for entry in entries:
            relative = (prefix / entry.name).as_posix()
            validate_relative_path(relative)
            key = unicodedata.normalize("NFC", relative)
            folded = key.casefold()
            if key in normalized and normalized[key] != relative:
                raise SourceSecurityError("Unicode-normalization path collision")
            if folded in casefolded and casefolded[folded] != relative:
                raise SourceSecurityError("case-colliding artifact paths")
            normalized[key] = relative
            casefolded[folded] = relative
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise SourceSecurityError("symbolic links are forbidden")
            if stat.S_ISDIR(info.st_mode):
                stack.append((Path(entry.path), prefix / entry.name))
                continue
            if not stat.S_ISREG(info.st_mode):
                raise SourceSecurityError("only regular files may be imported")
            if info.st_nlink != 1:
                raise SourceSecurityError("hard-link ambiguity is forbidden")
            if len(rows) >= maximum_file_count:
                raise SourceSecurityError("artifact file-count limit exceeded")
            digest, size = hash_file(Path(entry.path))
            total += size
            if total > maximum_artifact_bytes:
                raise SourceSecurityError("artifact byte limit exceeded")
            rows.append(ArtifactFile(relative, digest, size, media_type(relative), _role(relative)))
    if not rows:
        raise SourceSecurityError("empty directories are not research artifacts")
    return SourceInventory(tuple(sorted(rows, key=lambda x: x.relative_path)), total)
