"""Read-only Git-object evidence for committed Implementation Runs."""

from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath
import re
import subprocess
from typing import Iterable

from tools.quantmind2.validate_context_bootstrap import canonical_manifest_payload_hash

from .errors import GitEvidenceError, ManifestParseError
from .manifest_parser import ImplementationManifestParser, RUNS_PREFIX
from .manifest_v2 import canonical_json_hash, canonical_manifest_v2_payload_hash
from .models import (
    AnalyzedRun,
    BackfillPlan,
    DiscoveredRun,
    EvidenceCheck,
    GitConsistencyEvidence,
    RepositoryBinding,
)


_RUN_MANIFEST_RE = re.compile(
    r"^docs/quantmind2/implementation/runs/[0-9]{4}/[0-9]{4}-[0-9]{2}/"
    r"(?P<run_id>QM2-[A-Za-z0-9-]+-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7,12})/manifest\.json$"
)
_FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_MAX_GIT_OUTPUT = 16 * 1024 * 1024


def _resolved_status(source_status: str, containing_commit: str | None) -> tuple[str | None, str | None]:
    if source_status == "completed_uncommitted" and containing_commit:
        return "completed_committed", containing_commit
    if source_status == "partial_uncommitted" and containing_commit:
        return "partial_committed", containing_commit
    if source_status == "completed_committed":
        return source_status, containing_commit
    if source_status == "in_progress":
        return "running", None
    if source_status in {"failed", "blocked"}:
        return source_status, containing_commit
    return None, None


class GitSnapshot:
    """One explicit local binding and one immutable reachable Git commit."""

    def __init__(self, binding: RepositoryBinding, ref: str = "HEAD") -> None:
        self.binding = binding
        self.ref_commit = self._resolve_ref(ref)

    def _git(self, *args: str, max_output: int = _MAX_GIT_OUTPUT) -> bytes:
        env = os.environ.copy()
        env.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_OPTIONAL_LOCKS": "0",
            }
        )
        try:
            result = subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", *args],
                cwd=self.binding.repository_path,
                env=env,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitEvidenceError("Git evidence command could not complete") from exc
        if result.returncode:
            raise GitEvidenceError("Git evidence command failed")
        if len(result.stdout) > max_output:
            raise GitEvidenceError("Git evidence output exceeds the safe limit")
        return result.stdout

    def _resolve_ref(self, ref: str) -> str:
        if not isinstance(ref, str) or not ref or "\x00" in ref or len(ref) > 255:
            raise GitEvidenceError("Git ref is invalid", check="target_ref")
        output = self._git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
        commit = output.decode("ascii", "strict").strip()
        if not _FULL_COMMIT_RE.fullmatch(commit):
            raise GitEvidenceError("Git ref did not resolve to a full commit", check="target_ref")
        return commit

    def list_paths(self, prefix: str) -> tuple[str, ...]:
        output = self._git("ls-tree", "-rz", "--name-only", self.ref_commit, "--", prefix)
        paths = [item.decode("utf-8", "strict") for item in output.split(b"\0") if item]
        return tuple(sorted(paths))

    def read_blob(self, commit: str, path: str) -> bytes:
        return self._git("show", f"{commit}:{path}")

    def path_history(self, path: str) -> tuple[str, ...]:
        output = self._git("log", "--format=%H", self.ref_commit, "--", path)
        return tuple(line for line in output.decode("ascii").splitlines() if line)

    def path_additions(self, path: str) -> tuple[str, ...]:
        output = self._git("log", "--diff-filter=A", "--format=%H", self.ref_commit, "--", path)
        return tuple(line for line in output.decode("ascii").splitlines() if line)

    def object_exists(self, commit: str) -> bool:
        try:
            self._git("cat-file", "-e", f"{commit}^{{commit}}", max_output=1024)
        except GitEvidenceError:
            return False
        return True

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        try:
            self._git("merge-base", "--is-ancestor", ancestor, descendant, max_output=1024)
        except GitEvidenceError:
            return False
        return True

    def changed_files(self, base: str, containing: str) -> tuple[str, ...]:
        output = self._git("diff", "--name-only", "-z", base, containing, "--")
        return tuple(sorted(item.decode("utf-8", "strict") for item in output.split(b"\0") if item))

    def changed_statuses(self, base: str, containing: str) -> dict[str, str]:
        output = self._git("diff", "--name-status", base, containing, "--").decode("utf-8")
        statuses: dict[str, str] = {}
        for line in output.splitlines():
            columns = line.split("\t")
            if len(columns) == 2:
                statuses[columns[1]] = columns[0][0]
            elif len(columns) == 3 and columns[0].startswith(("R", "C")):
                statuses[columns[1]] = "D"
                statuses[columns[2]] = "A"
        return statuses

    def file_mode(self, commit: str, path: str) -> str | None:
        output = self._git("ls-tree", commit, "--", path).decode("utf-8").strip()
        if not output:
            return None
        return output.split(maxsplit=1)[0]

    def topological_positions(self) -> dict[str, int]:
        output = self._git("rev-list", "--topo-order", "--reverse", self.ref_commit)
        return {commit: index for index, commit in enumerate(output.decode("ascii").splitlines())}


