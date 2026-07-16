from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
import re
from typing import Any

import pandas as pd

from .errors import InvalidMarketDataRequest, LegacyFeatureBindingError
from .symbol import normalize_symbol


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ColumnRole(str, Enum):
    KEY = "key"
    FEATURE = "feature"
    LABEL = "label"
    METADATA = "metadata"
    WEIGHT = "weight"
    FORBIDDEN = "forbidden"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FeatureAccessPolicy:
    research_features: tuple[str, ...]
    labels: tuple[str, ...]
    metadata: tuple[str, ...]
    forbidden: tuple[str, ...]
    unknown: tuple[str, ...]

    @classmethod
    def from_schema(cls, schema: "LegacyFeatureSchema") -> "FeatureAccessPolicy":
        roles = schema.role_map()
        return cls(
            research_features=schema.research_feature_columns,
            labels=schema.label_columns,
            metadata=tuple(name for name, role in roles.items() if role == ColumnRole.METADATA.value),
            forbidden=tuple(name for name, role in roles.items() if role in {ColumnRole.FORBIDDEN.value, ColumnRole.WEIGHT.value}),
            unknown=schema.unknown_columns,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_features": list(self.research_features),
            "labels": list(self.labels),
            "metadata": list(self.metadata),
            "forbidden": list(self.forbidden),
            "unknown": list(self.unknown),
            "default_view": "keys_plus_research_features",
            "label_access": "explicit_reader_only",
        }


@dataclass(frozen=True)
class LegacyFeatureSourceBinding:
    source_id: str
    local_root: Path
    loader_id: str
    source_schema_version: str = "quantmind-model-features-v1"

    def __post_init__(self) -> None:
        for field_name in ("source_id", "loader_id", "source_schema_version"):
            value = str(getattr(self, field_name) or "").strip()
            if not _IDENTIFIER.fullmatch(value):
                raise LegacyFeatureBindingError(f"invalid {field_name}")
            object.__setattr__(self, field_name, value)
        root = Path(self.local_root).expanduser().resolve()
        object.__setattr__(self, "local_root", root)


@dataclass(frozen=True)
class LegacyFeatureRequest:
    source_id: str
    years: tuple[int, ...]
    start_date: date
    end_date: date
    symbols: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    include_labels: bool = False
    symbol_limit: int | None = None

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise InvalidMarketDataRequest("start_date must not exceed end_date")
        if not self.years:
            raise InvalidMarketDataRequest("at least one source year is required")
        years = tuple(int(item) for item in self.years)
        if len(set(years)) != len(years):
            raise InvalidMarketDataRequest("source years must not contain duplicates")
        if any(year < 1900 or year > 2200 for year in years):
            raise InvalidMarketDataRequest("source year is invalid")
        object.__setattr__(self, "years", tuple(sorted(years)))
        symbols = tuple(sorted({normalize_symbol(item) for item in self.symbols}))
        object.__setattr__(self, "symbols", symbols)
        columns = tuple(dict.fromkeys(str(item).strip() for item in self.columns if str(item).strip()))
        object.__setattr__(self, "columns", columns)
        if self.symbol_limit is not None and self.symbol_limit < 1:
            raise InvalidMarketDataRequest("symbol_limit must be positive")
        if symbols and self.symbol_limit is not None:
            raise InvalidMarketDataRequest("symbols and symbol_limit are mutually exclusive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "years": list(self.years),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "symbols": list(self.symbols),
            "columns": list(self.columns),
            "include_labels": self.include_labels,
            "symbol_limit": self.symbol_limit,
        }


@dataclass(frozen=True)
class LegacyFeatureSchema:
    column_order: tuple[str, ...]
    column_dtypes: tuple[tuple[str, str], ...]
    column_roles: tuple[tuple[str, ColumnRole], ...]
    research_feature_columns: tuple[str, ...]
    label_columns: tuple[str, ...]
    unknown_columns: tuple[str, ...]

    def role_map(self) -> dict[str, str]:
        return {name: role.value for name, role in self.column_roles}

    def dtype_map(self) -> dict[str, str]:
        return dict(self.column_dtypes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_order": list(self.column_order),
            "column_dtypes": self.dtype_map(),
            "column_roles": self.role_map(),
            "research_feature_columns": list(self.research_feature_columns),
            "label_columns": list(self.label_columns),
            "unknown_columns": list(self.unknown_columns),
        }


@dataclass(frozen=True)
class LegacyFeatureProbeResult:
    provider_id: str
    provider_version: str
    source_id: str
    loader_id: str
    available: bool
    missing_configuration: tuple[str, ...] = ()
    safe_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "source_id": self.source_id,
            "loader_id": self.loader_id,
            "available": self.available,
            "missing_configuration": list(self.missing_configuration),
            "safe_error": self.safe_error,
        }


@dataclass(frozen=True)
class LegacyFeatureInventory:
    source_id: str
    loader_id: str
    source_schema_version: str
    files: tuple[dict[str, Any], ...]
    schema: LegacyFeatureSchema

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "loader_id": self.loader_id,
            "source_schema_version": self.source_schema_version,
            "files": list(self.files),
            "schema": self.schema.to_dict(),
        }


@dataclass(frozen=True)
class LegacyFeatureBatch:
    provider_id: str
    provider_version: str
    request: LegacyFeatureRequest
    frame: pd.DataFrame
    inventory: LegacyFeatureInventory
    selected_symbols: tuple[str, ...]
    symbol_selection_rule: str
