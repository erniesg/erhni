"""Pure in-memory graph for the primary ERHNI analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from erhni.allocation import allocate_wld_responsibility
from erhni.config import MethodConfig
from erhni.countries import CountryCrosswalk
from erhni.metrics import apply_erhni, build_aqli_burden, happiness_weights, nhly
from erhni.sample import SampleInputError, build_balanced_sample


PIPELINE_EXCLUSION_COLUMNS = ("universe", "year", "iso3", "stage", "reason")
COUNTRY_YEAR_COLUMNS = (
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
    "population_weighted_happiness",
    "net_weight",
    "gross_weight",
    "nhly",
    "source_share",
    "allocated_happy_person_years",
    "penalty",
    "erhni",
    "rank",
)
YEAR_SUMMARY_COLUMNS = (
    "year",
    "balanced_country_count",
    "population_weighted_happiness",
    "net_weight",
    "gross_weight",
    "burden_universe_count",
    "burden_person_years",
    "weighted_aqli_burden",
    "wld_total",
    "country_source_count",
    "country_source_share",
    "ranking_source_share",
    "out_of_sample_country_share",
    "missing_population_source_share",
    "wld_reconciliation_residual_share",
    "wld_reconciliation_residual_allocation",
    "total_conserved_allocation",
)


class PipelineInputError(ValueError):
    """Raised when the normalized in-memory model graph is inconsistent."""


@dataclass(frozen=True, slots=True)
class PrimaryResult:
    """All named in-memory products of the primary ERHNI specification."""

    country_year: pd.DataFrame
    burden_universe: pd.DataFrame
    allocation_ledger: pd.DataFrame
    exclusions: pd.DataFrame
    sample_flow: pd.DataFrame
    year_summary: pd.DataFrame


def _validate_universes(method: MethodConfig) -> None:
    expected = {
        "burden_universe": "aqli_full_wdi_population",
        "allocation_denominator": "wdi_wld",
        "happiness_weight_universe": "balanced_analysis_panel",
        "ranking_universe": "balanced_complete_case",
    }
    for field, value in expected.items():
        if getattr(method, field) != value:
            raise PipelineInputError(f"unsupported {field}: {getattr(method, field)}")


def _validate_identity_contract(
    crosswalk: CountryCrosswalk,
    regions: pd.DataFrame,
) -> None:
    included = {
        decision.iso3
        for decision in crosswalk.decisions
        if decision.status == "include" and decision.iso3 is not None
    }
    region_ids = set(regions["iso3"].astype(str)) if "iso3" in regions else set()
    if not included or included != region_ids:
        raise PipelineInputError(
            "crosswalk include decisions and region identities must agree exactly"
        )


def _wdi_roles(wdi: pd.DataFrame, years: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {"year", "iso3", "record_type", "population", "ghg_total"}
    missing = sorted(required - set(wdi.columns))
    if missing:
        raise PipelineInputError(f"WDI input lacks required columns: {', '.join(missing)}")
    if not set(wdi["record_type"]).issubset({"country", "world"}):
        raise PipelineInputError("WDI normalized rows contain an unsupported record type")
    countries = wdi.loc[wdi["record_type"].eq("country")].copy()
    world = wdi.loc[wdi["record_type"].eq("world")].copy()
    if set(world["iso3"]) != {"WLD"}:
        raise PipelineInputError("official WLD must be the sole world denominator identity")
    if world.duplicated(["year", "iso3"]).any() or len(world) != len(years):
        raise PipelineInputError("WDI input must contain one WLD observation per year")
    if set(pd.to_numeric(world["year"], errors="coerce")) != set(years):
        raise PipelineInputError("WLD observations do not cover configured years")
    world["ghg_total"] = pd.to_numeric(world["ghg_total"], errors="coerce")
    if not np.isfinite(world["ghg_total"]).all() or (world["ghg_total"] <= 0).any():
        raise PipelineInputError("official WLD GHG totals must be finite and positive")
    countries["population"] = pd.to_numeric(countries["population"], errors="coerce")
    countries["ghg_total"] = pd.to_numeric(countries["ghg_total"], errors="coerce")
    finite_ghg = np.isfinite(countries["ghg_total"])
    if (countries.loc[finite_ghg, "ghg_total"] < 0).any():
        raise PipelineInputError("country GHG allocation inputs cannot be negative")
    return (
        countries.sort_values(["year", "iso3"], kind="stable", ignore_index=True),
        world.sort_values("year", kind="stable", ignore_index=True),
    )


def _pipeline_exclusions(
    sample_exclusions: pd.DataFrame,
    burden_exclusions: pd.DataFrame,
    countries: pd.DataFrame,
) -> pd.DataFrame:
    ranking = sample_exclusions.copy()
    ranking.insert(0, "universe", "ranking")
    burden = burden_exclusions.copy()
    burden.insert(0, "universe", "burden")
    burden.insert(3, "stage", "burden_universe")
    missing_ghg = countries.loc[
        ~np.isfinite(countries["ghg_total"]), ["year", "iso3"]
    ].copy()
    missing_ghg.insert(0, "universe", "allocation")
    missing_ghg["stage"] = "allocation_source"
    missing_ghg["reason"] = "missing_ghg_total"
    combined = pd.concat(
        [
            ranking.loc[:, PIPELINE_EXCLUSION_COLUMNS],
            burden.loc[:, PIPELINE_EXCLUSION_COLUMNS],
            missing_ghg.loc[:, PIPELINE_EXCLUSION_COLUMNS],
        ],
        ignore_index=True,
    ).sort_values(
        ["universe", "year", "iso3"], kind="stable", ignore_index=True
    )
    if combined.duplicated(["universe", "year", "iso3"]).any():
        raise PipelineInputError("pipeline exclusions contain multiple terminal reasons")
    if combined[["stage", "reason"]].isna().any().any():
        raise PipelineInputError("pipeline exclusion lacks a terminal reason")
    return combined


def build_primary_model(
    method: MethodConfig,
    happiness: pd.DataFrame,
    wdi: pd.DataFrame,
    aqli: pd.DataFrame,
    crosswalk: CountryCrosswalk,
    regions: pd.DataFrame,
) -> PrimaryResult:
    """Build the approved annual primary model without filesystem side effects."""

    _validate_universes(method)
    _validate_identity_contract(crosswalk, regions)
    try:
        sample = build_balanced_sample(method, happiness, wdi, aqli, regions)
    except SampleInputError as error:
        raise PipelineInputError(str(error)) from error
    if sample.balanced_panel.empty:
        raise PipelineInputError("balanced analysis panel is empty")
    if set(sample.balanced_panel["year"]) != set(method.years):
        raise PipelineInputError("balanced analysis panel lacks configured years")

    countries, world = _wdi_roles(wdi, method.years)
    burden = build_aqli_burden(
        aqli.loc[:, ["year", "iso3", "aqli_years_lost"]],
        countries.loc[:, ["year", "iso3", "population"]],
    )
    burden_by_year = burden.year_summary.set_index("year")
    if set(burden_by_year.index) != set(method.years):
        raise PipelineInputError("burden universe lacks configured years")

    ledger_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, float | int]] = []
    balanced_ids = set(sample.balanced_panel["iso3"])
    for year in method.years:
        ranked_year = sample.balanced_panel.loc[
            sample.balanced_panel["year"].eq(year)
        ]
        weight_summary = happiness_weights(
            ranked_year["life_ladder"].to_numpy(),
            ranked_year["population"].to_numpy(),
            neutral=method.neutral_point,
            scale=method.nhly_scale,
        )
        weight_rows.append(
            {
                "year": year,
                "population_weighted_happiness": weight_summary.population_weighted_happiness,
                "net_weight": weight_summary.net_weight,
                "gross_weight": weight_summary.gross_weight,
            }
        )
        country_year = countries.loc[countries["year"].eq(year)].copy()
        valid_source = np.isfinite(country_year["ghg_total"])
        allocation_input = country_year.loc[
            valid_source, ["iso3", "ghg_total", "population"]
        ].rename(columns={"ghg_total": "emissions"})
        wld_total = float(world.loc[world["year"].eq(year), "ghg_total"].item())
        burden_count = int(burden_by_year.loc[year, "burden_universe_count"])
        burden_person_years = float(
            burden_by_year.loc[year, "burden_person_years"]
        )
        allocation = allocate_wld_responsibility(
            allocation_input,
            burden_person_years=burden_person_years,
            weight=weight_summary.net_weight,
            wld_total=wld_total,
            max_abs_residual_share=method.max_abs_wld_reconciliation_share,
        )
        year_ledger = allocation.ledger.copy()
        year_ledger.insert(0, "year", year)
        year_ledger.insert(1, "allocation_key", "ghg_total")
        ledger_frames.append(year_ledger)

        source_rows = year_ledger.loc[year_ledger["ledger_role"].eq("country")]
        ranking_share = float(
            source_rows.loc[source_rows["iso3"].isin(balanced_ids), "source_share"].sum()
        )
        out_of_sample_share = float(
            source_rows.loc[~source_rows["iso3"].isin(balanced_ids), "source_share"].sum()
        )
        missing_population_share = float(
            source_rows.loc[
                source_rows["penalty_status"].ne("available"), "source_share"
            ].sum()
        )
        summary_rows.append(
            {
                "year": year,
                "balanced_country_count": int(ranked_year["iso3"].nunique()),
                "population_weighted_happiness": weight_summary.population_weighted_happiness,
                "net_weight": weight_summary.net_weight,
                "gross_weight": weight_summary.gross_weight,
                "burden_universe_count": burden_count,
                "burden_person_years": burden_person_years,
                "weighted_aqli_burden": weight_summary.net_weight
                * burden_person_years,
                "wld_total": wld_total,
                "country_source_count": allocation.summary.source_row_count,
                "country_source_share": allocation.summary.country_share_sum,
                "ranking_source_share": ranking_share,
                "out_of_sample_country_share": out_of_sample_share,
                "missing_population_source_share": missing_population_share,
                "wld_reconciliation_residual_share": allocation.summary.residual_share,
                "wld_reconciliation_residual_allocation": allocation.summary.residual_allocation,
                "total_conserved_allocation": allocation.summary.total_allocation,
            }
        )

    allocation_ledger = pd.concat(ledger_frames, ignore_index=True).sort_values(
        ["year", "ledger_role", "iso3"], kind="stable", ignore_index=True
    )
    weights = pd.DataFrame.from_records(weight_rows)
    panel = sample.balanced_panel.merge(
        weights,
        on="year",
        how="left",
        validate="many_to_one",
    )
    penalties = allocation_ledger.loc[
        allocation_ledger["ledger_role"].eq("country"),
        [
            "year",
            "iso3",
            "source_share",
            "allocated_happy_person_years",
            "penalty_per_resident",
        ],
    ].rename(columns={"penalty_per_resident": "penalty"})
    panel = panel.merge(
        penalties,
        on=["year", "iso3"],
        how="left",
        validate="one_to_one",
    )
    if panel[["source_share", "allocated_happy_person_years", "penalty"]].isna().any().any():
        raise PipelineInputError("balanced panel lacks a defined allocation penalty")
    panel["nhly"] = nhly(
        panel["life_ladder"].to_numpy(),
        panel["life_expectancy"].to_numpy(),
        neutral=method.neutral_point,
        scale=method.nhly_scale,
    )
    panel["erhni"] = apply_erhni(
        panel["nhly"].to_numpy(), panel["penalty"].to_numpy()
    )
    panel = panel.sort_values(
        ["year", "erhni", "iso3"],
        ascending=[True, False, True],
        kind="stable",
        ignore_index=True,
    )
    panel["rank"] = panel.groupby("year", sort=False).cumcount() + 1
    country_year = panel.loc[:, COUNTRY_YEAR_COLUMNS]

    year_summary = pd.DataFrame.from_records(summary_rows).loc[
        :, YEAR_SUMMARY_COLUMNS
    ]
    year_summary = year_summary.sort_values("year", kind="stable", ignore_index=True)
    ledger_total = allocation_ledger.groupby("year", sort=True)[
        "allocated_happy_person_years"
    ].sum()
    target = year_summary.set_index("year")["weighted_aqli_burden"]
    if not np.allclose(
        ledger_total.to_numpy(),
        target.to_numpy(),
        rtol=method.relative_tolerance,
        atol=method.absolute_tolerance,
    ):
        raise PipelineInputError("allocation ledger does not conserve annual burden")

    exclusions = _pipeline_exclusions(
        sample.exclusions,
        burden.exclusions,
        countries,
    )
    burden_universe = burden.universe.sort_values(
        ["year", "iso3"], kind="stable", ignore_index=True
    )
    return PrimaryResult(
        country_year=country_year,
        burden_universe=burden_universe,
        allocation_ledger=allocation_ledger,
        exclusions=exclusions,
        sample_flow=sample.flow,
        year_summary=year_summary,
    )
