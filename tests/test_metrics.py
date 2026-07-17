from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from erhni.metrics import (
    MetricInputError,
    NonPositiveWeightError,
    apply_erhni,
    build_aqli_burden,
    gross_lost_year_weight,
    happiness_weights,
    net_lost_year_weight,
    nhly,
    three_gas_co2e,
)


def test_nhly() -> None:
    assert nhly(
        happiness=6.0,
        life_expectancy=80.0,
        neutral=5.0,
        scale=10.0,
    ) == pytest.approx(8.0)


def test_nhly_is_vectorized_and_fails_on_invalid_inputs() -> None:
    result = nhly(
        happiness=np.array([4.0, 6.0]),
        life_expectancy=np.array([70.0, 80.0]),
        neutral=5.0,
        scale=10.0,
    )
    np.testing.assert_allclose(result, [-7.0, 8.0])
    with pytest.raises(MetricInputError, match="finite"):
        nhly(np.array([np.nan]), np.array([80.0]), neutral=5.0, scale=10.0)
    with pytest.raises(MetricInputError, match="same shape"):
        nhly(np.array([4.0, 6.0]), np.array([80.0]), neutral=5.0, scale=10.0)
    with pytest.raises(MetricInputError, match="scale"):
        nhly(6.0, 80.0, neutral=5.0, scale=0.0)


def test_population_weighted_net_weight() -> None:
    # H=[4,6], N=[1,3] => Hbar=5.5, w=.05
    assert net_lost_year_weight(
        [4.0, 6.0], [1.0, 3.0], neutral=5.0
    ) == pytest.approx(0.05)


def test_happiness_weight_summary_is_named_and_population_scale_invariant() -> None:
    base = happiness_weights([4.0, 6.0], [1.0, 3.0], neutral=5.0)
    scaled = happiness_weights([4.0, 6.0], [1_000.0, 3_000.0], neutral=5.0)

    assert base.population_weighted_happiness == pytest.approx(5.5)
    assert base.net_weight == pytest.approx(0.05)
    assert base.gross_weight == pytest.approx(0.55)
    assert base.observation_count == 2
    assert scaled == base


def test_nonpositive_weight_is_an_error() -> None:
    with pytest.raises(NonPositiveWeightError):
        net_lost_year_weight([4.0, 6.0], [1.0, 1.0], neutral=5.0)
    with pytest.raises(NonPositiveWeightError):
        net_lost_year_weight([3.0, 4.0], [1.0, 1.0], neutral=5.0)


def test_weight_inputs_must_be_finite_and_populations_positive() -> None:
    with pytest.raises(MetricInputError, match="population"):
        happiness_weights([5.0], [0.0], neutral=5.0)
    with pytest.raises(MetricInputError, match="finite"):
        happiness_weights([np.inf], [1.0], neutral=5.0)
    with pytest.raises(MetricInputError, match="nonempty"):
        happiness_weights([], [], neutral=5.0)


def test_gross_minus_net_weight_is_one_half() -> None:
    assert gross_lost_year_weight(
        [4.0, 6.0], [1.0, 3.0]
    ) - net_lost_year_weight(
        [4.0, 6.0], [1.0, 3.0], neutral=5.0
    ) == pytest.approx(0.5)


def test_erhni_is_nhly_minus_penalty_row_by_row() -> None:
    result = apply_erhni(np.array([8.0, -7.0]), np.array([0.07, 0.5]))
    np.testing.assert_allclose(result, [7.93, -7.5], rtol=1e-12, atol=1e-12)
    with pytest.raises(MetricInputError, match="same shape"):
        apply_erhni(np.array([1.0, 2.0]), np.array([1.0]))


def test_corrected_three_gas_is_direct_co2e_sum_without_gwp_multiplier() -> None:
    result = three_gas_co2e(
        co2e=np.array([1.0, 10.0]),
        ch4e=np.array([2.0, 20.0]),
        n2oe=np.array([3.0, 30.0]),
    )
    np.testing.assert_allclose(result, [6.0, 60.0])
    with pytest.raises(MetricInputError, match="nonnegative"):
        three_gas_co2e([-1.0], [2.0], [3.0])