def discover_runs(snapshot: GitSnapshot) -> tuple[DiscoveredRun, ...]:
    discovered: list[DiscoveredRun] = []
    seen: set[str] = set()
    for path in snapshot.list_paths(RUNS_PREFIX.as_posix()):
        if not path.endswith("/manifest.json"):
            continue
        match = _RUN_MANIFEST_RE.fullmatch(path)
        if match is None:
            raise GitEvidenceError("non-canonical Run manifest path exists", check="run_discovery")
        run_id = match.group("run_id")
        if run_id in seen:
            raise GitEvidenceError("duplicate Run ID exists in Git snapshot", run_id=run_id)
        seen.add(run_id)
        directory = str(PurePosixPath(path).parent)
        discovered.append(
            DiscoveredRun(run_id, directory, path, f"{directory}/report.md")
        )
    return tuple(sorted(discovered, key=lambda item: item.manifest_path))


class GitConsistencyService:
    def __init__(self, snapshot: GitSnapshot) -> None:
        self.snapshot = snapshot

    def validate(
        self,
        discovered: DiscoveredRun,
        parsed,
        manifest_bytes: bytes,
        report_bytes: bytes,
    ) -> GitConsistencyEvidence:
        payload = parsed.payload
        is_v2 = parsed.schema_version == "2.0.0"
        run_payload = payload["run"] if is_v2 else payload
        repository_payload = payload["repository"] if is_v2 else None
        integrity = payload["integrity"] if is_v2 else None
        checks: list[EvidenceCheck] = []

        def record(name: str, passed: bool, detail: str, *, mandatory: bool = True) -> None:
            checks.append(EvidenceCheck(name, mandatory, bool(passed), detail))

        binding_matches = (
            repository_payload["repository_id"] == self.snapshot.binding.repository_id
            if is_v2
            else True
        )
        record(
            "repository_binding",
            binding_matches,
            "explicit logical ID matches Manifest v2 repository identity"
            if is_v2
            else "explicit logical ID and local path supplied",
        )
        record("target_ref", True, f"resolved to {self.snapshot.ref_commit[:12]}")
        record("manifest_in_git", bool(manifest_bytes), "manifest blob exists in target snapshot")
        record("report_in_git", bool(report_bytes), "report blob exists in target snapshot")
        record("run_path", parsed.run_id == discovered.run_id, "Run ID and canonical directory agree")
        record(
            "report_hash",
            hashlib.sha256(report_bytes).hexdigest()
            == (integrity["report_sha256"] if is_v2 else payload["report_hash"]),
            "report SHA-256 checked against exact Git blob bytes",
        )
        record(
            "manifest_payload_hash",
            (
                canonical_manifest_v2_payload_hash(payload)
                == integrity["manifest_payload_sha256"]
                if is_v2
                else canonical_manifest_payload_hash(dict(payload))
                == payload["manifest_payload_hash"]
            ),
            f"canonical Manifest {'v2' if is_v2 else 'v1'} payload hash checked",
        )

        manifest_history = self.snapshot.path_history(discovered.manifest_path)
        report_history = self.snapshot.path_history(discovered.report_path)
        manifest_adds = self.snapshot.path_additions(discovered.manifest_path)
        report_adds = self.snapshot.path_additions(discovered.report_path)
        containing = manifest_adds[0] if len(manifest_adds) == 1 else None
        record("manifest_added_once", len(manifest_adds) == 1, "manifest must be added exactly once")
        record("report_added_once", len(report_adds) == 1, "report must be added exactly once")
        record(
            "paired_containing_commit",
            containing is not None and report_adds == (containing,),
            "manifest and report must first appear in the same commit",
        )
        record(
            "immutable_run_files",
            len(manifest_history) == 1 and len(report_history) == 1,
            "Run files must never be modified, deleted, or recreated",
        )
        if containing:
            record(
                "manifest_blob_immutable",
                self.snapshot.read_blob(containing, discovered.manifest_path) == manifest_bytes,
                "target and containing manifest blobs agree",
            )
            record(
                "report_blob_immutable",
                self.snapshot.read_blob(containing, discovered.report_path) == report_bytes,
                "target and containing report blobs agree",
            )
            record(
                "containing_reachable",
                self.snapshot.is_ancestor(containing, self.snapshot.ref_commit),
                "containing commit is reachable from target ref",
            )
        else:
            for name in ("manifest_blob_immutable", "report_blob_immutable", "containing_reachable"):
                record(name, False, "containing commit is unavailable")

        base = run_payload["base_commit"]
        base_exists = self.snapshot.object_exists(base)
        record("base_commit_exists", base_exists, f"base commit {base[:12]} exists")
        record(
            "base_is_ancestor",
            bool(containing and base_exists and self.snapshot.is_ancestor(base, containing)),
            "base commit must be an ancestor of containing commit",
        )
        declared_result = run_payload["result_commit"]
        result_ok = declared_result is None or declared_result == containing
        record(
            "result_commit",
            result_ok,
            "explicit result commit must equal containing commit; null uses pre-commit resolution",
        )

        actual_changed = self.snapshot.changed_files(base, containing) if containing and base_exists else ()
        declared_changed = (
            integrity["git_changed_paths"] if is_v2 else payload["changed_files"]
        )
        record(
            "changed_files",
            set(actual_changed) == set(declared_changed),
            "declared changed files equal base-to-containing Git diff",
        )
        statuses = self.snapshot.changed_statuses(base, containing) if containing and base_exists else {}
        actual_added = {path for path, status in statuses.items() if status == "A"}
        actual_deleted = {path for path, status in statuses.items() if status == "D"}
        record(
            "added_files",
            set(integrity["git_added_paths"] if is_v2 else payload["added_files"])
            == actual_added,
            "declared additions exactly equal Git diff additions",
        )
        record(
            "deleted_files",
            set(integrity["git_deleted_paths"] if is_v2 else payload["deleted_files"])
            == actual_deleted,
            "declared deletions exactly equal Git diff deletions",
        )
        modes = (
            self.snapshot.file_mode(containing, discovered.manifest_path) if containing else None,
            self.snapshot.file_mode(containing, discovered.report_path) if containing else None,
        )
        record("run_files_not_symlinks", all(mode in {"100644", "100755"} for mode in modes), "Run files are ordinary Git blobs")

        artifact_ok = True
        for artifact in payload["artifacts"]:
            artifact_path = artifact.get("path_or_uri") if is_v2 else artifact["path"]
            artifact_hash = artifact.get("content_hash") if is_v2 else artifact["hash"]
            if is_v2 and (
                artifact["location_kind"] != "repository_path" or artifact_hash is None
            ):
                continue
            try:
                blob = self.snapshot.read_blob(containing, artifact_path) if containing else b""
            except GitEvidenceError:
                artifact_ok = False
                break
            if hashlib.sha256(blob).hexdigest() != artifact_hash:
                artifact_ok = False
                break
        record("artifact_hashes", artifact_ok, "declared artifacts checked at containing commit")

        if is_v2:
            changed_file_hashes_ok = True
            changed_file_statuses_ok = True
            for item in payload["changed_files"]:
                expected_status = {
                    "added": "A", "modified": "M", "deleted": "D",
                    "renamed": "A", "unchanged": None,
                }[item["change_type"]]
                if expected_status is not None and statuses.get(item["path"]) != expected_status:
                    changed_file_statuses_ok = False
                if item["change_type"] == "renamed" and statuses.get(item["previous_path"]) != "D":
                    changed_file_statuses_ok = False
                try:
                    if item["before_hash"] is not None:
                        before_path = item["previous_path"] or item["path"]
                        before = self.snapshot.read_blob(base, before_path)
                        if hashlib.sha256(before).hexdigest() != item["before_hash"]:
                            changed_file_hashes_ok = False
                    if item["after_hash"] is not None:
                        after = self.snapshot.read_blob(containing, item["path"])
                        if hashlib.sha256(after).hexdigest() != item["after_hash"]:
                            changed_file_hashes_ok = False
                except GitEvidenceError:
                    changed_file_hashes_ok = False
            record(
                "changed_file_statuses",
                changed_file_statuses_ok,
                "structured ChangedFile types agree with Git statuses",
            )
            record(
                "changed_file_hashes",
                changed_file_hashes_ok,
                "structured ChangedFile hashes checked against base and containing blobs",
            )

            source_records = []
            for path in sorted(integrity["git_changed_paths"]):
                if path == run_payload["manifest_path"]:
                    source_records.append(
                        {"path": path, "sha256": None, "kind": "manifest_payload"}
                    )
                elif path in integrity["git_deleted_paths"]:
                    source_records.append({"path": path, "sha256": None, "kind": "deleted"})
                else:
                    try:
                        blob = self.snapshot.read_blob(containing, path) if containing else b""
                    except GitEvidenceError:
                        blob = b""
                    source_records.append(
                        {"path": path, "sha256": hashlib.sha256(blob).hexdigest(), "kind": "file"}
                    )
            record(
                "source_bundle_hash",
                canonical_json_hash(source_records) == integrity["source_bundle_sha256"],
                "v2 source bundle hash recomputed from committed Git blobs",
            )
            record(
                "git_diff_hash",
                canonical_json_hash(
                    {
                        "changed": integrity["git_changed_paths"],
                        "added": integrity["git_added_paths"],
                        "deleted": integrity["git_deleted_paths"],
                        "domain_changed_files": payload["changed_files"],
                    }
                )
                == integrity["git_diff_sha256"],
                "v2 structured Git diff declaration hash recomputed",
            )
        record(
            "execution_path_binding",
            True,
            "Manifest execution path retained only as informational evidence",
            mandatory=False,
        )

        resolved_status, resolved_result = _resolved_status(parsed.source_status, containing)
        return GitConsistencyEvidence(
            parsed.run_id,
            self.snapshot.binding.repository_id,
            self.snapshot.ref_commit,
            containing,
            parsed.source_status,
            resolved_status,
            resolved_result,
            actual_changed,
            tuple(checks),
        )


