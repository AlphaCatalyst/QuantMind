from __future__ import annotations

import os
import uuid
from pathlib import Path

from .canonical import CHUNK_SIZE, hash_file
from .errors import BlobContentConflict


class ContentAddressedBlobStore:
    def __init__(self, root: Path, *, fsync_on_publish: bool = True) -> None:
        self.root = Path(root)
        self.fsync_on_publish = fsync_on_publish

    def path_for(self, digest: str) -> Path:
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("invalid sha256 digest")
        return self.root / "objects" / "sha256" / digest[:2] / digest

    def _verify(self, path: Path, digest: str, size: int) -> None:
        actual, actual_size = hash_file(path)
        if actual != digest or actual_size != size:
            raise BlobContentConflict("existing content-addressed Blob differs")

    def ingest(self, source: Path, digest: str, size: int) -> tuple[bool, Path]:
        target = self.path_for(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self._verify(target, digest, size)
            return False, target
        staging_root = self.root / "staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        temporary = staging_root / f"blob-{uuid.uuid4().hex}"
        try:
            with Path(source).open("rb") as reader, temporary.open("xb") as writer:
                for chunk in iter(lambda: reader.read(CHUNK_SIZE), b""):
                    writer.write(chunk)
                writer.flush()
                if self.fsync_on_publish:
                    os.fsync(writer.fileno())
            self._verify(temporary, digest, size)
            try:
                os.link(temporary, target)
                created = True
            except FileExistsError:
                self._verify(target, digest, size)
                created = False
            temporary.unlink(missing_ok=True)
            if self.fsync_on_publish:
                descriptor = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return created, target
        finally:
            temporary.unlink(missing_ok=True)

    def verify(self, digest: str, size: int) -> bool:
        path = self.path_for(digest)
        if not path.is_file():
            return False
        self._verify(path, digest, size)
        return True
