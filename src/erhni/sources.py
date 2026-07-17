"""Checksum-verified acquisition and fail-closed source schema validation."""

from __future__ import annotations

import argparse
import csv
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
from typing import Callable, Iterable, Mapping, Sequence
from urllib.error import URLError
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

import pandas as pd

from erhni.config import REPOSITORY_ROOT, SourceLock, SourcesConfig, load_sources
from erhni.hashing import sha256_file


YEARS = (2016, 2017, 2018)
ISO3_RE = re.compile(r"^[A-Z]{3}$")
WDI_CURRENT_FAMILIES = frozenset({"wdi_current", "edgar_ar5_excl_lulucf"})
DS57_OBSERVATION_COLUMNS = (
    "Country Name",
    "Country Code",
    "Indicator Name",
    "Indicator Code",
    *(str(year) for year in range(1960, 2026)),
)
DS57_INDICATOR_COLUMNS = (
    "INDICATOR_CODE",
    "INDICATOR_NAME",
    "SOURCE_NOTE",
    "SOURCE_ORGANIZATION",
)
DS57_COUNTRY_COLUMNS = (
    "Country Code",
    "Region",
    "IncomeGroup",
    "SpecialNotes",
    "TableName",
)
DS57_ARCHIVE_ONLY_CODES = frozenset(
    {"CNI", "EEC", "ISD", "LIO", "LIX", "LSA", "OEC", "SXN", "YMD"}
)
Downloader = Callable[[str], bytes]


class SourceError(RuntimeError):
    """Base class for acquisition and validation failures."""


class SourceAcquisitionError(SourceError):
    """Raised when locked bytes cannot be retrieved."""


class SourceIntegrityError(SourceError):
    """Raised when bytes do not match their locked SHA-256 digest."""


class SourceSchemaError(SourceError):
    """Raised when a pinned source no longer has its expected schema."""


class SourceFamilyError(SourceSchemaError):
    """Raised when bytes are passed to a parser for another source family."""


def _default_downloader(url: str) -> bytes:
    try:
        with urlopen(url, timeout=60) as response:  # noqa: S310 - URLs are canonical locks
            return response.read()
    except (OSError, URLError) as error:
        raise SourceAcquisitionError(f"source unavailable: {url}: {error}") from error


def _verify_hash(path: Path, lock: SourceLock) -> str:
    try:
        observed = sha256_file(path)
    except OSError as error:
        raise SourceAcquisitionError(
            f"cannot read source {lock.key}: {error}"
        ) from error
    if observed != lock.sha256:
        raise SourceIntegrityError(
            f"sha256 mismatch for {lock.key}: expected {lock.sha256}, observed {observed}"
        )
    return observed


def _acquire_to(lock: SourceLock, destination: Path, downloader: Downloader) -> Path:
    if destination.exists():
        try:
            _verify_hash(destination, lock)
        except SourceIntegrityError:
            pass
        else:
            return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    try:
        try:
            content = downloader(lock.url)
        except SourceError:
            raise
        except Exception as error:
            raise SourceAcquisitionError(
                f"source unavailable for {lock.key}: {error}"
            ) from error
        part.write_bytes(content)
        observed = sha256_file(part)
        if observed != lock.sha256:
            raise SourceIntegrityError(
                f"sha256 mismatch for {lock.key}: expected {lock.sha256}, observed {observed}"
            )
        os.replace(part, destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return destination


def acquire_one(
    lock: SourceLock,
    repository_root: str | Path,
    *,
    raw_dir: str | Path | None = None,
    downloader: Downloader = _default_downloader,
) -> Path:
    """Acquire one lock beneath a root, replacing its destination only on a hash match."""

    root = Path(repository_root)
    destination = (
        root / lock.relative_path
        if lock.redistributable
        else resolve_source_path(
            lock,
            repository_root=root,
            raw_dir=raw_dir or root / "data/raw/external",
        )
    )
    return _acquire_to(lock, destination, downloader)


def _restricted_destination(lock: SourceLock, root: Path, raw_dir: str | Path) -> Path:
    raw = Path(raw_dir)
    if not raw.is_absolute():
        raw = root / raw
    raw = raw.resolve()
    destination = (raw / lock.relative_path.name).resolve()
    canonical = root / "data/raw/external"
    canonical_resolved = canonical.resolve()

    if destination.is_relative_to(root):
        safe_in_repo = (
            canonical_resolved == canonical
            and raw == canonical
            and destination.parent == canonical
        )
        if not safe_in_repo:
            raise SourceAcquisitionError(
                f"restricted destination is not the ignored repository raw root: {destination}"
            )
    return destination


def resolve_source_path(
    lock: SourceLock,
    *,
    repository_root: str | Path = REPOSITORY_ROOT,
    raw_dir: str | Path = "data/raw/external",
) -> Path:
    """Resolve public snapshots and restricted raw inputs into separate locations."""

    root = Path(repository_root).resolve()
    if lock.redistributable:
        return root / lock.relative_path
    return _restricted_destination(lock, root, raw_dir)


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise SourceSchemaError(
            f"{label} missing required columns: {', '.join(missing)}"
        )


def _read_tabular(
    path: Path, *, whr: bool = False, preserve_tokens: bool = False
) -> pd.DataFrame:
    try:
        if path.suffix.lower() == ".xls":
            if not whr:
                raise SourceFamilyError(f"unexpected Excel source: {path.name}")
            workbook = pd.ExcelFile(path, engine="xlrd")
            if "Sheet1" not in workbook.sheet_names:
                raise SourceSchemaError("WHR annual workbook must contain Sheet1")
            return pd.read_excel(workbook, sheet_name="Sheet1")
        if preserve_tokens:
            return pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
            )
        return pd.read_csv(path)
    except SourceError:
        raise
    except Exception as error:
        raise SourceSchemaError(f"cannot parse {path.name}: {error}") from error