class ImplementationRunPlanner:
    """Discover and validate all Run blobs before any database write."""

    def __init__(self, snapshot: GitSnapshot, parser: ImplementationManifestParser | None = None) -> None:
        self.snapshot = snapshot
        self.parser = parser or ImplementationManifestParser()
        self.consistency = GitConsistencyService(snapshot)

    def plan(self, run_id: str | None = None) -> BackfillPlan:
        from .domain_bundle import DomainBundleBuilder

        runs: list[AnalyzedRun] = []
        for discovered in discover_runs(self.snapshot):
            if run_id is not None and discovered.run_id != run_id:
                continue
            try:
                manifest_bytes = self.snapshot.read_blob(self.snapshot.ref_commit, discovered.manifest_path)
                report_bytes = self.snapshot.read_blob(self.snapshot.ref_commit, discovered.report_path)
                parsed = self.parser.parse(
                    manifest_bytes,
                    manifest_path=discovered.manifest_path,
                    directory_run_id=discovered.run_id,
                )
                evidence = self.consistency.validate(
                    discovered, parsed, manifest_bytes, report_bytes
                )
                domain_build = DomainBundleBuilder(self.snapshot.binding).build(parsed, evidence)
                runs.append(AnalyzedRun(discovered, parsed, evidence, domain_build))
            except (GitEvidenceError, ManifestParseError) as exc:
                failed = GitConsistencyEvidence(
                    discovered.run_id,
                    self.snapshot.binding.repository_id,
                    self.snapshot.ref_commit,
                    None,
                    None,
                    None,
                    None,
                    (),
                    (EvidenceCheck("analysis", True, False, exc.error_code),),
                )
                runs.append(AnalyzedRun(discovered, None, failed, None, (exc.error_code,)))
        if run_id is not None and not runs:
            raise GitEvidenceError("requested Run ID does not exist", run_id=run_id)
        positions = self.snapshot.topological_positions()
        runs.sort(
            key=lambda item: (
                positions.get(item.evidence.containing_commit or "", 2**63),
                item.discovered.run_id,
            )
        )
        return BackfillPlan(self.snapshot.binding.repository_id, self.snapshot.ref_commit, tuple(runs))
