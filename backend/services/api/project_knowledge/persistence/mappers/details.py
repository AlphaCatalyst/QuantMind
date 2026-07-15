"""Pure explicit mappings for the four Implementation Run detail records."""

from backend.services.api.project_knowledge.persistence.orm_detail_models import (
    ChangedFileRecord,
    ChangedSymbolRecord,
    ImplementationArtifactRecord,
    TestExecutionRecord,
)
from backend.services.engine.project_knowledge.domain.enums import (
    FileChangeType,
    SymbolChangeType,
    SymbolType,
    TestExecutionStatus,
)
from backend.services.engine.project_knowledge.domain.errors import LedgerDomainError
from backend.services.engine.project_knowledge.domain.models import (
    ChangedFile,
    ChangedSymbol,
    ImplementationArtifact,
    TestExecution,
)

from .common import (
    enum_from_storage,
    enum_to_storage,
    loaded_column,
    safe_record_identity,
    validate_parent_run_id,
)
from .errors import DomainToRecordError, LedgerMapperError, RecordToDomainError
from .identity import changed_file_record_id, changed_symbol_record_id


def _read(values: dict[str, object], name: str, object_type: str, identity: str | None) -> object:
    return loaded_column(values, name, object_type=object_type, identity=identity)


def _wrap_domain_error(exc: LedgerDomainError, object_type: str, identity: str | None):  # noqa: ANN201
    return RecordToDomainError(
        "stored values failed Domain validation",
        object_type=object_type,
        safe_identity=identity,
        field_name=exc.field,
        underlying_error_type=type(exc).__name__,
        error_code=exc.error_code,
    )


def _require_type(item: object, expected: type, object_type: str) -> None:
    if not isinstance(item, expected):
        raise DomainToRecordError(
            f"expected a {object_type} domain object",
            object_type=object_type,
            underlying_error_type=type(item).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )


def changed_file_to_record(
    implementation_run_id: str,
    item: ChangedFile,
) -> ChangedFileRecord:
    _require_type(item, ChangedFile, "ChangedFile")
    run_id = validate_parent_run_id(
        implementation_run_id, item.implementation_run_id, object_type="ChangedFile"
    )
    return ChangedFileRecord(
        changed_file_id=changed_file_record_id(
            implementation_run_id=run_id,
            path=item.path,
            change_type=item.change_type,
        ),
        implementation_run_id=run_id,
        path=item.path,
        change_type=enum_to_storage(
            item.change_type, field_name="change_type", object_type="ChangedFile"
        ),
        before_hash=item.before_hash,
        after_hash=item.after_hash,
        previous_path=item.previous_path,
    )