def read_whr_annual(path: str | Path, *, years: Sequence[int] = YEARS) -> pd.DataFrame:
    """Read only direct annual WHR Life Ladder observations."""

    frame = _read_tabular(Path(path), whr=True)
    required = ("Country name", "year", "Life Ladder")
    _require_columns(frame, required, "WHR annual table")
    selected = frame.loc[:, required].rename(
        columns={"Country name": "source_name", "Life Ladder": "life_ladder"}
    )
    selected["year"] = pd.to_numeric(selected["year"], errors="coerce")
    selected["life_ladder"] = pd.to_numeric(selected["life_ladder"], errors="coerce")
    selected = selected[selected["year"].isin(years)].copy()
    if selected[["source_name", "year", "life_ladder"]].isna().any().any():
        raise SourceSchemaError("WHR annual fields contain blanks or nonnumeric values")
    selected["year"] = selected["year"].astype(int)
    if selected.duplicated(["source_name", "year"]).any():
        raise SourceSchemaError("WHR annual table contains duplicate country-year rows")
    if set(selected["year"]) != set(years):
        raise SourceSchemaError(
            "WHR annual table does not contain every configured year"
        )
    return selected.reset_index(drop=True)


def read_aqli(path: str | Path, *, years: Sequence[int] = YEARS) -> pd.DataFrame:
    """Read direct AQLI WHO-benchmark fields, retaining zeros and excluding blanks."""

    frame = _read_tabular(Path(path), preserve_tokens=True)
    year_columns = [f"who{year}" for year in years]
    required = ["id", "whostandard", *year_columns]
    _require_columns(frame, required, "AQLI country data")
    selected = frame.loc[:, required].copy()
    ids = selected["id"].astype(str)
    if not ids.map(lambda value: bool(ISO3_RE.fullmatch(value))).all():
        raise SourceSchemaError("AQLI id values must be uppercase ISO3 codes")
    if ids.duplicated().any():
        raise SourceSchemaError("AQLI contains duplicate id rows")
    benchmark = pd.to_numeric(selected["whostandard"], errors="coerce")
    if benchmark.isna().any() or not (benchmark == 5).all():
        raise SourceSchemaError("AQLI whostandard must equal 5 for every row")
    for column in year_columns:
        original = selected[column]
        blank = original.astype(str).str.strip().eq("")
        numeric = pd.to_numeric(original.mask(blank), errors="coerce")
        invalid = ~blank & numeric.isna()
        if invalid.any():
            raise SourceSchemaError(f"AQLI {column} contains nonnumeric values")
        if not numeric.dropna().map(math.isfinite).all():
            raise SourceSchemaError(f"AQLI {column} contains non-finite values")
        if (numeric.dropna() < 0).any():
            raise SourceSchemaError(f"AQLI {column} contains negative values")
        selected[column] = numeric
    long = selected.drop(columns="whostandard").melt(
        id_vars="id", var_name="year", value_name="aqli_years_lost"
    )
    long = long.dropna(subset=["aqli_years_lost"])
    long["year"] = long["year"].str.removeprefix("who").astype(int)
    long = long.rename(columns={"id": "iso3"})
    if long.duplicated(["iso3", "year"]).any():
        raise SourceSchemaError("AQLI contains duplicate ISO3-year rows")
    return long.loc[:, ["iso3", "year", "aqli_years_lost"]].reset_index(drop=True)


