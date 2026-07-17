"""Pure scientific metrics for ERHNI, with explicit units and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


Numeric = float | Sequence[float] | np.ndarray
BURDEN_COLUMNS = (
    "year",
    "iso3",
    "aqli_years_lost",
    "population",
    "burden_person_years",
)
BURDEN_EXCLUSION_COLUMNS = ("year", "iso3", "reason")
BURDEN_SUMMARY_COLUMNS = (
    "year",
    "burden_universe_count",
    "burden_person_years",
)


class MetricInputError(ValueError):
    """Raised when a scientific metric receives an invalid input."""


class NonPositiveWeightError(MetricInputError):
    """Raised when the configured net-happiness weight is not positive."""


@dataclass(frozen=True, slots=True)
class HappinessWeightSummary:
    """Population-weighted happiness and its net and gross lost-year weights."""

    population_weighted_happiness: float
    net_weight: float
    gross_weight: float
    observation_count: int


@dataclass(frozen=True, slots=True)
class BurdenResult:
    """Full valid AQLI-WDI burden universe plus terminal exclusions."""

    universe: pd.DataFrame
    exclusions: pd.DataFrame
    year_summary: pd.DataFrame


def _numeric_array(value: Numeric, label: str) -> np.ndarray:
    try:
        return np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise MetricInputError(f"{label} must be numeric") from error


def _finite_scalar(value: float, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise MetricInputError(f"{label} must be numeric") from error
    if not np.isfinite(result):
        raise MetricInputError(f"{label} must be finite")
    return result


def _return_scalar_if_scalar(value: np.ndarray) -> float | np.ndarray:
    return float(value) if value.ndim == 0 else value


def nhly(
    happiness: Numeric,
    life_expectancy: Numeric,
    *,
    neutral: float,
    scale: float,
) -> float | np.ndarray:
    """Return net-happiness-weighted life years per resident."""

    happiness_values = _numeric_array(happiness, "happiness")
    life_values = _numeric_array(life_expectancy, "life expectancy")
    if happiness_values.shape != life_values.shape:
        raise MetricInputError("happiness and life expectancy must have the same shape")
    if not np.isfinite(happiness_values).all() or not np.isfinite(life_values).all():
        raise MetricInputError("NHLY inputs must be finite")
    neutral_value = _finite_scalar(neutral, "neutral point")
    scale_value = _finite_scalar(scale, "scale")
    if scale_value <= 0:
        raise MetricInputError("scale must be positive")
    result = ((happiness_values - neutral_value) / scale_value) * life_values
    return _return_scalar_if_scalar(result)


def _weight_components(
    happiness: Numeric,
    population: Numeric,
    *,
    neutral: float,
    scale: float,
) -> tuple[float, float, float, int]:
    happiness_values = _numeric_array(happiness, "happiness")
    population_values = _numeric_array(population, "population")
    if happiness_values.ndim != 1 or population_values.ndim != 1:
        raise MetricInputError("happiness and population must be one-dimensional")
    if happiness_values.shape != population_values.shape:
        raise MetricInputError("happiness and population must have the same shape")
    if happiness_values.size == 0:
        raise MetricInputError("happiness weight inputs must be nonempty")
    if not np.isfinite(happiness_values).all() or not np.isfinite(population_values).all():
        raise MetricInputError("happiness weight inputs must be finite")
    if (population_values <= 0).any():
        raise MetricInputError("population values must be positive")
    neutral_value = _finite_scalar(neutral, "neutral point")
    scale_value = _finite_scalar(scale, "scale")
    if scale_value <= 0:
        raise MetricInputError("scale must be positive")
    weighted_happiness = float(
        np.dot(happiness_values, population_values) / population_values.sum()
    )
    net_weight = (weighted_happiness - neutral_value) / scale_value
    gross_weight = weighted_happiness / scale_value
    return weighted_happiness, net_weight, gross_weight, int(happiness_values.size)


def happiness_weights(
    happiness: Numeric,
    population: Numeric,
    *,
    neutral: float,
    scale: float = 10.0,
) -> HappinessWeightSummary:
    """Return the balanced-panel Hbar and positive primary/gross weights."""

    weighted_happiness, net_weight, gross_weight, count = _weight_components(
        happiness,
        population,
        neutral=neutral,
        scale=scale,
    )
    if net_weight <= 0:
        raise NonPositiveWeightError(
            f"net lost-year weight must be positive, observed {net_weight:.15g}"
        )
    return HappinessWeightSummary(
        population_weighted_happiness=weighted_happiness,
        net_weight=net_weight,
        gross_weight=gross_weight,
        observation_count=count,
    )


def net_lost_year_weight(
    happiness: Numeric,
    population: Numeric,
    *,
    neutral: float,
    scale: float = 10.0,
) -> float:
    """Return positive `(Hbar - neutral) / scale`, failing instead of clamping."""

    return happiness_weights(
        happiness,
        population,
        neutral=neutral,
        scale=scale,
    ).net_weight


def gross_lost_year_weight(
    happiness: Numeric,
    population: Numeric,
    *,
    scale: float = 10.0,
) -> float:
    """Return the explicitly normative gross-happiness penalty weight Hbar/scale."""

    _, _, gross_weight, _ = _weight_components(
        happiness,
        population,
        neutral=0.0,
        scale=scale,
    )
    return gross_weight


def apply_erhni(nhly_values: Numeric, penalties: Numeric) -> float | np.ndarray:
    """Subtract responsibility penalty per resident from NHLY row by row."""

    achievement = _numeric_array(nhly_values, "NHLY")
    penalty = _numeric_array(penalties, "penalty")
    if achievement.shape != penalty.shape:
        raise MetricInputError("NHLY and penalty must have the same shape")
    if not np.isfinite(achievement).all() or not np.isfinite(penalty).all():
        raise MetricInputError("NHLY and penalty must be finite")
    return _return_scalar_if_scalar(achievement - penalty)


def three_gas_co2e(
    co2e: Numeric,
    ch4e: Numeric,
    n2oe: Numeric,
) -> float | np.ndarray:
    """Sum three already-AR5-standardized CO2e series without another GWP."""

    components = (
        _numeric_array(co2e, "CO2e"),
        _numeric_array(ch4e, "CH4e"),
        _numeric_array(n2oe, "N2Oe"),
    )
    if len({component.shape for component in components}) != 1:
        raise MetricInputError("three-gas CO2e components must have the same shape")
    if not all(np.isfinite(component).all() for component in components):
        raise MetricInputError("three-gas CO2e components must be finite")
    if any((component < 0).any() for component in components):
        raise MetricInputError("three-gas CO2e components must be nonnegative")
    result = components[0] + components[1] + components[2]
    return _return_scalar_if_scalar(result)


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise MetricInputError(f"{label} lacks required columns: {', '.join(missing)}")


def _validate_keys(frame: pd.DataFrame, label: str) -> None:
    if frame.duplicated(["year", "iso3"]).any():
        raise MetricInputError(f"{label} contains duplicate country-year keys")
    if frame[["year", "iso3"]].isna().any().any():
        raise MetricInputError(f"{label} contains a missing canonical mapping")
    iso3 = frame["iso3"].astype(str)
    if not iso3.str.fullmatch(r"[A-Z]{3}").all():
        raise MetricInputError(f"{label} contains an invalid canonical ISO3 mapping")
    year = pd.to_numeric(frame["year"], errors="coerce")
    if year.isna().any() or not np.isfinite(year).all() or not np.equal(year, np.floor(year)).all():
        raise MetricInputError(f"{label} contains an invalid year")


def build_aqli_burden(aqli: pd.DataFrame, population: pd.DataFrame) -> BurdenResult:
    """Build the sample-independent AQLI/full-WDI-population burden universe."""

    _require_columns(aqli, {"year", "iso3", "aqli_years_lost"}, "AQLI input")
    _require_columns(population, {"year", "iso3", "population"}, "population input")
    _validate_keys(aqli, "AQLI input")
    _validate_keys(population, "population input")

    left = aqli.loc[:, ["year", "iso3", "aqli_years_lost"]].copy()
    right = population.loc[:, ["year", "iso3", "population"]].copy()
    left["year"] = pd.to_numeric(left["year"]).astype(int)
    right["year"] = pd.to_numeric(right["year"]).astype(int)
    left["aqli_years_lost"] = pd.to_numeric(
        left["aqli_years_lost"], errors="coerce"
    )
    right["population"] = pd.to_numeric(right["population"], errors="coerce")
    finite_loss = np.isfinite(left["aqli_years_lost"])
    if (left.loc[finite_loss, "aqli_years_lost"] < 0).any():
        raise MetricInputError("AQLI years lost cannot be negative")

    merged = left.merge(
        right,
        how="left",
        on=["year", "iso3"],
        validate="one_to_one",
        indicator=True,
        sort=False,
    ).sort_values(["year", "iso3"], kind="stable", ignore_index=True)
    reason = pd.Series(pd.NA, index=merged.index, dtype="string")
    invalid_loss = ~np.isfinite(merged["aqli_years_lost"])
    reason.loc[invalid_loss] = "nonfinite_aqli_years_lost"
    missing_population = merged["_merge"].eq("left_only") & reason.isna()
    reason.loc[missing_population] = "missing_wdi_population_mapping"
    nonfinite_population = ~np.isfinite(merged["population"]) & reason.isna()
    reason.loc[nonfinite_population] = "nonfinite_wdi_population"
    nonpositive_population = merged["population"].le(0) & reason.isna()
    reason.loc[nonpositive_population] = "nonpositive_wdi_population"

    valid = reason.isna()
    universe = merged.loc[
        valid,
        ["year", "iso3", "aqli_years_lost", "population"],
    ].copy()
    universe["burden_person_years"] = (
        universe["aqli_years_lost"] * universe["population"]
    )
    universe = universe.loc[:, BURDEN_COLUMNS].reset_index(drop=True)
    exclusions = merged.loc[~valid, ["year", "iso3"]].copy()
    exclusions["reason"] = reason.loc[~valid].to_numpy()
    exclusions = exclusions.loc[:, BURDEN_EXCLUSION_COLUMNS].reset_index(drop=True)

    years = pd.Index(sorted(left["year"].unique()), name="year")
    if universe.empty:
        grouped = pd.DataFrame(
            {
                "burden_universe_count": np.zeros(len(years), dtype=int),
                "burden_person_years": np.zeros(len(years), dtype=float),
            },
            index=years,
        )
    else:
        grouped = universe.groupby("year", sort=True).agg(
            burden_universe_count=("iso3", "size"),
            burden_person_years=("burden_person_years", "sum"),
        )
        grouped = grouped.reindex(years, fill_value=0)
    year_summary = grouped.reset_index().loc[:, BURDEN_SUMMARY_COLUMNS]
    year_summary["burden_universe_count"] = year_summary[
        "burden_universe_count"
    ].astype(int)
    year_summary["burden_person_years"] = year_summary[
        "burden_person_years"
    ].astype(float)
    return BurdenResult(
        universe=universe,
        exclusions=exclusions,
        year_summary=year_summary,
    )