def changed_file_from_record(record: ChangedFileRecord) -> ChangedFile:
    object_type = "ChangedFile"
    if not isinstance(record, ChangedFileRecord):
        raise RecordToDomainError(
            "expected a ChangedFileRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("changed_file_id"))
    try:
        item = ChangedFile(
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            path=_read(values, "path", object_type, identity),
            change_type=enum_from_storage(
                FileChangeType,
                _read(values, "change_type", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="change_type",
            ),
            before_hash=_read(values, "before_hash", object_type, identity),
            after_hash=_read(values, "after_hash", object_type, identity),
            previous_path=_read(values, "previous_path", object_type, identity),
        )
        stored_id = _read(values, "changed_file_id", object_type, identity)
        expected_id = changed_file_record_id(
            implementation_run_id=item.implementation_run_id,
            path=item.path,
            change_type=item.change_type,
        )
        if stored_id != expected_id:
            raise RecordToDomainError(
                "stored technical identity does not match canonical fields",
                object_type=object_type,
                safe_identity=identity,
                field_name="changed_file_id",
                error_code="MAPPER_IDENTITY_MISMATCH",
            )
        return item
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _wrap_domain_error(exc, object_type, identity) from exc


def changed_symbol_to_record(
    implementation_run_id: str,
    item: ChangedSymbol,
) -> ChangedSymbolRecord:
    _require_type(item, ChangedSymbol, "ChangedSymbol")
    run_id = validate_parent_run_id(
        implementation_run_id, item.implementation_run_id, object_type="ChangedSymbol"
    )
    return ChangedSymbolRecord(
        changed_symbol_id=changed_symbol_record_id(
            implementation_run_id=run_id,
            file_path=item.file_path,
            qualified_name=item.qualified_name,
        ),
        implementation_run_id=run_id,
        file_path=item.file_path,
        qualified_name=item.qualified_name,
        symbol_type=enum_to_storage(
            item.symbol_type, field_name="symbol_type", object_type="ChangedSymbol"
        ),
        change_type=enum_to_storage(
            item.change_type, field_name="change_type", object_type="ChangedSymbol"
        ),
    )


def changed_symbol_from_record(record: ChangedSymbolRecord) -> ChangedSymbol:
    object_type = "ChangedSymbol"
    if not isinstance(record, ChangedSymbolRecord):
        raise RecordToDomainError(
            "expected a ChangedSymbolRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("changed_symbol_id"))
    try:
        item = ChangedSymbol(
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            file_path=_read(values, "file_path", object_type, identity),
            qualified_name=_read(values, "qualified_name", object_type, identity),
            symbol_type=enum_from_storage(
                SymbolType,
                _read(values, "symbol_type", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="symbol_type",
            ),
            change_type=enum_from_storage(
                SymbolChangeType,
                _read(values, "change_type", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="change_type",
            ),
        )
        stored_id = _read(values, "changed_symbol_id", object_type, identity)
        expected_id = changed_symbol_record_id(
            implementation_run_id=item.implementation_run_id,
            file_path=item.file_path,
            qualified_name=item.qualified_name,
        )
        if stored_id != expected_id:
            raise RecordToDomainError(
                "stored technical identity does not match canonical fields",
                object_type=object_type,
                safe_identity=identity,
                field_name="changed_symbol_id",
                error_code="MAPPER_IDENTITY_MISMATCH",
            )
        return item
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _wrap_domain_error(exc, object_type, identity) from exc


def test_execution_to_record(
    implementation_run_id: str,
    item: TestExecution,
) -> TestExecutionRecord:
    _require_type(item, TestExecution, "TestExecution")
    run_id = validate_parent_run_id(
        implementation_run_id, item.implementation_run_id, object_type="TestExecution"
    )
    return TestExecutionRecord(
        test_execution_id=item.test_execution_id,
        implementation_run_id=run_id,
        command=item.command,
        purpose=item.purpose,
        status=enum_to_storage(
            item.status, field_name="status", object_type="TestExecution"
        ),
        passed_count=item.passed_count,
        failed_count=item.failed_count,
        skipped_count=item.skipped_count,
        not_run_reason=item.not_run_reason,
        artifact_uri=item.artifact_uri,
        artifact_hash=item.artifact_hash,
    )


def test_execution_from_record(record: TestExecutionRecord) -> TestExecution:
    object_type = "TestExecution"
    if not isinstance(record, TestExecutionRecord):
        raise RecordToDomainError(
            "expected a TestExecutionRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("test_execution_id"))
    try:
        return TestExecution(
            test_execution_id=_read(values, "test_execution_id", object_type, identity),
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            command=_read(values, "command", object_type, identity),
            purpose=_read(values, "purpose", object_type, identity),
            status=enum_from_storage(
                TestExecutionStatus,
                _read(values, "status", object_type, identity),
                object_type=object_type,
                identity=identity,
                field_name="status",
            ),
            passed_count=_read(values, "passed_count", object_type, identity),
            failed_count=_read(values, "failed_count", object_type, identity),
            skipped_count=_read(values, "skipped_count", object_type, identity),
            not_run_reason=_read(values, "not_run_reason", object_type, identity),
            artifact_uri=_read(values, "artifact_uri", object_type, identity),
            artifact_hash=_read(values, "artifact_hash", object_type, identity),
        )
    except LedgerMapperError:
        raise
    except LedgerDomainError as exc:
        raise _wrap_domain_error(exc, object_type, identity) from exc


def implementation_artifact_to_record(
    implementation_run_id: str,
    item: ImplementationArtifact,
) -> ImplementationArtifactRecord:
    _require_type(item, ImplementationArtifact, "ImplementationArtifact")
    run_id = validate_parent_run_id(
        implementation_run_id,
        item.implementation_run_id,
        object_type="ImplementationArtifact",
    )
    return ImplementationArtifactRecord(
        artifact_id=item.artifact_id,
        implementation_run_id=run_id,
        artifact_type=item.artifact_type,
        path_or_uri=item.path_or_uri,
        content_hash=item.content_hash,
        schema_version=item.schema_version,
        size_bytes=item.size_bytes,
    )


def implementation_artifact_from_record(
    record: ImplementationArtifactRecord,
) -> ImplementationArtifact:
    object_type = "ImplementationArtifact"
    if not isinstance(record, ImplementationArtifactRecord):
        raise RecordToDomainError(
            "expected an ImplementationArtifactRecord",
            object_type=object_type,
            underlying_error_type=type(record).__name__,
            error_code="INVALID_OBJECT_TYPE",
        )
    values = vars(record)
    identity = safe_record_identity(values.get("artifact_id"))
    try:
        return ImplementationArtifact(
            artifact_id=_read(values, "artifact_id", object_type, identity),
            implementation_run_id=_read(values, "implementation_run_id", object_type, identity),
            artifact_type=_read(values, "artifact_type", object_type, identity),
            path_or_uri=_read(values, "path_or_uri", object_type, identity),
            content_hash=_read(values, "content_hash", object_type, identity),
            schema_version=_read(values, "schema_version", object_type, identity),
            size_bytes=_read(values, "size_bytes", object_type, identity),
        )
    except LedgerDomainError as exc:
        raise _wrap_domain_error(exc, object_type, identity) from exc
