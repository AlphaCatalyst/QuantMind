import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.services.engine.artifact_store.blob_store import ContentAddressedBlobStore
from backend.services.engine.artifact_store.errors import BlobContentConflict


def test_blob_publish_reuse_and_concurrency(tmp_path):
    store = ContentAddressedBlobStore(tmp_path, fsync_on_publish=False)
    source = tmp_path / "source"
    source.write_bytes(b"quantmind" * 10000)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    size = source.stat().st_size
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.ingest(source, digest, size), range(16)))
    assert sum(created for created, _ in results) == 1
    assert store.verify(digest, size)
    assert store.ingest(source, digest, size)[0] is False


def test_blob_conflict_is_fail_closed(tmp_path):
    store = ContentAddressedBlobStore(tmp_path, fsync_on_publish=False)
    source = tmp_path / "source"
    source.write_bytes(b"expected")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = store.path_for(digest)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"corrupt")
    with pytest.raises(BlobContentConflict):
        store.ingest(source, digest, source.stat().st_size)
