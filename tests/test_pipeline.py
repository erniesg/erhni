from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from erhni.countries import CountryCrosswalk, CountryDecision
from erhni.pipeline import build_primary_model


YEARS = (2016, 2017, 2018)


def _crosswalk() -> CountryCrosswalk:
    decisions = []
    for source in ("whr", "aqli", "wdi"):
        for iso3, name in (("AAA", "Alpha"), ("BBB", "Beta"), ("CCC", "Gamma")):
            decisions.append(
                CountryDecision(
                    source=source,
                    source_name=iso3,
                    iso3=iso3,
                    display_name=name,
                    status="include",
                    reason="Reviewed synthetic identity",
                )
            )
    decisions.append(
        CountryDecision(
            source="wdi",
            source_name="WLD",
            iso3="WLD",
            display_name="World",
            status="aggregate",
            reason="Official allocation denominator",
        )
    )
    return CountryCrosswalk(decisions)


def _primary_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    happiness_rows = []
    for iso3 in ("AAA", "BBB"):
        for year in YEARS:
            happiness_rows.append(
                {
                    "source": "whr",
                    "year": year,
                    "iso3": iso3,
                    "display_name": iso3,
                    "life_ladder": 6.0,
                    "imputed": False,
                }
            )
    # Gamma is complete in one year but not balanced; its high score must not
    # enter that year's population-weighted happiness weight.
    happiness_rows.append(
        {
            "source": "whr",
            "year": 2016,
            "iso3": "CCC",
            "display_name": "CCC",
            "life_ladder": 10.0,
            "imputed": False,
        }
    )
    happiness = pd.DataFrame(happiness_rows)

    wdi_rows = []
    for year in YEARS:
        for iso3, population, emissions in (
            ("AAA", 100.0, 10.0),
            ("BBB", 300.0, 30.0),
            ("CCC", 600.0, 57.0),
        ):
            wdi_rows.append(
                {
                    "source": "wdi",
                    "year": year,
                    "iso3": iso3,
                    "display_name": iso3,
                    "record_type": "country",
                    "population": population,
                    "life_expectancy": 80.0,
                    "ghg_total": emissions,
                    "ghg_co2": emissions * 0.5,
                    "ghg_ch4": emissions * 0.3,
                    "ghg_n2o": emissions * 0.2,
                    "imputed": False,
                }
            )
        wdi_rows.append(
            {
                "source": "wdi",
                "year": year,
                "iso3": "WLD",
                "display_name": "World",
                "record_type": "world",
                "population": 1_000.0,
                "life_expectancy": 75.0,
                "ghg_total": 100.0,
                "ghg_co2": 50.0,
                "ghg_ch4": 30.0,
                "ghg_n2o": 20.0,
                "imputed": False,
            }
        )
    wdi = pd.DataFrame(wdi_rows)
    aqli = pd.DataFrame(
        [
            {
                "source": "aqli",
                "year": year,
                "iso3": iso3,
                "display_name": iso3,
                "aqli_years_lost": 1.0,
                "imputed": False,
            }
            for year in YEARS
            for iso3 in ("AAA", "BBB", "CCC")
        ]
    )
    regions = pd.DataFrame(
        {
            "iso3": ["AAA", "BBB", "CCC"],
            "display_name": ["Alpha", "Beta", "Gamma"],
            "source_region": ["Synthetic", "Synthetic", "Synthetic"],
            "display_region": ["Synthetic", "Synthetic", "Synthetic"],
        }
    )
    return happiness, wdi, aqli, regions


@pytest.fixture
def primary_result(method):
    happiness, wdi, aqli, regions = _primary_inputs()
    return build_primary_model(
        method,
        happiness,
        wdi,
        aqli,
        _crosswalk(),
        regions,
    )


def test_primary_model_invariants(primary_result) -> None:
    panel = primary_result.country_year
    assert set(panel.year) == {2016, 2017, 2018}
    assert panel.groupby("iso3").size().eq(3).all()
    np.testing.assert_allclose(
        panel.erhni,
        panel.nhly - panel.penalty,
        rtol=1e-12,
        atol=1e-12,
    )
    ledger = primary_result.allocation_ledger.groupby(
        "year", as_index=True
    ).allocated_happy_person_years.sum()
    target = primary_result.year_summary.set_index("year").weighted_aqli_burden
    assert ledger.index.equals(target.index)
    np.testing.assert_allclose(
        ledger.to_numpy(),
        target.to_numpy(),
        rtol=1e-12,
        atol=1e-6,
    )
    assert set(
        primary_result.allocation_ledger.query(
            "ledger_role == 'wld_reconciliation_residual'"
        ).year
    ) == {2016, 2017, 2018}


def test_weight_uses_only_balanced_panel_but_other_universes_do_not(primary_result) -> None:
    summary = primary_result.year_summary.set_index("year")

    assert summary["population_weighted_happiness"].eq(6.0).all()
    np.testing.assert_allclose(summary["net_weight"], 0.1)
    np.testing.assert_allclose(summary["gross_weight"], 0.6)
    assert summary["balanced_country_count"].eq(2).all()
    assert summary["burden_universe_count"].eq(3).all()
    country_ledger = primary_result.allocation_ledger.query("ledger_role == 'country'")
    assert country_ledger.groupby("year")["iso3"].nunique().eq(3).all()
    np.testing.assert_allclose(summary["ranking_source_share"], 0.4)
    np.testing.assert_allclose(summary["out_of_sample_country_share"], 0.57)
    np.testing.assert_allclose(summary["wld_reconciliation_residual_share"], 0.03)


def test_rank_ties_break_by_iso3_after_metric(primary_result) -> None:
    for _, year in primary_result.country_year.groupby("year", sort=True):
        assert list(year["iso3"]) == ["AAA", "BBB"]
        assert list(year["rank"]) == [1, 2]
        assert year["erhni"].nunique() == 1


def test_every_pipeline_exclusion_has_one_terminal_reason(primary_result) -> None:
    exclusions = primary_result.exclusions

    assert not exclusions.duplicated(["universe", "year", "iso3"]).any()
    assert exclusions[["universe", "stage", "reason"]].notna().all().all()
    ranking = exclusions.query("universe == 'ranking'")
    assert set(ranking["iso3"]) == {"CCC"}
    assert len(ranking) == 3


def test_primary_model_is_invariant_to_input_row_order(method) -> None:
    happiness, wdi, aqli, regions = _primary_inputs()
    forward = build_primary_model(
        method,
        happiness,
        wdi,
        aqli,
        _crosswalk(),
        regions,
    )
    reverse = build_primary_model(
        method,
        happiness.iloc[::-1].reset_index(drop=True),
        wdi.iloc[::-1].reset_index(drop=True),
        aqli.iloc[::-1].reset_index(drop=True),
        _crosswalk(),
        regions.iloc[::-1].reset_index(drop=True),
    )

    for field in (
        "country_year",
        "burden_universe",
        "allocation_ledger",
        "exclusions",
        "sample_flow",
        "year_summary",
    ):
        pd.testing.assert_frame_equal(getattr(forward, field), getattr(reverse, field))
