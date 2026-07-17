"""Reviewed, exact country-identity decisions for every normalized source."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Iterable, Mapping

import pandas as pd

from erhni.config import REPOSITORY_ROOT, SourcesConfig
from erhni.sources import resolve_source_path, validate_all


COUNTRY_MAP_COLUMNS = (
    "source",
    "source_name",
    "canonical_iso3",
    "display_name",
    "status",
    "reason",
)
REGION_COLUMNS = ("iso3", "display_name", "source_region", "display_region")
ALLOWED_SOURCES = frozenset({"whr", "aqli", "wdi"})
ALLOWED_STATUSES = frozenset({"include", "exclude", "aggregate"})
ISO3_RE = re.compile(r"^[A-Z]{3}$")


class CountryMapError(ValueError):
    """Raised when an identity decision is missing, duplicate, or malformed."""


@dataclass(frozen=True, slots=True)
class CountryDecision:
    source: str
    source_name: str
    iso3: str | None
    display_name: str
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class Coverage:
    missing: tuple[tuple[str, str], ...]
    duplicate: tuple[tuple[str, str], ...]


class CountryCrosswalk:
    """An exact lookup table; it deliberately provides no fuzzy-name fallback."""

    def __init__(self, decisions: Iterable[CountryDecision]) -> None:
        materialized = tuple(decisions)
        by_key: dict[tuple[str, str], CountryDecision] = {}
        duplicate: list[tuple[str, str]] = []
        for decision in materialized:
            key = (decision.source, decision.source_name)
            if key in by_key:
                duplicate.append(key)
            by_key[key] = decision
        if duplicate:
            rendered = ", ".join(f"{source}:{name}" for source, name in duplicate)
            raise CountryMapError(f"duplicate country-map decisions: {rendered}")
        self.decisions = materialized
        self._by_key = MappingProxyType(by_key)

    def resolve(self, source: str, source_name: str) -> CountryDecision:
        """Resolve one source token by exact equality only."""

        try:
            return self._by_key[(source, source_name)]
        except KeyError as error:
            raise CountryMapError(
                f"no explicit country decision for {source}:{source_name}"
            ) from error

    def coverage(
        self,
        raw_names: Mapping[str, Iterable[str]] | Iterable[tuple[str, str]],
    ) -> Coverage:
        """Report source identities without exactly one reviewed decision."""

        if isinstance(raw_names, Mapping):
            keys = {
                (source, source_name)
                for source, names in raw_names.items()
                for source_name in names
            }
        else:
            keys = set(raw_names)
        missing = tuple(sorted(keys - set(self._by_key)))
        counts: dict[tuple[str, str], int] = {}
        for decision in self.decisions:
            key = (decision.source, decision.source_name)
            counts[key] = counts.get(key, 0) + 1
        duplicate = tuple(sorted(key for key, count in counts.items() if count != 1))
        return Coverage(missing=missing, duplicate=duplicate)


def _required_text(row: Mapping[str, str], field: str, row_number: int) -> str:
    value = row.get(field, "")
    if value == "" or value.strip() != value:
        raise CountryMapError(f"row {row_number} has blank or untrimmed {field}")
    return value


def load_country_map(path: str | Path) -> CountryCrosswalk:
    """Load and validate the reviewed identity crosswalk."""

    source_path = Path(path)
    try:
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != COUNTRY_MAP_COLUMNS:
                raise CountryMapError("country map has unexpected columns")
            raw_rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise CountryMapError(f"cannot read country map {source_path}: {error}") from error
    if not raw_rows:
        raise CountryMapError("country map must contain decisions")

    decisions: list[CountryDecision] = []
    for row_number, row in enumerate(raw_rows, start=2):
        source = _required_text(row, "source", row_number)
        source_name = _required_text(row, "source_name", row_number)
        display_name = _required_text(row, "display_name", row_number)
        status = _required_text(row, "status", row_number)
        reason = _required_text(row, "reason", row_number)
        if source not in ALLOWED_SOURCES:
            raise CountryMapError(f"row {row_number} has invalid source: {source}")
        if status not in ALLOWED_STATUSES:
            raise CountryMapError(f"row {row_number} has invalid status: {status}")
        raw_iso3 = row.get("canonical_iso3", "")
        iso3 = raw_iso3 or None
        if iso3 is not None and not ISO3_RE.fullmatch(iso3):
            raise CountryMapError(f"row {row_number} has invalid canonical ISO3")
        if status in {"include", "aggregate"} and iso3 is None:
            raise CountryMapError(f"row {row_number} {status} decision has blank ISO3")
        if status == "exclude" and iso3 is not None:
            raise CountryMapError(f"row {row_number} exclusion must not assign an ISO3")
        decisions.append(
            CountryDecision(
                source=source,
                source_name=source_name,
                iso3=iso3,
                display_name=display_name,
                status=status,
                reason=reason,
            )
        )
    return CountryCrosswalk(decisions)


def load_regions(path: str | Path) -> pd.DataFrame:
    """Load the one-row-per-included-identity region review table."""

    source_path = Path(path)
    try:
        frame = pd.read_csv(source_path, dtype=str, keep_default_na=False)
    except (OSError, UnicodeError, pd.errors.ParserError) as error:
        raise CountryMapError(f"cannot read regions {source_path}: {error}") from error
    if tuple(frame.columns) != REGION_COLUMNS:
        raise CountryMapError("regions table has unexpected columns")
    if frame.empty:
        raise CountryMapError("regions table must contain reviewed identities")
    if frame.isin([""]).any().any():
        raise CountryMapError("regions table contains a blank decision")
    if not frame["iso3"].map(lambda value: bool(ISO3_RE.fullmatch(value))).all():
        raise CountryMapError("regions table contains an invalid ISO3")
    if frame["iso3"].duplicated().any():
        raise CountryMapError("regions table contains duplicate ISO3 rows")
    return frame


def _load_identity_column(path: Path, column: str, *, excel: bool = False) -> tuple[str, ...]:
    if excel:
        frame = pd.read_excel(path, sheet_name="Sheet1", usecols=[column])
    else:
        frame = pd.read_csv(
            path,
            usecols=[column],
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    values = frame[column].dropna().astype(str)
    if values.eq("").any():
        raise CountryMapError(f"{path.name} contains a blank {column} identity")
    return tuple(sorted(values.unique()))


def collect_source_identities(
    sources: SourcesConfig,
    *,
    repository_root: str | Path = REPOSITORY_ROOT,
    raw_dir: str | Path = "data/raw/external",
) -> Mapping[str, tuple[str, ...]]:
    """Collect identities only after all locked inputs pass source validation."""

    root = Path(repository_root).resolve()
    validate_all(sources, repository_root=root, raw_dir=raw_dir)
    whr_path = resolve_source_path(sources.whr, repository_root=root, raw_dir=raw_dir)
    aqli_path = resolve_source_path(sources.aqli, repository_root=root, raw_dir=raw_dir)
    country_lock = sources.lock("wdi_country_metadata")
    country_path = resolve_source_path(
        country_lock, repository_root=root, raw_dir=raw_dir
    )
    try:
        payload = json.loads(country_path.read_text(encoding="utf-8"))
        rows = payload[1]
        wdi_ids = {str(row["id"]) for row in rows}
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise CountryMapError("validated WDI country metadata cannot be read") from error
    for lock in sources.locks.values():
        if (
            lock.source_family not in {"wdi_current", "edgar_ar5_excl_lulucf"}
            or lock.expected_indicator in {None, "country"}
            or lock.relative_path.name.endswith(".metadata.json")
        ):
            continue
        observation_path = resolve_source_path(
            lock, repository_root=root, raw_dir=raw_dir
        )
        try:
            observation_rows = json.loads(
                observation_path.read_text(encoding="utf-8")
            )[1]
            for row in observation_rows:
                iso3 = str(row["countryiso3code"])
                country = row["country"]
                token = iso3 or str(country["id"])
                wdi_ids.add(token)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise CountryMapError(
                "validated WDI observations cannot be read for identity coverage"
            ) from error
    return MappingProxyType(
        {
            "whr": _load_identity_column(whr_path, "Country name", excel=True),
            "aqli": _load_identity_column(aqli_path, "id"),
            "wdi": tuple(sorted(wdi_ids)),
        }
    )
