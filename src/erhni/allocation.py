"""Pure WLD-denominator responsibility allocation with exact conservation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


LEDGER_COLUMNS = (
    "iso3",
    "ledger_role",
    "emissions",
    "wld_total",
    "source_share",
    "burden_person_years",
    "weight",
    "allocated_happy_person_years",
    "population",
    "penalty_per_resident",
    "penalty_status",
)


class AllocationInputError(ValueError):
    """Raised when allocation inputs violate the scientific contract."""


class ResidualShareError(AllocationInputError):
    """Raised when the signed WLD reconciliation residual exceeds its bound."""


@dataclass(frozen=True, slots=True)
class AllocationSummary:
    """Named WLD allocation diagnostics for one year and one allocation key."""

    source_row_count: int
    burden_person_years: float
    weight: float
    wld_total: float
    country_share_sum: float
    residual_share: float
    residual_allocation: float
    total_allocation: float


@dataclass(frozen=True, slots=True)
class AllocationResult:
    """Full source ledger, including the signed WLD reconciliation row."""

    ledger: pd.DataFrame
    summary: AllocationSummary


def _finite_scalar(value: float, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise AllocationInputError(f"{label} must be numeric") from error
    if not np.isfinite(result):
        raise AllocationInputError(f"{label} must be finite")
    return result


def allocate_wld_responsibility(
    sources: pd.DataFrame,
    *,
    burden_person_years: float,
    weight: float,
    wld_total: float,
    max_abs_residual_share: float,
) -> AllocationResult:
    """Allocate `weight * burden` by unrenormalized source/WLD shares."""

    required = {"iso3", "emissions", "population"}
    missing = sorted(required - set(sources.columns))
    if missing:
        raise AllocationInputError(
            f"allocation sources lack required columns: {', '.join(missing)}"
        )
    if sources.empty:
        raise AllocationInputError("allocation sources must be nonempty")
    if sources["iso3"].isna().any() or sources["iso3"].astype(str).eq("").any():
        raise AllocationInputError("allocation sources contain a missing ISO3")
    if sources["iso3"].duplicated().any():
        raise AllocationInputError("allocation sources contain duplicate ISO3 rows")

    burden = _finite_scalar(burden_person_years, "burden person-years")
    if burden < 0:
        raise AllocationInputError("burden person-years must be nonnegative")
    weight_value = _finite_scalar(weight, "weight")
    if weight_value <= 0:
        raise AllocationInputError("weight must be positive")
    world = _finite_scalar(wld_total, "WLD total")
    if world <= 0:
        raise AllocationInputError("WLD total must be positive")
    bound = _finite_scalar(max_abs_residual_share, "residual-share bound")
    if bound < 0:
        raise AllocationInputError("residual-share bound must be nonnegative")

    frame = sources.loc[:, ["iso3", "emissions", "population"]].copy()
    frame["iso3"] = frame["iso3"].astype(str)
    try:
        frame["emissions"] = pd.to_numeric(frame["emissions"], errors="raise")
    except (TypeError, ValueError) as error:
        raise AllocationInputError("emissions must be numeric") from error
    if not np.isfinite(frame["emissions"]).all():
        raise AllocationInputError("emissions must be finite")
    if (frame["emissions"] < 0).any():
        raise AllocationInputError("emissions must be nonnegative")
    frame["population"] = pd.to_numeric(frame["population"], errors="coerce")
    frame = frame.sort_values("iso3", kind="stable", ignore_index=True)

    frame["ledger_role"] = "country"
    frame["wld_total"] = world
    frame["source_share"] = frame["emissions"] / world
    frame["burden_person_years"] = burden
    frame["weight"] = weight_value
    target = weight_value * burden
    frame["allocated_happy_person_years"] = target * frame["source_share"]
    population_valid = np.isfinite(frame["population"]) & frame["population"].gt(0)
    frame["penalty_per_resident"] = np.where(
        population_valid,
        frame["allocated_happy_person_years"] / frame["population"],
        np.nan,
    )
    frame["penalty_status"] = np.where(
        population_valid,
        "available",
        "missing_or_nonpositive_population",
    )

    country_share_sum = float(frame["source_share"].sum())
    residual_share = 1.0 - country_share_sum
    if abs(residual_share) > bound and not np.isclose(
        abs(residual_share), bound, rtol=0.0, atol=1e-12
    ):
        raise ResidualShareError(
            "absolute WLD reconciliation residual share "
            f"{abs(residual_share):.15g} exceeds bound {bound:.15g}"
        )
    residual_allocation = residual_share * target
    residual = pd.DataFrame(
        [
            {
                "iso3": "WLD_RESIDUAL",
                "ledger_role": "wld_reconciliation_residual",
                "emissions": world - float(frame["emissions"].sum()),
                "wld_total": world,
                "source_share": residual_share,
                "burden_person_years": burden,
                "weight": weight_value,
                "allocated_happy_person_years": residual_allocation,
                "population": np.nan,
                "penalty_per_resident": np.nan,
                "penalty_status": "not_applicable",
            }
        ]
    )
    ledger = pd.concat([frame, residual], ignore_index=True).loc[:, LEDGER_COLUMNS]
    total_allocation = float(ledger["allocated_happy_person_years"].sum())
    if not np.isclose(total_allocation, target, rtol=1e-12, atol=1e-9):
        raise AllocationInputError("WLD allocation does not conserve weighted burden")
    return AllocationResult(
        ledger=ledger,
        summary=AllocationSummary(
            source_row_count=len(frame),
            burden_person_years=burden,
            weight=weight_value,
            wld_total=world,
            country_share_sum=country_share_sum,
            residual_share=residual_share,
            residual_allocation=residual_allocation,
            total_allocation=total_allocation,
        ),
    )
