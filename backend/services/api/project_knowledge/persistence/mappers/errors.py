"""Safe, transport-neutral errors for Ledger Domain/ORM conversion."""

from __future__ import annotations


class LedgerMapperError(ValueError):
    """Base Mapper error with stable metadata and no rejected-object repr."""

    error_code = "LEDGER_MAPPER_ERROR"

    def __init__(
        self,
        safe_message: str,
        *,
        object_type: str,
        safe_identity: str | None = None,
        field_name: str | None = None,
        underlying_error_type: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.error_code = error_code or type(self).error_code
        self.object_type = object_type
        self.safe_identity = safe_identity
        self.field_name = field_name
        self.underlying_error_type = underlying_error_type
        self.safe_message = safe_message
        super().__init__(safe_message)

    def __str__(self) -> str:
        context = [self.error_code, self.object_type]
        if self.safe_identity is not None:
            context.append(self.safe_identity)
        if self.field_name is not None:
            context.append(self.field_name)
        return f"{'/'.join(context)}: {self.safe_message}"


class RecordToDomainError(LedgerMapperError):
    """Expected stored-value failure during ORM-to-Domain conversion."""

    error_code = "RECORD_TO_DOMAIN_ERROR"


class DomainToRecordError(LedgerMapperError):
    """Expected value/contract failure during Domain-to-ORM conversion."""

    error_code = "DOMAIN_TO_RECORD_ERROR"


class UnknownEnumValueError(RecordToDomainError):
    """Stored enum value does not exactly match the requested Domain Enum."""

    error_code = "UNKNOWN_ENUM"


class InvalidMapperValueError(LedgerMapperError):
    """A conversion utility received an unsupported value shape."""

    error_code = "INVALID_MAPPER_VALUE"


class MapperContractVersionError(DomainToRecordError):
    """A caller requested an unsupported Mapper contract version."""

    error_code = "MAPPER_CONTRACT_VERSION_UNSUPPORTED"