def _load_wdi_json(path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceSchemaError(f"source is not valid WDI JSON: {path.name}") from error
    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not isinstance(payload[0], dict)
        or not isinstance(payload[1], list)
        or not all(isinstance(row, dict) for row in payload[1])
    ):
        raise SourceSchemaError("WDI JSON must contain one header and one row list")
    return payload[0], payload[1]


def read_wdi_observations(
    path: str | Path,
    lock: SourceLock,
    *,
    years: Sequence[int] = YEARS,
    expected_lastupdated: str | None = None,
) -> pd.DataFrame:
    """Validate and normalize one current WDI observation response."""

    if lock.source_family not in WDI_CURRENT_FAMILIES:
        raise SourceFamilyError(
            f"WDI successor JSON parser cannot read family {lock.source_family}"
        )
    if lock.expected_indicator in {None, "country"}:
        raise SourceFamilyError("WDI observation parser requires an indicator lock")
    source_path = Path(path)
    if source_path.suffix.lower() == ".zip":
        raise SourceFamilyError("WDI successor JSON parser cannot read an archive ZIP")
    header, rows = _load_wdi_json(source_path)
    if str(header.get("sourceid")) != lock.expected_source_id:
        raise SourceSchemaError("unexpected WDI source ID")
    if (
        expected_lastupdated is not None
        and header.get("lastupdated") != expected_lastupdated
    ):
        raise SourceSchemaError("unexpected WDI lastupdated release")
    normalized = []
    for row in rows:
        indicator = row.get("indicator")
        if (
            not isinstance(indicator, dict)
            or indicator.get("id") != lock.expected_indicator
        ):
            raise SourceSchemaError("unexpected WDI indicator")
        iso3 = row.get("countryiso3code")
        if iso3 == "":
            continue
        if not isinstance(iso3, str) or not ISO3_RE.fullmatch(iso3):
            raise SourceSchemaError("WDI observation has invalid ISO3 code")
        try:
            year = int(str(row.get("date")))
        except ValueError as error:
            raise SourceSchemaError("WDI observation has invalid year") from error
        if year not in years:
            raise SourceSchemaError("WDI observation contains a year outside the lock")
        country = row.get("country")
        if not isinstance(country, dict) or not isinstance(country.get("value"), str):
            raise SourceSchemaError("WDI observation has invalid country metadata")
        value = row.get("value")
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise SourceSchemaError("WDI observation value must be numeric or null")
        normalized.append(
            {
                "country_name": country["value"],
                "iso3": iso3,
                "year": year,
                "indicator": lock.expected_indicator,
                "value": value,
                "unit": lock.unit,
                "source_id": lock.expected_source_id,
            }
        )
    frame = pd.DataFrame.from_records(normalized)
    if frame.empty:
        raise SourceSchemaError("WDI observation response has no rows")
    if frame.duplicated(["iso3", "year"]).any():
        raise SourceSchemaError("WDI observation contains duplicate ISO3-year rows")
    if set(frame["year"]) != set(years):
        raise SourceSchemaError(
            "WDI observation does not contain every configured year"
        )
    if "WLD" not in set(frame["iso3"]):
        raise SourceSchemaError("WDI observation does not contain WLD")
    return frame


