from __future__ import annotations

import argparse

from .config import resolve_runtime_context
from .enums import ArtifactRuntimeMode
from .errors import ArtifactRuntimeError


BASELINE_INVENTORY_ID = (
    "sai_b0c038070f5e09a4f6ab261647c8686ef09c8e99bfc924afc2ced942c2370320"
)


def add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--artifact-runtime-mode",
        choices=tuple(item.value for item in ArtifactRuntimeMode),
        default=None,
        help="defaults to QUANTMIND_ARTIFACT_RUNTIME_MODE or store_required",
    )
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--cache-root", default=None)


def runtime_context_from_args(
    args, *, inventory_id: str | None = BASELINE_INVENTORY_ID
):
    return resolve_runtime_context(
        explicit_mode=getattr(args, "artifact_runtime_mode", None),
        explicit_store_root=getattr(args, "store_root", None),
        explicit_cache_root=getattr(args, "cache_root", None),
        inventory_id=inventory_id,
    )


def safe_error_payload(exc: Exception) -> dict[str, str]:
    """Return a bounded CLI error without physical paths or secret-bearing text."""
    if isinstance(exc, ArtifactRuntimeError):
        return {"status": "error", "error_code": exc.code, "message": str(exc)}
    return {
        "status": "error",
        "error_code": type(exc).__name__,
        "message": "Artifact Runtime operation failed; inspect local diagnostics",
    }
