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


def _source_spec(
    url: str,
    path: str,
    publisher: str,
    source_family: str,
    unit: str,
    expected_source_id: str,
    sha256: str,
    *,
    expected_indicator: str | None = None,
    redistributable: bool,
    benchmark: float | None = None,
    source_updated_at: str | None = None,
    provenance_url: str | None = None,
    archive_capture: str | None = None,
) -> Mapping[str, object]:
    return MappingProxyType(
        {
            "url": url,
            "relative_path": path,
            "publisher": publisher,
            "source_family": source_family,
            "unit": unit,
            "expected_source_id": expected_source_id,
            "expected_indicator": expected_indicator,
            "access_date": "2026-07-17",
            "redistributable": redistributable,
            "sha256": sha256,
            "benchmark": benchmark,
            "source_updated_at": source_updated_at,
            "provenance_url": provenance_url,
            "archive_capture": archive_capture,
        }
    )


CANONICAL_SOURCE_LOCKS: Mapping[str, Mapping[str, object]] = MappingProxyType(
    {
        "whr_2022_table_2_1": _source_spec(
            "https://web.archive.org/web/20220715181822id_/https://happiness-report.s3.amazonaws.com/2022/DataForTable2.1.xls",
            "data/raw/external/whr_2022_data_for_table_2_1.xls",
            "World Happiness Report",
            "whr_2022_annual_table_2_1",
            "Cantril ladder score",
            "DataForTable2.1",
            "f118e7f606f091b978edc674242b491b79ee37bea6cb2b5243f805f5f39ccfa4",
            redistributable=False,
            provenance_url="https://web.archive.org/web/20220715181822id_/https://worldhappiness.report/ed/2022/",
            archive_capture="2022-07-15T18:18:22Z",
        ),
        "aqli_2025_gadm0": _source_spec(
            "https://cdn.sanity.io/files/3o8tp68r/production/4d1bc319df6657d5ced2fdfc38604e0da13cc812.csv",
            "data/raw/external/aqli_2025_gadm0.csv",
            "Energy Policy Institute at the University of Chicago",
            "aqli_2025_country_gadm0",
            "life expectancy years lost per resident",
            "AQLI 2025 country-level data",
            "65bf00ba910932d408debb37dce3ea769eb2f1d3d0aef81f223b77947b81be73",
            redistributable=False,
            benchmark=5.0,
            source_updated_at="2025-08-19T13:13:14Z",
        ),
        "wdi_population": _source_spec(
            "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?date=2016:2018&format=json&per_page=20000",
            "data/snapshots/wdi/SP.POP.TOTL.json",
            "World Bank",
            "wdi_current",
            "people",
            "2",
            "37c342714703650a21a159153626e42f114005220d77e60eeff835c70b95bd66",
            expected_indicator="SP.POP.TOTL",
            redistributable=True,
        ),
        "wdi_life_expectancy": _source_spec(
            "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.LE00.IN?date=2016:2018&format=json&per_page=20000",
            "data/snapshots/wdi/SP.DYN.LE00.IN.json",
            "World Bank",
            "wdi_current",
            "years",
            "2",
            "5bf9cb1fab1a58a5eef347da0fe0356fb80ff1539171deebc41455f8ecf47693",
            expected_indicator="SP.DYN.LE00.IN",
            redistributable=True,
        ),
        "wdi_ghg_total": _source_spec(
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.ALL.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "data/snapshots/wdi/EN.GHG.ALL.MT.CE.AR5.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "Mt CO2 equivalent",
            "2",
            "68207c08d82f19942abb8a4437449079a4d46a645d4136ccb7698ab983d79b58",
            expected_indicator="EN.GHG.ALL.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_ghg_co2": _source_spec(
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CO2.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "data/snapshots/wdi/EN.GHG.CO2.MT.CE.AR5.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "Mt CO2 equivalent",
            "2",
            "a97b7839bc570ff012478ca1db8661c4ae4ca502ee4d8188a86ea922eed0f8d0",
            expected_indicator="EN.GHG.CO2.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_ghg_ch4": _source_spec(
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.CH4.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "data/snapshots/wdi/EN.GHG.CH4.MT.CE.AR5.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "Mt CO2 equivalent",
            "2",
            "5a5dbd12458e21022f3264faa43349dd94a061a68fb552889f5c6d806605eae4",
            expected_indicator="EN.GHG.CH4.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_ghg_n2o": _source_spec(
            "https://api.worldbank.org/v2/country/all/indicator/EN.GHG.N2O.MT.CE.AR5?date=2016:2018&format=json&per_page=20000",
            "data/snapshots/wdi/EN.GHG.N2O.MT.CE.AR5.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "Mt CO2 equivalent",
            "2",
            "e862b242cccfc9b78ba92c2f2341e5da888061d00629ab74ab5d347202ee2b79",
            expected_indicator="EN.GHG.N2O.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_country_metadata": _source_spec(
            "https://api.worldbank.org/v2/country?format=json&per_page=400",
            "data/snapshots/wdi/country.metadata.json",
            "World Bank",
            "wdi_current",
            "metadata",
            "2",
            "d29d57f8adf954c5e2a1520a02fb2c7b45575d8db3bd327a9dff47d66914231c",
            expected_indicator="country",
            redistributable=True,
        ),
        "wdi_population_metadata": _source_spec(
            "https://api.worldbank.org/v2/indicator/SP.POP.TOTL?format=json",
            "data/snapshots/wdi/SP.POP.TOTL.metadata.json",
            "World Bank",
            "wdi_current",
            "metadata",
            "2",
            "2f8491efc00bf2c0995112ff8e87aba69e5e9d22d0880b22f7e3a4ec757ba05c",
            expected_indicator="SP.POP.TOTL",
            redistributable=True,
        ),
        "wdi_life_expectancy_metadata": _source_spec(
            "https://api.worldbank.org/v2/indicator/SP.DYN.LE00.IN?format=json",
            "data/snapshots/wdi/SP.DYN.LE00.IN.metadata.json",
            "World Bank",
            "wdi_current",
            "metadata",
            "2",
            "a39cb6fddfbbb953053690366243dffe77a266c4deae79c46ce5a06da9f5fc31",
            expected_indicator="SP.DYN.LE00.IN",
            redistributable=True,
        ),
        "wdi_ghg_total_metadata": _source_spec(
            "https://api.worldbank.org/v2/indicator/EN.GHG.ALL.MT.CE.AR5?format=json",
            "data/snapshots/wdi/EN.GHG.ALL.MT.CE.AR5.metadata.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "metadata",
            "2",
            "cc3dc0cec5b9a6bd3874cfc8c3e4f0e7ee5232f8726927d9784b6abdcc8e3ed8",
            expected_indicator="EN.GHG.ALL.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_ghg_co2_metadata": _source_spec(
            "https://api.worldbank.org/v2/indicator/EN.GHG.CO2.MT.CE.AR5?format=json",
            "data/snapshots/wdi/EN.GHG.CO2.MT.CE.AR5.metadata.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "metadata",
            "2",
            "b589d061bd920762db1bc986fd2e8f75cb25aeb940509907a1906fd40484e839",
            expected_indicator="EN.GHG.CO2.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_ghg_ch4_metadata": _source_spec(
            "https://api.worldbank.org/v2/indicator/EN.GHG.CH4.MT.CE.AR5?format=json",
            "data/snapshots/wdi/EN.GHG.CH4.MT.CE.AR5.metadata.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "metadata",
            "2",
            "708193dc91019e5dee1d8c426a67fca4967ca2fedac12598ab64730e4037375e",
            expected_indicator="EN.GHG.CH4.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_ghg_n2o_metadata": _source_spec(
            "https://api.worldbank.org/v2/indicator/EN.GHG.N2O.MT.CE.AR5?format=json",
            "data/snapshots/wdi/EN.GHG.N2O.MT.CE.AR5.metadata.json",
            "World Bank / EDGAR",
            "edgar_ar5_excl_lulucf",
            "metadata",
            "2",
            "c4d6c1792a8a4ce42271b0237e08af0a1362de841965cad4a7f6a7131e0adf8e",
            expected_indicator="EN.GHG.N2O.MT.CE.AR5",
            redistributable=True,
        ),
        "wdi_archive_total_ghg": _source_spec(
            "https://api.worldbank.org/v2/en/indicator/EN.ATM.GHGT.KT.CE?downloadformat=csv",
            "data/snapshots/wdi_archive/EN.ATM.GHGT.KT.CE.zip",
            "World Bank",
            "wdi_archive_ds57",
            "kt CO2 equivalent",
            "57",
            "ba749f90dc55b7373c3b7b7eab0cd7c8eb5dac9a070c6a746225c90f94271ba8",
            expected_indicator="EN.ATM.GHGT.KT.CE",
            redistributable=True,
        ),
        "wdi_archive_ch4": _source_spec(
            "https://api.worldbank.org/v2/en/indicator/EN.ATM.METH.KT.CE?downloadformat=csv",
            "data/snapshots/wdi_archive/EN.ATM.METH.KT.CE.zip",
            "World Bank",
            "wdi_archive_ds57",
            "kt CO2 equivalent",
            "57",
            "c1bf878a5bad6151bde1258e5f4c25fddfa9a5862180927c6e25e2127d2fbb54",
            expected_indicator="EN.ATM.METH.KT.CE",
            redistributable=True,
        ),
        "wdi_archive_n2o": _source_spec(
            "https://api.worldbank.org/v2/en/indicator/EN.ATM.NOXE.KT.CE?downloadformat=csv",
            "data/snapshots/wdi_archive/EN.ATM.NOXE.KT.CE.zip",
            "World Bank",
            "wdi_archive_ds57",
            "kt CO2 equivalent",
            "57",
            "d9aec51af3b04beeeb0389e218eb43b18f1a526d4d42bc3325726ffd866efad9",
            expected_indicator="EN.ATM.NOXE.KT.CE",
            redistributable=True,
        ),
    }
)

CANONICAL_METHOD_PINS: Mapping[str, object] = MappingProxyType(
    {
        "years": (2016, 2017, 2018),
        "burden_universe": "aqli_full_wdi_population",
        "allocation_denominator": "wdi_wld",
        "happiness_weight_universe": "balanced_analysis_panel",
        "ranking_universe": "balanced_complete_case",
        "neutral_point": 5.0,
        "nhly_scale": 10.0,
        "headline_weight": "population_weighted_net_happiness",
        "nonpositive_weight": "error",
        "max_abs_wld_reconciliation_share": 0.05,
        "primary_ghg_family": "edgar_ar5_excl_lulucf",
        "ghg_total_indicator": "EN.GHG.ALL.MT.CE.AR5",
        "ghg_co2_indicator": "EN.GHG.CO2.MT.CE.AR5",
        "ghg_ch4_indicator": "EN.GHG.CH4.MT.CE.AR5",
        "ghg_n2o_indicator": "EN.GHG.N2O.MT.CE.AR5",
        "ghg_fallback_family": None,
        "gross_penalty_sensitivity": True,
        "fixed_penalty_weights": (0.05, 0.10, 0.25, 0.50, 0.765, 1.00),
        "sensitivity_neutral_points": (4.0, 4.5, 5.0, 5.1),
        "aqli_rounding_half_width": 0.05,
        "lower_bound_floor": 0.0,
        "uncertainty_label": "rounding_sensitivity_not_confidence_interval",
        "decomposition": "shapley",
        "absolute_tolerance": 1e-9,
        "relative_tolerance": 1e-10,
    }
)


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


def _validate_method_pins(method: MethodConfig) -> MethodConfig:
    for field, expected in CANONICAL_METHOD_PINS.items():
        if getattr(method, field) != expected:
            raise ConfigError(f"method pin {field} does not match the approved value")
    return method


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

    method = MethodConfig(
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
        decomposition=_require_string(reconciliation, "decomposition"),
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
    )
    return _validate_method_pins(method)


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


SOURCE_FIELDS = frozenset(
    {
        "key",
        "url",
        "path",
        "publisher",
        "source_family",
        "unit",
        "expected_source_id",
        "expected_indicator",
        "access_date",
        "redistributable",
        "sha256",
        "benchmark",
        "source_updated_at",
        "provenance_url",
        "archive_capture",
    }
)


def _validate_canonical_sources(locks: Mapping[str, SourceLock]) -> None:
    expected_keys = set(CANONICAL_SOURCE_LOCKS)
    actual_keys = set(locks)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ConfigError(
            f"canonical source lock keys differ; missing={missing}, extra={extra}"
        )
    for key, expected in CANONICAL_SOURCE_LOCKS.items():
        lock = locks[key]
        observed = {
            "url": lock.url,
            "relative_path": lock.relative_path.as_posix(),
            "publisher": lock.publisher,
            "source_family": lock.source_family,
            "unit": lock.unit,
            "expected_source_id": lock.expected_source_id,
            "expected_indicator": lock.expected_indicator,
            "access_date": lock.access_date,
            "redistributable": lock.redistributable,
            "sha256": lock.sha256,
            "benchmark": lock.benchmark,
            "source_updated_at": lock.source_updated_at,
            "provenance_url": lock.provenance_url,
            "archive_capture": lock.archive_capture,
        }
        for field, value in expected.items():
            if observed[field] != value:
                raise ConfigError(
                    f"canonical source lock {key}.{field} does not match the approved value"
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
    for raw in raw_sources:
        if isinstance(raw, dict) and (extra_fields := set(raw) - SOURCE_FIELDS):
            raise ConfigError(
                f"canonical source lock has unregistered fields: {sorted(extra_fields)}"
            )
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
    _validate_canonical_sources(by_key)
    return SourcesConfig(
        locks=MappingProxyType(by_key),
        wdi_lastupdated=wdi_lastupdated,
        fallback_families=MappingProxyType({}),
    )