def read_wdi_metadata(path: str | Path, lock: SourceLock) -> dict[str, object]:
    """Validate one WDI indicator metadata response and its GHG semantics."""

    if lock.source_family not in WDI_CURRENT_FAMILIES:
        raise SourceFamilyError(
            f"WDI metadata parser cannot read family {lock.source_family}"
        )
    _, rows = _load_wdi_json(Path(path))
    if len(rows) != 1 or rows[0].get("id") != lock.expected_indicator:
        raise SourceSchemaError("unexpected WDI metadata indicator")
    row = rows[0]
    source = row.get("source")
    if not isinstance(source, dict) or str(source.get("id")) != lock.expected_source_id:
        raise SourceSchemaError("unexpected WDI metadata source ID")
    name = row.get("name")
    note = row.get("sourceNote")
    if not isinstance(name, str) or not isinstance(note, str):
        raise SourceSchemaError("WDI metadata requires name and sourceNote")
    summary: dict[str, object] = {
        "rows": 1,
        "source_id": lock.expected_source_id,
        "indicator": lock.expected_indicator,
        "unit": lock.unit,
    }
    if lock.source_family == "edgar_ar5_excl_lulucf":
        name_semantics = name.lower()
        note_semantics = note.lower()
        if "mt co2e" not in name_semantics:
            raise SourceSchemaError("successor GHG metadata must state Mt CO2e")
        if "ar5" not in note_semantics:
            raise SourceSchemaError("successor GHG metadata must state AR5")
        contradictory_standardization = re.search(
            r"\bnot\s+standardized\s+to\s+carbon dioxide equivalent values\b",
            note_semantics,
        )
        affirmative_standardization = re.search(
            r"\bstandardized\s+to\s+carbon dioxide equivalent values\b",
            note_semantics,
        )
        if contradictory_standardization is not None:
            raise SourceSchemaError(
                "successor GHG metadata contradicts CO2-equivalent standardization"
            )
        if affirmative_standardization is None:
            raise SourceSchemaError(
                "successor GHG metadata must state CO2-equivalent standardization"
            )
        contradiction = re.search(
            r"\b(?:does\s+not\s+exclude|not\s+excluding)\b[^.]*\blulucf\b",
            note_semantics,
        )
        affirmative_exclusion = re.search(
            r"\b(?:excludes|excluding)\b[^.]{0,200}\blulucf\b",
            note_semantics,
        )
        if contradiction is not None:
            raise SourceSchemaError(
                "successor GHG metadata contradicts the required exclude LULUCF boundary"
            )
        if affirmative_exclusion is None:
            raise SourceSchemaError("successor GHG metadata must exclude LULUCF")
        summary.update(
            {
                "unit": "Mt CO2e",
                "assessment": "AR5",
                "boundary": "excludes LULUCF",
                "already_co2_equivalent": lock.expected_indicator
                in {"EN.GHG.CH4.MT.CE.AR5", "EN.GHG.N2O.MT.CE.AR5"},
            }
        )
    return summary


def _read_wdi_country_metadata(path: Path, lock: SourceLock) -> dict[str, object]:
    _, rows = _load_wdi_json(path)
    ids: list[str] = []
    for row in rows:
        iso3 = row.get("id")
        region = row.get("region")
        if not isinstance(iso3, str) or not ISO3_RE.fullmatch(iso3):
            raise SourceSchemaError("WDI country metadata has invalid ISO3 code")
        if not isinstance(region, dict) or not isinstance(region.get("value"), str):
            raise SourceSchemaError("WDI country metadata has invalid region")
        ids.append(iso3)
    if len(ids) != len(set(ids)):
        raise SourceSchemaError("WDI country metadata contains duplicate ISO3 rows")
    if "WLD" not in ids:
        raise SourceSchemaError("WDI country metadata does not contain WLD")
    return {
        "rows": len(rows),
        "source_id": lock.expected_source_id,
        "contains_wld": True,
    }


def _decode_member(archive: ZipFile, name: str) -> str:
    try:
        return archive.read(name).decode("utf-8-sig")
    except (KeyError, UnicodeDecodeError) as error:
        raise SourceSchemaError(f"invalid DS57 member {name}") from error


def _csv_rows(
    text: str, *, header_prefix: str
) -> tuple[list[str], list[dict[str, str]]]:
    lines = text.splitlines()
    try:
        header_index = next(
            index
            for index, line in enumerate(lines)
            if line.lstrip('\ufeff"').startswith(header_prefix)
        )
    except StopIteration as error:
        raise SourceSchemaError(
            f"DS57 member schema is missing the expected {header_prefix} header"
        ) from error
    reader = csv.DictReader(StringIO("\n".join(lines[header_index:])))
    if reader.fieldnames is None:
        raise SourceSchemaError("DS57 member has no CSV header")
    fields = list(reader.fieldnames)
    trailing_empty_column = bool(fields and fields[-1] == "")
    if trailing_empty_column:
        fields.pop()
    rows = list(reader)
    for row in rows:
        if None in row:
            raise SourceSchemaError("DS57 member row exceeds its declared schema")
        if any(value is None for value in row.values()):
            raise SourceSchemaError(
                "DS57 member row is truncated relative to its declared schema"
            )
        if trailing_empty_column:
            if str(row.get("", "")).strip():
                raise SourceSchemaError(
                    "DS57 member has a nonempty trailing schema column"
                )
            row.pop("", None)
    return fields, rows


