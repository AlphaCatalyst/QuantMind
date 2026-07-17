from enum import Enum


class ArtifactRuntimeMode(str, Enum):
    LEGACY_LOCAL = "legacy_local"
    STORE_PREFERRED = "store_preferred"
    STORE_REQUIRED = "store_required"


class LocalPathPurpose(str, Enum):
    LEGACY_INPUT = "legacy_input"
    CACHE = "cache"
    STAGING = "staging"
    GIT_CONTROL = "git_control"
    TEST_FIXTURE = "test_fixture"
