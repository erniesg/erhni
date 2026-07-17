from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from erhni.allocation import (
    AllocationInputError,
    ResidualShareError,
    allocate_wld_responsibility,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "iso3": ["AAA", "BBB"],
            "emissions": [20.0, 70.0],
            "population": [100.0, 350.0],
        }
    )


def test_wld_allocation_fixture_conserves_signed_residual() -> None:
    result = allocate_wld_responsibility(
        _fixture(),
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        # The exact fixture has a 0.10 residual, so it exercises conservation
        # at that explicit bound rather than the stricter primary-run bound.
        max_abs_residual_share=0.10,
    )
    countries = result.ledger.query("ledger_role == 'country'").set_index("iso3")
    residual = result.ledger.query(
        "ledger_role == 'wld_reconciliation_residual'"
    ).iloc[0]

    assert countries.loc["AAA", "source_share"] == pytest.approx(0.2)
    assert countries.loc["BBB", "source_share"] == pytest.approx(0.7)
    assert countries.loc["AAA", "allocated_happy_person_years"] == pytest.approx(7.0)
    assert countries.loc["BBB", "allocated_happy_person_years"] == pytest.approx(24.5)
    assert countries.loc["AAA", "penalty_per_resident"] == pytest.approx(0.07)
    assert countries.loc["BBB", "penalty_per_resident"] == pytest.approx(0.07)
    assert residual["source_share"] == pytest.approx(0.1)
    assert residual["allocated_happy_person_years"] == pytest.approx(3.5)
    assert result.summary.residual_share == pytest.approx(0.1)
    assert result.summary.total_allocation == pytest.approx(35.0)
    assert result.ledger["allocated_happy_person_years"].sum() == pytest.approx(35.0)


def test_country_shares_use_wld_and_are_never_sample_renormalized() -> None:
    result = allocate_wld_responsibility(
        _fixture(),
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.2,
    )
    countries = result.ledger.query("ledger_role == 'country'")

    assert countries["source_share"].sum() == pytest.approx(0.9)
    assert not np.isclose(countries["source_share"].sum(), 1.0)
    assert result.summary.wld_total == pytest.approx(100.0)


def test_signed_residual_can_be_negative_within_bound() -> None:
    frame = _fixture().assign(emissions=[30.0, 74.0])
    result = allocate_wld_responsibility(
        frame,
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.05,
    )

    assert result.summary.residual_share == pytest.approx(-0.04)
    assert result.summary.residual_allocation == pytest.approx(-1.4)
    assert result.summary.total_allocation == pytest.approx(35.0)


def test_residual_outside_primary_bound_fails() -> None:
    with pytest.raises(ResidualShareError, match="0.05"):
        allocate_wld_responsibility(
            _fixture().assign(emissions=[20.0, 74.0]),
            burden_person_years=700.0,
            weight=0.05,
            wld_total=100.0,
            max_abs_residual_share=0.05,
        )


def test_residual_exactly_at_primary_bound_is_allowed() -> None:
    result = allocate_wld_responsibility(
        _fixture().assign(emissions=[20.0, 75.0]),
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.05,
    )

    assert result.summary.residual_share == pytest.approx(0.05)


def test_missing_population_keeps_total_allocation_without_penalty() -> None:
    frame = _fixture().assign(population=[np.nan, 350.0])
    result = allocate_wld_responsibility(
        frame,
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.2,
    )
    aaa = result.ledger.set_index("iso3").loc["AAA"]

    assert aaa["allocated_happy_person_years"] == pytest.approx(7.0)
    assert pd.isna(aaa["penalty_per_resident"])
    assert aaa["penalty_status"] == "missing_or_nonpositive_population"
    assert result.summary.total_allocation == pytest.approx(35.0)


def test_allocation_is_row_order_invariant() -> None:
    forward = allocate_wld_responsibility(
        _fixture(),
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.2,
    )
    reverse = allocate_wld_responsibility(
        _fixture().iloc[::-1].reset_index(drop=True),
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.2,
    )

    pd.testing.assert_frame_equal(forward.ledger, reverse.ledger)
    assert forward.summary == reverse.summary


def test_common_population_scale_leaves_per_resident_penalty_invariant() -> None:
    base = allocate_wld_responsibility(
        _fixture(),
        burden_person_years=700.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.2,
    )
    scaled = allocate_wld_responsibility(
        _fixture().assign(population=[1_000.0, 3_500.0]),
        burden_person_years=7_000.0,
        weight=0.05,
        wld_total=100.0,
        max_abs_residual_share=0.2,
    )
    base_penalty = base.ledger.query("ledger_role == 'country'")["penalty_per_resident"]
    scaled_penalty = scaled.ledger.query("ledger_role == 'country'")["penalty_per_resident"]

    np.testing.assert_allclose(base_penalty, scaled_penalty)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("emissions", -1.0, "nonnegative"),
        ("emissions", np.nan, "finite"),
        ("wld_total", 0.0, "WLD"),
        ("burden_person_years", np.inf, "burden"),
        ("weight", 0.0, "weight"),
        ("max_abs_residual_share", -0.1, "bound"),
    ],
)
def test_allocation_rejects_invalid_scientific_inputs(
    field: str, value: float, message: str
) -> None:
    frame = _fixture()
    kwargs = {
        "burden_person_years": 700.0,
        "weight": 0.05,
        "wld_total": 100.0,
        "max_abs_residual_share": 0.2,
    }
    if field == "emissions":
        frame.loc[0, "emissions"] = value
    else:
        kwargs[field] = value

    with pytest.raises(AllocationInputError, match=message):
        allocate_wld_responsibility(frame, **kwargs)


def test_allocation_rejects_duplicate_source_rows() -> None:
    frame = pd.concat([_fixture(), _fixture().iloc[[0]]], ignore_index=True)
    with pytest.raises(AllocationInputError, match="duplicate"):
        allocate_wld_responsibility(
            frame,
            burden_person_years=700.0,
            weight=0.05,
            wld_total=100.0,
            max_abs_residual_share=0.2,
        )


def test_scientific_kernel_imports_no_file_or_network_modules() -> None:
    prohibited = {"argparse", "csv", "json", "os", "pathlib", "requests", "urllib"}
    for relative in ("src/erhni/metrics.py", "src/erhni/allocation.py"):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports |= {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not imports & prohibited