def _ds57_member_roles(names: list[str], indicator: str) -> dict[str, str]:
    escaped_indicator = re.escape(indicator)
    patterns = {
        "observations": re.compile(
            rf"^API_{escaped_indicator}_DS57_en_csv_v2_(\d+)\.csv$"
        ),
        "indicator": re.compile(
            rf"^Metadata_Indicator_API_{escaped_indicator}_DS57_en_csv_v2_(\d+)\.csv$"
        ),
        "country": re.compile(
            rf"^Metadata_Country_API_{escaped_indicator}_DS57_en_csv_v2_(\d+)\.csv$"
        ),
    }
    roles: dict[str, str] = {}
    revisions: set[str] = set()
    for role, pattern in patterns.items():
        matches = [(name, pattern.fullmatch(name)) for name in names]
        matches = [(name, match) for name, match in matches if match is not None]
        if len(matches) != 1:
            raise SourceSchemaError(
                f"DS57 ZIP must contain exactly one canonical {role} member"
            )
        name, match = matches[0]
        roles[role] = name
        revisions.add(match.group(1))
    if len(set(roles.values())) != 3 or len(revisions) != 1:
        raise SourceSchemaError(
            "DS57 ZIP members must use one consistent source-57 revision"
        )
    if set(roles.values()) != set(names):
        raise SourceSchemaError("DS57 ZIP contains an unexpected member")
    return roles


def _require_exact_ds57_columns(
    fields: list[str], expected: tuple[str, ...], label: str
) -> None:
    if tuple(fields) != expected:
        raise SourceSchemaError(f"DS57 {label} has unexpected schema columns")


