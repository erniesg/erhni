"""Pure complete-case and balanced-panel construction for ERHNI."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from erhni.config import MethodConfig


SAMPLE_COLUMNS = (
    "year",
    "iso3",
    "display_name",
    "source_region",
    "display_region",
    "life_ladder",
    "life_expectancy",
    "population",
    "aqli_years_lost",
    "ghg_total",
    "ghg_co2",
    "ghg_ch4",
    "ghg_n2o",
)
EXCLUSION_COLUMNS = ("year", "iso3", "stage", "reason")
FLOW_COLUMNS = (
    "stage",
    "eligible_country_year_rows",
    "eligible_countries",
    "excluded_at_stage",
)


class SampleInputError(ValueError):
    """Raised when normalized inputs cannot define the approved sample."""


@dataclass(frozen=True, slots=True)
class SampleResult:
    """Maximal complete cases, balanced panel, and generated flow evidence."""

    maximal_complete_case: pd.DataFrame
    balanced_panel: pd.DataFrame
    exclusions: pd.DataFrame
    flow: pd.DataFrame


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SampleInputError(f"{label} lacks required columns: {', '.join(missing)}")


def _validate_normalized(
    frame: pd.DataFrame,
    *,
    required: set[str],
    label: str,
    years: tuple[int, ...],
) -> pd.DataFrame:
    _require_columns(frame, required | {"year", "iso3", "imputed"}, label)
    selected = frame.copy()
    if selected.duplicated(["year", "iso3"]).any():
        raise SampleInputError(f"{label} contains duplicate country-year rows")
    if selected[["year", "iso3"]].isna().any().any():
        raise SampleInputError(f"{label} contains missing country-year keys")
    numeric_year = pd.to_numeric(selected["year"], errors="coerce")
    if numeric_year.isna().any() or not np.equal(numeric_year, np.floor(numeric_year)).all():
        raise SampleInputError(f"{label} contains an invalid year")
    selected["year"] = numeric_year.astype(int)
    if not set(selected["year"]).issubset(years):
        raise SampleInputError(f"{label} contains a year outside the configured window")
    iso3 = selected["iso3"].astype(str)
    if not iso3.str.fullmatch(r"[A-Z]{3}").all():
        raise SampleInputError(f"{label} contains an invalid canonical ISO3")
    selected["iso3"] = iso3
    if not selected["imputed"].isin([False, 0]).all():
        raise SampleInputError(f"{label} contains imputed observations")
    return selected


def _flow_row(stage: str, eligible: pd.Series, grid: pd.DataFrame, before: int) -> dict[str, object]:
    remaining = grid.loc[eligible]
    count = int(eligible.sum())
    return {
        "stage": stage,
        "eligible_country_year_rows": count,
        "eligible_countries": int(remaining["iso3"].nunique()),
        "excluded_at_stage": before - count,
    }


def build_balanced_sample(
    method: MethodConfig,
    happiness: pd.DataFrame,
    wdi: pd.DataFrame,
    aqli: pd.DataFrame,
    regions: pd.DataFrame,
) -> SampleResult:
    """Construct maximal and balanced complete cases without a target count."""

    years = method.years
    happiness_input = _validate_normalized(
        happiness,
        required={"life_ladder"},
        label="happiness input",
        years=years,
    )
    wdi_input = _validate_normalized(
        wdi,
        required={
            "record_type",
            "population",
            "life_expectancy",
            "ghg_total",
            "ghg_co2",
            "ghg_ch4",
            "ghg_n2o",
        },
        label="WDI input",
        years=years,
    )
    aqli_input = _validate_normalized(
        aqli,
        required={"aqli_years_lost"},
        label="AQLI input",
        years=years,
    )
    _require_columns(
        regions,
        {"iso3", "display_name", "source_region", "display_region"},
        "regions input",
    )
    if regions["iso3"].isna().any() or regions["iso3"].duplicated().any():
        raise SampleInputError("regions input contains missing or duplicate ISO3 rows")

    countries = wdi_input.loc[wdi_input["record_type"].eq("country")].copy()
    source_iso3 = sorted(
        set(happiness_input["iso3"])
        | set(countries["iso3"])
        | set(aqli_input["iso3"])
    )
    if not source_iso3:
        raise SampleInputError("normalized sources contain no country identities")
    region_table = regions.loc[
        :, ["iso3", "display_name", "source_region", "display_region"]
    ].copy()
    missing_regions = sorted(set(source_iso3) - set(region_table["iso3"]))
    if missing_regions:
        raise SampleInputError(
            "regions input lacks normalized identities: " + ", ".join(missing_regions)
        )

    grid = pd.MultiIndex.from_product(
        [years, source_iso3], names=["year", "iso3"]
    ).to_frame(index=False)
    grid = grid.merge(region_table, on="iso3", how="left", validate="many_to_one")
    grid = grid.merge(
        happiness_input.loc[:, ["year", "iso3", "life_ladder"]],
        on=["year", "iso3"],
        how="left",
        validate="one_to_one",
    )
    grid = grid.merge(
        countries.loc[
            :,
            [
                "year",
                "iso3",
                "population",
                "life_expectancy",
                "ghg_total",
                "ghg_co2",
                "ghg_ch4",
                "ghg_n2o",
            ],
        ],
        on=["year", "iso3"],
        how="left",
        validate="one_to_one",
    )
    grid = grid.merge(
        aqli_input.loc[:, ["year", "iso3", "aqli_years_lost"]],
        on=["year", "iso3"],
        how="left",
        validate="one_to_one",
    ).sort_values(["year", "iso3"], kind="stable", ignore_index=True)

    numeric_columns = (
        "life_ladder",
        "life_expectancy",
        "population",
        "aqli_years_lost",
        "ghg_total",
        "ghg_co2",
        "ghg_ch4",
        "ghg_n2o",
    )
    for column in numeric_columns:
        grid[column] = pd.to_numeric(grid[column], errors="coerce")
    finite_aqli = np.isfinite(grid["aqli_years_lost"])
    if (grid.loc[finite_aqli, "aqli_years_lost"] < 0).any():
        raise SampleInputError("AQLI years lost cannot be negative")
    finite_ghg = np.isfinite(grid["ghg_total"])
    if (grid.loc[finite_ghg, "ghg_total"] < 0).any():
        raise SampleInputError("primary GHG values cannot be negative")

    eligible = pd.Series(True, index=grid.index)
    stage = pd.Series(pd.NA, index=grid.index, dtype="string")
    reason = pd.Series(pd.NA, index=grid.index, dtype="string")
    flow_rows = [_flow_row("source_union", eligible, grid, before=len(grid))]

    rules = (
        ("happiness_available", np.isfinite(grid["life_ladder"]), "missing_happiness"),
        (
            "life_expectancy_available",
            np.isfinite(grid["life_expectancy"]),
            "missing_life_expectancy",
        ),
        ("population_available", np.isfinite(grid["population"]), "missing_population"),
        ("positive_population", grid["population"].gt(0), "nonpositive_population"),
        ("aqli_available", np.isfinite(grid["aqli_years_lost"]), "missing_aqli"),
        ("primary_ghg_available", np.isfinite(grid["ghg_total"]), "missing_ghg_total"),
    )
    before = len(grid)
    for stage_name, condition, terminal_reason in rules:
        failed = eligible & ~condition
        stage.loc[failed] = stage_name
        reason.loc[failed] = terminal_reason
        eligible &= condition
        flow_rows.append(_flow_row(stage_name, eligible, grid, before=before))
        before = int(eligible.sum())

    maximal = grid.loc[eligible, SAMPLE_COLUMNS].copy()
    counts = maximal.groupby("iso3", sort=True)["year"].nunique()
    balanced_iso3 = set(counts[counts.eq(len(years))].index)
    balanced_mask = eligible & grid["iso3"].isin(balanced_iso3)
    unbalanced = eligible & ~balanced_mask
    stage.loc[unbalanced] = "balanced_three_year_panel"
    reason.loc[unbalanced] = "not_balanced_across_configured_years"
    flow_rows.append(
        _flow_row(
            "balanced_three_year_panel",
            balanced_mask,
            grid,
            before=int(eligible.sum()),
        )
    )

    balanced = grid.loc[balanced_mask, SAMPLE_COLUMNS].copy()
    maximal = maximal.sort_values(["year", "iso3"], kind="stable", ignore_index=True)
    balanced = balanced.sort_values(["year", "iso3"], kind="stable", ignore_index=True)
    exclusions = grid.loc[~balanced_mask, ["year", "iso3"]].copy()
    exclusions["stage"] = stage.loc[~balanced_mask].to_numpy()
    exclusions["reason"] = reason.loc[~balanced_mask].to_numpy()
    exclusions = exclusions.loc[:, EXCLUSION_COLUMNS].sort_values(
        ["year", "iso3"], kind="stable", ignore_index=True
    )
    if exclusions[["stage", "reason"]].isna().any().any():
        raise SampleInputError("sample exclusion lacks a terminal reason")
    if len(exclusions) + len(balanced) != len(grid):
        raise SampleInputError("sample flow does not partition source country-years")
    flow = pd.DataFrame.from_records(flow_rows, columns=FLOW_COLUMNS)
    return SampleResult(
        maximal_complete_case=maximal,
        balanced_panel=balanced,
        exclusions=exclusions,
        flow=flow,
    )