def _aqli_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    aqli = pd.DataFrame(
        {
            "year": [2016, 2016, 2016, 2016, 2016],
            "iso3": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "aqli_years_lost": [0.0, 2.0, 1.0, 3.0, np.nan],
        }
    )
    population = pd.DataFrame(
        {
            "year": [2016, 2016, 2016, 2016],
            "iso3": ["AAA", "BBB", "CCC", "DDD"],
            "population": [100.0, 200.0, 0.0, np.inf],
        }
    )
    return aqli, population


def test_aqli_burden_uses_full_valid_universe_and_keeps_zero_loss() -> None:
    aqli, population = _aqli_fixture()
    result = build_aqli_burden(aqli, population)

    assert list(result.universe["iso3"]) == ["AAA", "BBB"]
    assert result.universe.loc[result.universe["iso3"].eq("AAA"), "aqli_years_lost"].item() == 0
    assert result.year_summary.loc[0, "burden_universe_count"] == 2
    assert result.year_summary.loc[0, "burden_person_years"] == pytest.approx(400.0)
    assert set(result.exclusions["iso3"]) == {"CCC", "DDD", "EEE"}
    assert set(result.exclusions["reason"]) == {
        "nonpositive_wdi_population",
        "nonfinite_wdi_population",
        "nonfinite_aqli_years_lost",
    }


def test_aqli_missing_population_mapping_is_an_explicit_exclusion() -> None:
    aqli = pd.DataFrame(
        {"year": [2016], "iso3": ["AAA"], "aqli_years_lost": [1.0]}
    )
    population = pd.DataFrame(columns=["year", "iso3", "population"])

    result = build_aqli_burden(aqli, population)

    assert result.universe.empty
    assert result.year_summary.to_dict("records") == [
        {"year": 2016, "burden_universe_count": 0, "burden_person_years": 0.0}
    ]
    assert result.exclusions.to_dict("records") == [
        {"year": 2016, "iso3": "AAA", "reason": "missing_wdi_population_mapping"}
    ]


@pytest.mark.parametrize("kind", ["aqli", "population"])
def test_aqli_burden_rejects_duplicate_country_year_keys(kind: str) -> None:
    aqli = pd.DataFrame(
        {"year": [2016], "iso3": ["AAA"], "aqli_years_lost": [1.0]}
    )
    population = pd.DataFrame(
        {"year": [2016], "iso3": ["AAA"], "population": [100.0]}
    )
    if kind == "aqli":
        aqli = pd.concat([aqli, aqli], ignore_index=True)
    else:
        population = pd.concat([population, population], ignore_index=True)

    with pytest.raises(MetricInputError, match="duplicate"):
        build_aqli_burden(aqli, population)


def test_aqli_burden_rejects_negative_loss() -> None:
    aqli = pd.DataFrame(
        {"year": [2016], "iso3": ["AAA"], "aqli_years_lost": [-0.1]}
    )
    population = pd.DataFrame(
        {"year": [2016], "iso3": ["AAA"], "population": [100.0]}
    )

    with pytest.raises(MetricInputError, match="negative"):
        build_aqli_burden(aqli, population)


def test_aqli_burden_is_row_order_invariant() -> None:
    aqli, population = _aqli_fixture()
    forward = build_aqli_burden(aqli, population)
    reverse = build_aqli_burden(
        aqli.iloc[::-1].reset_index(drop=True),
        population.iloc[::-1].reset_index(drop=True),
    )

    pd.testing.assert_frame_equal(forward.universe, reverse.universe)
    pd.testing.assert_frame_equal(forward.exclusions, reverse.exclusions)
    pd.testing.assert_frame_equal(forward.year_summary, reverse.year_summary)


def test_common_population_scale_scales_total_burden_only() -> None:
    aqli = pd.DataFrame(
        {
            "year": [2016, 2016],
            "iso3": ["AAA", "BBB"],
            "aqli_years_lost": [0.0, 2.0],
        }
    )
    population = pd.DataFrame(
        {
            "year": [2016, 2016],
            "iso3": ["AAA", "BBB"],
            "population": [100.0, 200.0],
        }
    )

    base = build_aqli_burden(aqli, population)
    scaled = build_aqli_burden(aqli, population.assign(population=lambda x: x.population * 10))

    assert scaled.year_summary.loc[0, "burden_universe_count"] == 2
    assert scaled.year_summary.loc[0, "burden_person_years"] == pytest.approx(
        10 * base.year_summary.loc[0, "burden_person_years"]
    )