def read_wdi_archive(
    path: str | Path, lock: SourceLock, *, years: Sequence[int] = YEARS
) -> pd.DataFrame:
    """Validate an official source-57 archive and normalize available locked years."""

    if lock.source_family != "wdi_archive_ds57" or lock.expected_source_id != "57":
        raise SourceFamilyError("DS57 parser requires the wdi_archive_ds57 family")
    indicator = lock.expected_indicator
    if indicator is None:
        raise SourceSchemaError("DS57 lock requires an indicator")
    expected_lock_path = f"data/snapshots/wdi_archive/{indicator}.zip"
    if lock.relative_path.as_posix() != expected_lock_path:
        raise SourceFamilyError(
            "DS57 lock path must identify the configured archive indicator family"
        )
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != 3 or len(set(names)) != 3:
                raise SourceSchemaError("DS57 ZIP must contain exactly three members")
            roles = _ds57_member_roles(names, indicator)
            observation_text = _decode_member(archive, roles["observations"])
            indicator_text = _decode_member(archive, roles["indicator"])
            country_text = _decode_member(archive, roles["country"])
    except SourceError:
        raise
    except (OSError, BadZipFile) as error:
        raise SourceSchemaError("source is not a valid DS57 ZIP") from error

    if (
        re.search(
            r'(?m)^"?Data Source"?,"?WDI Database Archives"?,?\r?$', observation_text
        )
        is None
    ):
        raise SourceSchemaError("DS57 observation member has unexpected data source")
    fields, rows = _csv_rows(observation_text, header_prefix="Country Name")
    _require_exact_ds57_columns(fields, DS57_OBSERVATION_COLUMNS, "observation member")
    indicator_fields, indicator_rows = _csv_rows(
        indicator_text, header_prefix="INDICATOR_CODE"
    )
    _require_exact_ds57_columns(
        indicator_fields, DS57_INDICATOR_COLUMNS, "indicator metadata"
    )
    if len(indicator_rows) != 1:
        raise SourceSchemaError(
            "DS57 indicator metadata must contain one indicator row"
        )
    indicator_row = indicator_rows[0]
    if any(not str(indicator_row.get(field, "")).strip() for field in indicator_fields):
        raise SourceSchemaError("DS57 indicator metadata fields must be nonblank")
    if indicator_row["INDICATOR_CODE"] != indicator:
        raise SourceSchemaError("DS57 indicator metadata has an unexpected indicator")
    country_fields, country_rows = _csv_rows(country_text, header_prefix="Country Code")
    _require_exact_ds57_columns(
        country_fields, DS57_COUNTRY_COLUMNS, "country metadata"
    )
    if not country_rows:
        raise SourceSchemaError("DS57 country metadata has no rows")
    country_codes: list[str] = []
    for row in country_rows:
        code = str(row.get("Country Code", "")).strip()
        if not ISO3_RE.fullmatch(code):
            raise SourceSchemaError(
                "DS57 country metadata requires valid nonblank country codes"
            )
        country_codes.append(code)
    if len(country_codes) != len(set(country_codes)):
        raise SourceSchemaError(
            "DS57 country metadata contains duplicate country codes"
        )
    country_code_set = set(country_codes)

    normalized = []
    raw_ids: list[str] = []
    for row in rows:
        iso3 = str(row.get("Country Code", "")).strip()
        if not ISO3_RE.fullmatch(iso3):
            raise SourceSchemaError("DS57 observation has invalid ISO3 code")
        raw_ids.append(iso3)
        if row.get("Indicator Code") != indicator:
            raise SourceSchemaError("DS57 observation has an unexpected indicator")
        if (
            str(row.get("Indicator Name", "")).strip()
            != indicator_row["INDICATOR_NAME"]
        ):
            raise SourceSchemaError(
                "DS57 observation and indicator metadata names are inconsistent"
            )
        if not str(row.get("Country Name", "")).strip():
            raise SourceSchemaError("DS57 observation country name must be nonblank")
        for year in years:
            raw_value = str(row.get(str(year), "")).strip()
            if not raw_value:
                continue
            try:
                value = float(raw_value)
            except ValueError as error:
                raise SourceSchemaError(
                    "DS57 observation has a nonnumeric value"
                ) from error
            normalized.append(
                {
                    "country_name": row["Country Name"],
                    "iso3": iso3,
                    "year": year,
                    "indicator": indicator,
                    "value": value,
                    "unit": lock.unit,
                    "source_id": "57",
                    "country_metadata_member": iso3 in country_code_set,
                }
            )
    raw_id_set = set(raw_ids)
    if "WLD" not in raw_id_set:
        raise SourceSchemaError("DS57 observation does not contain WLD")
    unknown_observation_codes = raw_id_set - country_code_set - DS57_ARCHIVE_ONLY_CODES
    if unknown_observation_codes:
        raise SourceSchemaError(
            "DS57 observation country metadata membership is inconsistent: "
            + ", ".join(sorted(unknown_observation_codes))
        )
    missing_observation_codes = country_code_set - raw_id_set
    if missing_observation_codes:
        raise SourceSchemaError(
            "DS57 country metadata includes codes absent from observations: "
            + ", ".join(sorted(missing_observation_codes))
        )
    frame = pd.DataFrame.from_records(
        normalized,
        columns=[
            "country_name",
            "iso3",
            "year",
            "indicator",
            "value",
            "unit",
            "source_id",
            "country_metadata_member",
        ],
    )
    if frame.duplicated(["iso3", "year"]).any():
        raise SourceSchemaError("DS57 observation contains duplicate ISO3-year rows")
    frame.attrs["members"] = sorted(names)
    frame.attrs["archive_only_country_codes"] = sorted(raw_id_set - country_code_set)
    release_match = re.search(r'Last Updated Date"?,"?([^"\r\n,]+)', observation_text)
    if release_match is None:
        raise SourceSchemaError("DS57 observation member has no release date")
    frame.attrs["release"] = release_match.group(1)
    return frame


