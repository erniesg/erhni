from __future__ import annotations

import pandas as pd
import pytest

from erhni.sample import SampleInputError, build_balanced_sample


YEARS = (2016, 2017, 2018)


def _sample_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    happiness = pd.DataFrame(
        [
            {"year": year, "iso3": iso3, "life_ladder": 6.0, "imputed": False}
            for iso3, years in {
                "AAA": YEARS,
                "BBB": (2016, 2017),
                "CCC": YEARS,
            }.items()
            for year in years
        ]
    )
    wdi_rows = []
    for year in YEARS:
        for iso3 in ("AAA", "BBB", "CCC"):
            wdi_rows.append(
                {
                    "year": year,
                    "iso3": iso3,
                    "record_type": "country",
                    "population": 100.0,
                    "life_expectancy": (
                        float("nan") if (iso3, year) == ("CCC", 2017) else 80.0
                    ),
                    "ghg_total": 10.0,
                    "ghg_co2": 5.0,
                    "ghg_ch4": 3.0,
                    "ghg_n2o": 2.0,
                    "imputed": False,
                }
            )
    wdi = pd.DataFrame(wdi_rows)
    aqli = pd.DataFrame(
        [
            {
                "year": year,
                "iso3": iso3,
                "aqli_years_lost": 1.0,
                "imputed": False,
            }
            for iso3 in ("AAA", "BBB", "CCC")
            for year in YEARS
        ]
    )
    regions = pd.DataFrame(
        {
            "iso3": ["AAA", "BBB", "CCC"],
            "display_name": ["Alpha", "Beta", "Gamma"],
            "source_region": ["Region", "Region", "Region"],
            "display_region": ["Region", "Region", "Region"],
        }
    )
    return happiness, wdi, aqli, regions


def test_balanced_flow_counts_are_computed_from_rows(method) -> None:
    happiness, wdi, aqli, regions = _sample_inputs()
    result = build_balanced_sample(method, happiness, wdi, aqli, regions)
    flow = result.flow.set_index("stage")

    assert flow.loc["source_union", "eligible_country_year_rows"] == 9
    assert flow.loc["happiness_available", "eligible_country_year_rows"] == 8
    assert flow.loc["life_expectancy_available", "eligible_country_year_rows"] == 7
    assert flow.loc["balanced_three_year_panel", "eligible_country_year_rows"] == 3
    assert flow.loc["balanced_three_year_panel", "eligible_countries"] == 1
    assert set(result.balanced_panel["iso3"]) == {"AAA"}

    changed = happiness.loc[
        ~(
            happiness["iso3"].eq("AAA")
            & happiness["year"].eq(2018)
        )
    ]
    changed_result = build_balanced_sample(method, changed, wdi, aqli, regions)
    changed_final = changed_result.flow.set_index("stage").loc[
        "balanced_three_year_panel"
    ]
    assert changed_final["eligible_country_year_rows"] == 0
    assert changed_final["eligible_countries"] == 0


def test_every_nonselected_country_year_has_one_terminal_reason(method) -> None:
    result = build_balanced_sample(method, *_sample_inputs())
    exclusions = result.exclusions

    assert len(exclusions) == 6
    assert not exclusions.duplicated(["year", "iso3"]).any()
    assert exclusions[["stage", "reason"]].notna().all().all()
    assert set(exclusions["reason"]) == {
        "missing_happiness",
        "missing_life_expectancy",
        "not_balanced_across_configured_years",
    }


def test_balanced_panel_has_exact_configured_years_unique_keys_and_no_imputation(
    method,
) -> None:
    result = build_balanced_sample(method, *_sample_inputs())
    panel = result.balanced_panel

    assert set(panel["year"]) == set(YEARS)
    assert panel.groupby("iso3").size().eq(len(YEARS)).all()
    assert not panel.duplicated(["year", "iso3"]).any()
    assert list(panel.sort_values(["year", "iso3"])["iso3"]) == ["AAA"] * 3


def test_sample_construction_is_row_order_invariant(method) -> None:
    happiness, wdi, aqli, regions = _sample_inputs()
    forward = build_balanced_sample(method, happiness, wdi, aqli, regions)
    reverse = build_balanced_sample(
        method,
        happiness.iloc[::-1].reset_index(drop=True),
        wdi.iloc[::-1].reset_index(drop=True),
        aqli.iloc[::-1].reset_index(drop=True),
        regions.iloc[::-1].reset_index(drop=True),
    )

    pd.testing.assert_frame_equal(forward.maximal_complete_case, reverse.maximal_complete_case)
    pd.testing.assert_frame_equal(forward.balanced_panel, reverse.balanced_panel)
    pd.testing.assert_frame_equal(forward.exclusions, reverse.exclusions)
    pd.testing.assert_frame_equal(forward.flow, reverse.flow)


def test_sample_rejects_duplicate_or_imputed_inputs(method) -> None:
    happiness, wdi, aqli, regions = _sample_inputs()
    duplicated = pd.concat([happiness, happiness.iloc[[0]]], ignore_index=True)
    with pytest.raises(SampleInputError, match="duplicate"):
        build_balanced_sample(method, duplicated, wdi, aqli, regions)

    imputed = happiness.copy()
    imputed.loc[0, "imputed"] = True
    with pytest.raises(SampleInputError, match="imputed"):
        build_balanced_sample(method, imputed, wdi, aqli, regions)
