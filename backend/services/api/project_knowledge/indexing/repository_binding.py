"""Explicit trusted binding from a logical repository ID to one checkout."""

from __future__ import annotations

from pathlib import Path
import subprocess

from backend.services.engine.project_knowledge.domain.validators import validate_identifier

from .errors import RepositoryBindingError
from .models import RepositoryBinding


def bind_repository(repository_id: str, repository_path: str | Path) -> RepositoryBinding:
    """Validate an explicit binding without inferring identity from local facts."""
    try:
        logical_id = validate_identifier(repository_id, field="repository_id")
    except ValueError as exc:
        raise RepositoryBindingError("logical repository ID is invalid") from exc
    supplied = Path(repository_path)
    if not supplied.is_absolute():
        raise RepositoryBindingError("repository path must be absolute")
    resolved = supplied.resolve()
    if not resolved.is_dir():
        raise RepositoryBindingError("repository path is not a directory")
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "rev-parse", "--show-toplevel"],
        cwd=resolved,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode or not result.stdout.strip():
        raise RepositoryBindingError("repository path is not a readable Git worktree")
    if Path(result.stdout.strip()).resolve() != resolved:
        raise RepositoryBindingError("repository path must name the Git worktree root")
    return RepositoryBinding(logical_id, resolved)
