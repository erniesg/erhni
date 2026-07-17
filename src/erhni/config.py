"""Immutable, fail-closed configuration for the ERHNI pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping
import re
import tomllib


class ConfigError(ValueError):
    """Raised when a method or source lock is not an approved configuration."""


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RETIRED_GHG_INDICATORS = frozenset(
    {"EN.ATM.GHGT.KT.CE", "EN.ATM.METH.KT.CE", "EN.ATM.NOXE.KT.CE"}
)
SOURCE_FAMILIES = frozenset(
    {
        "whr_2022_annual_table_2_1",
        "aqli_2025_country_gadm0",
        "wdi_current",
        "edgar_ar5_excl_lulucf",
        "wdi_archive_ds57",
    }
)


@dataclass(frozen=True, slots=True)
class MethodConfig:
    years: tuple[int, ...]
    burden_universe: str
    allocation_denominator: str
    happiness_weight_universe: str
    ranking_universe: str
    neutral_point: float
    nhly_scale: float
    headline_weight: str
    nonpositive_weight: str
    max_abs_wld_reconciliation_share: float
    primary_ghg_family: str
    ghg_total_indicator: str
    ghg_co2_indicator: str
    ghg_ch4_indicator: str
    ghg_n2o_indicator: str
    ghg_fallback_family: str | None
    gross_penalty_sensitivity: bool
    fixed_penalty_weights: tuple[float, ...]
    sensitivity_neutral_points: tuple[float, ...]
    aqli_rounding_half_width: float
    lower_bound_floor: float
    uncertainty_label: str
    decomposition: str
    absolute_tolerance: float
    relative_tolerance: float


@dataclass(frozen=True, slots=True)
class SourceLock:
    key: str
    url: str
    relative_path: PurePosixPath
    path: Path
    publisher: str
    source_family: str
    unit: str
    expected_source_id: str
    expected_indicator: str | None
    access_date: str
    redistributable: bool
    sha256: str
    benchmark: float | None = None
    source_updated_at: str | None = None
    provenance_url: str | None = None
    archive_capture: str | None = None


@dataclass(frozen=True, slots=True)
class SourcesConfig:
    locks: Mapping[str, SourceLock]
    wdi_lastupdated: str
    fallback_families: Mapping[str, str]

    def lock(self, key: str) -> SourceLock:
        try:
            return self.locks[key]
        except KeyError as error:
            raise ConfigError(f"unknown source lock: {key}") from error

    @property
    def whr(self) -> SourceLock:
        return self.lock("whr_2022_table_2_1")

    @property
    def aqli(self) -> SourceLock:
        return self.lock("aqli_2025_gadm0")


def _repository_path(path: str | Path | None, default_name: str) -> Path:
    candidate = REPOSITORY_ROOT / "config" / default_name if path is None else Path(path)
    if not candidate.is_absolute():
        candidate = REPOSITORY_ROOT / candidate
    return candidate.resolve()


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read configuration {path}: {error}") from error


def _require_table(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a TOML table")
    return value


def _require_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{name} must be a nonempty string")
    return value


def _require_number(data: Mapping[str, Any], name: str) -> float:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number")
    return float(value)


def _require_bool(data: Mapping[str, Any], name: str) -> bool:
    value = data.get(name)
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be a boolean")
    return value


def _require_one_of(value: str, name: str, choices: set[str]) -> str:
    if value not in choices:
        options = ", ".join(sorted(choices))
        raise ConfigError(f"{name} must be one of: {options}")
    return value


def _number_tuple(data: Mapping[str, Any], name: str) -> tuple[float, ...]:
    values = data.get(name)
    if not isinstance(values, list) or not values:
        raise ConfigError(f"{name} must be a nonempty array")
    return tuple(_require_number({"value": value}, "value") for value in values)


def load_method(path: str | Path | None = None) -> MethodConfig:
    """Load the approved method lock from a repository-relative TOML file."""

    data = _read_toml(_repository_path(path, "method.toml"))
    analysis = _require_table(data, "analysis")
    universes = _require_table(data, "universes")
    nhly = _require_table(data, "nhly")
    responsibility = _require_table(data, "responsibility")
    ghg = _require_table(data, "ghg")
    sensitivity = _require_table(data, "sensitivity")
    uncertainty = _require_table(data, "uncertainty")
    reconciliation = _require_table(data, "reconciliation")

    raw_years = analysis.get("years")
    if not isinstance(raw_years, list) or any(
        isinstance(year, bool) or not isinstance(year, int) for year in raw_years
    ):
        raise ConfigError("analysis.years must be an integer array")
    years = tuple(raw_years)
    if years != (2016, 2017, 2018):
        raise ConfigError("analysis.years must pin 2016, 2017, and 2018")

    burden_universe = _require_one_of(
        _require_string(universes, "burden"),
        "universes.burden",
        {"aqli_full_wdi_population"},
    )
    allocation_denominator = _require_one_of(
        _require_string(universes, "allocation_denominator"),
        "universes.allocation_denominator",
        {"wdi_wld"},
    )
    happiness_weight_universe = _require_one_of(
        _require_string(universes, "happiness_weight"),
        "universes.happiness_weight",
        {"balanced_analysis_panel"},
    )
    ranking_universe = _require_one_of(
        _require_string(universes, "ranking"),
        "universes.ranking",
        {"balanced_complete_case"},
    )

    neutral_point = _require_number(nhly, "neutral_point")
    if neutral_point != 5.0:
        raise ConfigError("nhly.neutral_point must be 5.0")
    nhly_scale = _require_number(nhly, "scale")
    if nhly_scale <= 0:
        raise ConfigError("nhly.scale must be positive")

    headline_weight = _require_one_of(
        _require_string(responsibility, "headline_weight"),
        "responsibility.headline_weight",
        {"population_weighted_net_happiness"},
    )
    nonpositive_weight = _require_one_of(
        _require_string(responsibility, "nonpositive_weight"),
        "responsibility.nonpositive_weight",
        {"error"},
    )
    max_abs_wld_reconciliation_share = _require_number(
        responsibility, "max_abs_wld_reconciliation_share"
    )
    if not 0 < max_abs_wld_reconciliation_share <= 1:
        raise ConfigError("responsibility.max_abs_wld_reconciliation_share must be in (0, 1]")

    primary_ghg_family = _require_one_of(
        _require_string(ghg, "primary_family"),
        "ghg.primary_family",
        {"edgar_ar5_excl_lulucf"},
    )
    indicators = tuple(
        _require_string(ghg, name)
        for name in ("total_indicator", "co2_indicator", "ch4_indicator", "n2o_indicator")
    )
    if indicators[0] in RETIRED_GHG_INDICATORS:
        raise ConfigError("retired GHG indicator cannot be the primary indicator")
    if indicators != (
        "EN.GHG.ALL.MT.CE.AR5",
        "EN.GHG.CO2.MT.CE.AR5",
        "EN.GHG.CH4.MT.CE.AR5",
        "EN.GHG.N2O.MT.CE.AR5",
    ):
        raise ConfigError("ghg indicators must pin the active EDGAR AR5 family")
    raw_fallback = _require_string(ghg, "fallback_family")
    if raw_fallback != "none":
        raise ConfigError("ghg fallback family is prohibited")

    fixed_penalty_weights = _number_tuple(sensitivity, "fixed_penalty_weights")
    sensitivity_neutral_points = _number_tuple(sensitivity, "neutral_points")
    gross_penalty_sensitivity = _require_bool(sensitivity, "gross_penalty_weight")
    aqli_rounding_half_width = _require_number(uncertainty, "aqli_rounding_half_width")
    lower_bound_floor = _require_number(uncertainty, "lower_bound_floor")
    absolute_tolerance = _require_number(reconciliation, "absolute_tolerance")
    relative_tolerance = _require_number(reconciliation, "relative_tolerance")
    if absolute_tolerance <= 0 or relative_tolerance <= 0:
        raise ConfigError("reconciliation tolerances must be positive")

    return MethodConfig(
        years=years,
        burden_universe=burden_universe,
        allocation_denominator=allocation_denominator,
        happiness_weight_universe=happiness_weight_universe,
        ranking_universe=ranking_universe,
        neutral_point=neutral_point,
        nhly_scale=nhly_scale,
        headline_weight=headline_weight,
        nonpositive_weight=nonpositive_weight,
        max_abs_wld_reconciliation_share=max_abs_wld_reconciliation_share,
        primary_ghg_family=primary_ghg_family,
        ghg_total_indicator=indicators[0],
        ghg_co2_indicator=indicators[1],
        ghg_ch4_indicator=indicators[2],
        ghg_n2o_indicator=indicators[3],
        ghg_fallback_family=None,
        gross_penalty_sensitivity=gross_penalty_sensitivity,
        fixed_penalty_weights=fixed_penalty_weights,
        sensitivity_neutral_points=sensitivity_neutral_points,
        aqli_rounding_half_width=aqli_rounding_half_width,
        lower_bound_floor=lower_bound_floor,
        uncertainty_label=_require_string(uncertainty, "label"),
        decomposition=_require_one_of(
            _require_string(reconciliation, "decomposition"),
            "reconciliation.decomposition",
            {"shapley"},
        ),
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
    )


def _relative_destination(raw_path: str) -> tuple[PurePosixPath, Path]:
    relative = PurePosixPath(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ConfigError(f"source path must be repository-relative: {raw_path}")
    resolved = (REPOSITORY_ROOT / relative).resolve()
    if REPOSITORY_ROOT not in resolved.parents:
        raise ConfigError(f"source path escapes repository: {raw_path}")
    return relative, resolved


def _load_source(raw: Mapping[str, Any]) -> SourceLock:
    key = _require_string(raw, "key")
    if "fallback_family" in raw:
        raise ConfigError(f"{key} source fallback is prohibited")
    sha256 = _require_string(raw, "sha256")
    if not SHA256_RE.fullmatch(sha256):
        raise ConfigError(f"{key}.sha256 must be lowercase hexadecimal SHA-256")
    relative_path, resolved_path = _relative_destination(_require_string(raw, "path"))
    access_date = _require_string(raw, "access_date")
    if access_date != "2026-07-17":
        raise ConfigError(f"{key}.access_date must pin 2026-07-17")
    benchmark = raw.get("benchmark")
    if benchmark is not None:
        benchmark = _require_number(raw, "benchmark")
    return SourceLock(
        key=key,
        url=_require_string(raw, "url"),
        relative_path=relative_path,
        path=resolved_path,
        publisher=_require_string(raw, "publisher"),
        source_family=_require_one_of(
            _require_string(raw, "source_family"),
            f"{key}.source_family",
            set(SOURCE_FAMILIES),
        ),
        unit=_require_string(raw, "unit"),
        expected_source_id=_require_string(raw, "expected_source_id"),
        expected_indicator=(
            _require_string(raw, "expected_indicator")
            if raw.get("expected_indicator") is not None
            else None
        ),
        access_date=access_date,
        redistributable=_require_bool(raw, "redistributable"),
        sha256=sha256,
        benchmark=benchmark,
        source_updated_at=raw.get("source_updated_at"),
        provenance_url=raw.get("provenance_url"),
        archive_capture=raw.get("archive_capture"),
    )


def load_sources(path: str | Path | None = None) -> SourcesConfig:
    """Load source locks while preserving immutable, repository-resolved destinations."""

    data = _read_toml(_repository_path(path, "sources.toml"))
    if "fallback" in data:
        raise ConfigError("automatic source fallback is prohibited")
    wdi = _require_table(data, "wdi")
    wdi_lastupdated = _require_string(wdi, "lastupdated")
    if wdi_lastupdated != "2026-07-13":
        raise ConfigError("wdi.lastupdated must pin 2026-07-13")
    raw_sources = data.get("source")
    if not isinstance(raw_sources, list):
        raise ConfigError("source must be an array of TOML tables")
    locks = [_load_source(raw) for raw in raw_sources if isinstance(raw, dict)]
    if len(locks) != len(raw_sources):
        raise ConfigError("each source entry must be a TOML table")
    keys = [lock.key for lock in locks]
    if len(set(keys)) != len(keys):
        raise ConfigError("source keys must be unique")
    by_key = {lock.key: lock for lock in locks}
    required = {"whr_2022_table_2_1", "aqli_2025_gadm0"}
    if missing := required - by_key.keys():
        raise ConfigError(f"missing required source locks: {', '.join(sorted(missing))}")
    if by_key["aqli_2025_gadm0"].benchmark != 5.0:
        raise ConfigError("AQLI benchmark must be 5.0")
    families = {lock.source_family for lock in locks}
    if "edgar_ar5_excl_lulucf" not in families or "wdi_archive_ds57" not in families:
        raise ConfigError("archive and successor GHG source families must both be explicit")
    return SourcesConfig(
        locks=MappingProxyType(by_key),
        wdi_lastupdated=wdi_lastupdated,
        fallback_families=MappingProxyType({}),
    )
