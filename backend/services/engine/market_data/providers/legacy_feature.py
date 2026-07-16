from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow.parquet as pq

from ..errors import (
    LegacyFeatureAccessError,
    LegacyFeatureBindingError,
    LegacyFeatureSchemaError,
    ProviderUnavailableError,
)
from ..legacy_models import (
    ColumnRole,
    LegacyFeatureBatch,
    LegacyFeatureInventory,
    LegacyFeatureProbeResult,
    LegacyFeatureRequest,
    LegacyFeatureSchema,
    LegacyFeatureSourceBinding,
)


KEY_COLUMNS = ("symbol", "trade_date")
EVIDENCED_LABEL_COLUMNS = {"label"}
EVIDENCED_WEIGHT_COLUMNS = {"weight"}
EVIDENCED_METADATA_COLUMNS = {"split", "year"}
RESERVED_FORBIDDEN_COLUMNS = {
    "target", "future_return", "future_return_1d", "future_return_5d",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LegacyFeatureProvider:
    """Read-only adapter for the annual Parquet consumed by QuantMind training."""

    provider_id = "legacy-feature-parquet"
    provider_version = "legacy-feature-provider-v1"

    def __init__(self, binding: LegacyFeatureSourceBinding, catalog_path: Path) -> None:
        self.binding = binding
        self.catalog_path = Path(catalog_path).resolve()
        self._feature_allowlist = self._load_feature_allowlist()

    def _load_feature_allowlist(self) -> tuple[str, ...]:
        try:
            payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            keys: list[str] = []
            for category in payload["categories"]:
                for feature in category.get("features", []):
                    key = str(feature.get("key") or "").strip()
                    if feature.get("enabled", True) and key and key not in keys:
                        keys.append(key)
            if not keys:
                raise ValueError("empty catalog")
            return tuple(keys)
        except Exception as exc:
            raise LegacyFeatureBindingError("feature catalog is unavailable or invalid") from exc

    def probe(self) -> LegacyFeatureProbeResult:
        missing = []
        if not self.binding.local_root.is_dir():
            missing.append("source_root")
        if not self.catalog_path.is_file():
            missing.append("feature_catalog")
        return LegacyFeatureProbeResult(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            source_id=self.binding.source_id,
            loader_id=self.binding.loader_id,
            available=not missing,
            missing_configuration=tuple(missing),
            safe_error=None if not missing else "Legacy feature source binding is unavailable",
        )

    def _source_file(self, year: int) -> tuple[Path, str]:
        relative = Path(f"model_features_{year}.parquet")
        path = (self.binding.local_root / relative).resolve()
        if self.binding.local_root not in path.parents:
            raise LegacyFeatureBindingError("source path escapes binding root")
        if not path.is_file():
            raise ProviderUnavailableError(f"bound annual feature file is missing for year {year}")
        return path, relative.as_posix()

    @staticmethod
    def _iter_key_batches(path: Path) -> Iterator[pd.DataFrame]:
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(columns=list(KEY_COLUMNS), batch_size=131072):
            yield batch.to_pandas()

    def _build_schema(self, arrow_schema) -> LegacyFeatureSchema:  # noqa: ANN001
        names = tuple(arrow_schema.names)
        if not set(KEY_COLUMNS).issubset(names):
            raise LegacyFeatureSchemaError("source is missing symbol or trade_date")
        roles: list[tuple[str, ColumnRole]] = []
        for name in names:
            if name in KEY_COLUMNS:
                role = ColumnRole.KEY
            elif name in self._feature_allowlist:
                role = ColumnRole.FEATURE
            elif name in EVIDENCED_LABEL_COLUMNS:
                role = ColumnRole.LABEL
            elif name in EVIDENCED_WEIGHT_COLUMNS:
                role = ColumnRole.WEIGHT
            elif name in EVIDENCED_METADATA_COLUMNS:
                role = ColumnRole.METADATA
            elif name in RESERVED_FORBIDDEN_COLUMNS:
                role = ColumnRole.FORBIDDEN
            else:
                role = ColumnRole.UNKNOWN
            roles.append((name, role))
        role_map = dict(roles)
        return LegacyFeatureSchema(
            column_order=names,
            column_dtypes=tuple((field.name, str(field.type)) for field in arrow_schema),
            column_roles=tuple(roles),
            research_feature_columns=tuple(
                name for name in self._feature_allowlist if role_map.get(name) is ColumnRole.FEATURE
            ),
            label_columns=tuple(name for name, role in roles if role is ColumnRole.LABEL),
            unknown_columns=tuple(name for name, role in roles if role is ColumnRole.UNKNOWN),
        )

    def discover(self, years: tuple[int, ...]) -> LegacyFeatureInventory:
        probe = self.probe()
        if not probe.available:
            raise ProviderUnavailableError(probe.safe_error or "legacy feature provider unavailable")
        if len(set(years)) != len(years):
            raise LegacyFeatureBindingError("duplicate source year")
        files: list[dict] = []
        reference_schema = None
        reference_signature = None
        for year in sorted(years):
            path, relative = self._source_file(year)
            parquet = pq.ParquetFile(path)
            schema = self._build_schema(parquet.schema_arrow)
            signature = (schema.column_order, schema.column_dtypes)
            if reference_signature is not None and signature != reference_signature:
                raise LegacyFeatureSchemaError("annual source schema or column order drift")
            reference_schema = reference_schema or schema
            reference_signature = reference_signature or signature
            date_min = None
            date_max = None
            symbols: set[str] = set()
            for keys in self._iter_key_batches(path):
                dates = pd.to_datetime(keys["trade_date"], errors="coerce")
                current_min = dates.min()
                current_max = dates.max()
                date_min = current_min if date_min is None or current_min < date_min else date_min
                date_max = current_max if date_max is None or current_max > date_max else date_max
                symbols.update(keys["symbol"].dropna().astype(str).tolist())
            files.append({
                "file_relative_path": relative,
                "year": int(year),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "row_count": parquet.metadata.num_rows,
                "column_names": list(schema.column_order),
                "column_dtypes": schema.dtype_map(),
                "date_min": date_min.date().isoformat() if date_min is not None else None,
                "date_max": date_max.date().isoformat() if date_max is not None else None,
                "symbol_count": len(symbols),
            })
        if reference_schema is None:
            raise ProviderUnavailableError("no annual feature files were discovered")
        return LegacyFeatureInventory(
            source_id=self.binding.source_id,
            loader_id=self.binding.loader_id,
            source_schema_version=self.binding.source_schema_version,
            files=tuple(files),
            schema=reference_schema,
        )

    def _select_symbols(self, request: LegacyFeatureRequest) -> tuple[tuple[str, ...], str]:
        if request.symbols:
            return request.symbols, "explicit-symbols-v1"
        candidates: set[str] = set()
        for year in request.years:
            path, _ = self._source_file(year)
            for keys in self._iter_key_batches(path):
                dates = pd.to_datetime(keys["trade_date"], errors="coerce").dt.date
                mask = (dates >= request.start_date) & (dates <= request.end_date)
                candidates.update(keys.loc[mask, "symbol"].dropna().astype(str).tolist())
        selected = tuple(sorted(candidates))
        if request.symbol_limit is not None:
            selected = selected[:request.symbol_limit]
            rule = f"sorted-symbol-prefix-limit-{request.symbol_limit}-v1"
        else:
            rule = "all-bound-source-symbols-v1"
        return selected, rule

    def read(self, request: LegacyFeatureRequest) -> LegacyFeatureBatch:
        if request.source_id != self.binding.source_id:
            raise LegacyFeatureBindingError("request source_id differs from explicit binding")
        inventory = self.discover(request.years)
        schema = inventory.schema
        allowed = set(schema.research_feature_columns)
        feature_columns = request.columns or schema.research_feature_columns
        denied = [name for name in feature_columns if name not in allowed]
        if denied:
            raise LegacyFeatureAccessError("requested columns are not research features")
        read_columns = [*KEY_COLUMNS, *feature_columns]
        if request.include_labels:
            read_columns.extend(schema.label_columns)
        read_columns = list(dict.fromkeys(read_columns))
        selected_symbols, selection_rule = self._select_symbols(request)
        selected_set = set(selected_symbols)
        chunks: list[pd.DataFrame] = []
        for year in request.years:
            path, _ = self._source_file(year)
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(columns=read_columns, batch_size=65536):
                frame = batch.to_pandas()
                dates = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date
                mask = (
                    (dates >= request.start_date)
                    & (dates <= request.end_date)
                    & frame["symbol"].astype(str).isin(selected_set)
                )
                if mask.any():
                    chunks.append(frame.loc[mask, read_columns].copy())
        if chunks:
            result = pd.concat(chunks, ignore_index=True)
            result = result.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
        else:
            result = pd.DataFrame(columns=read_columns)
        return LegacyFeatureBatch(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            request=request,
            frame=result,
            inventory=inventory,
            selected_symbols=selected_symbols,
            symbol_selection_rule=selection_rule,
        )