def validate_source(
    lock: SourceLock,
    path: str | Path,
    *,
    years: Sequence[int] = YEARS,
    expected_lastupdated: str | None = None,
) -> dict[str, object]:
    """Verify one source hash and validate the schema selected by its locked family."""

    source_path = Path(path)
    _verify_hash(source_path, lock)
    if lock.source_family == "whr_2022_annual_table_2_1":
        frame = read_whr_annual(source_path, years=years)
        return {
            "rows": len(frame),
            "columns": list(frame.columns),
            "years": list(years),
        }
    if lock.source_family == "aqli_2025_country_gadm0":
        frame = read_aqli(source_path, years=years)
        return {
            "rows": len(frame),
            "columns": list(frame.columns),
            "years": list(years),
        }
    if lock.source_family == "wdi_archive_ds57":
        frame = read_wdi_archive(source_path, lock, years=years)
        return {
            "rows": len(frame),
            "columns": list(frame.columns),
            "source_id": "57",
            "members": frame.attrs["members"],
            "archive_only_country_code_count": len(
                frame.attrs["archive_only_country_codes"]
            ),
            "release": frame.attrs["release"],
        }
    if lock.source_family in WDI_CURRENT_FAMILIES:
        if lock.expected_indicator == "country":
            summary = _read_wdi_country_metadata(source_path, lock)
            summary["release"] = expected_lastupdated
            return summary
        if lock.relative_path.name.endswith(".metadata.json"):
            summary = read_wdi_metadata(source_path, lock)
            summary["release"] = expected_lastupdated
            return summary
        frame = read_wdi_observations(
            source_path,
            lock,
            years=years,
            expected_lastupdated=expected_lastupdated,
        )
        return {
            "rows": len(frame),
            "columns": list(frame.columns),
            "years": list(years),
            "source_id": lock.expected_source_id,
            "unit": lock.unit,
            "contains_wld": True,
            "lastupdated": expected_lastupdated,
            "release": expected_lastupdated,
        }
    raise SourceFamilyError(
        f"unsupported configured source family: {lock.source_family}"
    )


def validate_all(
    sources: SourcesConfig,
    *,
    repository_root: str | Path = REPOSITORY_ROOT,
    raw_dir: str | Path = "data/raw/external",
    include_restricted: bool = True,
) -> dict[str, dict[str, object]]:
    """Validate configured sources using only bytes resolved beneath the supplied root."""

    summaries: dict[str, dict[str, object]] = {}
    for key in sorted(sources.locks):
        lock = sources.locks[key]
        if not include_restricted and not lock.redistributable:
            continue
        path = resolve_source_path(
            lock, repository_root=repository_root, raw_dir=raw_dir
        )
        summaries[key] = validate_source(
            lock,
            path,
            expected_lastupdated=sources.wdi_lastupdated
            if lock.source_family in WDI_CURRENT_FAMILIES
            else None,
        )
    return summaries


def build_source_manifest(
    locks: Iterable[SourceLock],
    paths: Mapping[str, Path],
    destination: str | Path,
    *,
    schemas: Mapping[str, Mapping[str, object]],
) -> Path:
    """Write a deterministic, non-row-level source evidence manifest."""

    entries = []
    for lock in sorted(locks, key=lambda item: item.key):
        path = paths[lock.key]
        schema = dict(schemas[lock.key])
        release = (
            lock.source_updated_at
            or lock.archive_capture
            or schema.get("release")
            or schema.get("lastupdated")
            or schema.get("source_id")
        )
        entries.append(
            {
                "key": lock.key,
                "publisher": lock.publisher,
                "release": release,
                "original_url": lock.provenance_url or lock.url,
                "retrieval_url": lock.url,
                "access_date": lock.access_date,
                "expected_sha256": lock.sha256,
                "observed_sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "schema": schema,
                "rights": "redistributable official snapshot"
                if lock.redistributable
                else "restricted source; excluded from public release",
                "redistributable": lock.redistributable,
                "source_family": lock.source_family,
            }
        )
    payload = {"schema_version": 1, "sources": entries}
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_name(output.name + ".part")
    try:
        part.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(part, output)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return output


def _run(command: str, config: Path, raw_dir: Path) -> None:
    sources = load_sources(config)
    paths = {
        key: resolve_source_path(lock, repository_root=REPOSITORY_ROOT, raw_dir=raw_dir)
        for key, lock in sources.locks.items()
    }
    if command == "acquire":
        for key in sorted(sources.locks):
            _acquire_to(sources.locks[key], paths[key], _default_downloader)
    schemas = validate_all(
        sources,
        repository_root=REPOSITORY_ROOT,
        raw_dir=raw_dir,
        include_restricted=True,
    )
    build_source_manifest(
        sources.locks.values(),
        paths,
        REPOSITORY_ROOT / "data/derived/source_manifest.json",
        schemas=schemas,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("acquire", "validate"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--config", type=Path, default=Path("config/sources.toml")
        )
        subparser.add_argument(
            "--raw-dir", type=Path, default=Path("data/raw/external")
        )
    args = parser.parse_args(argv)
    _run(args.command, args.config, args.raw_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
