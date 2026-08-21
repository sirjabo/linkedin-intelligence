"""Sprint L — A/B Experiment endpoints.

POST /experiments/assign   — assign a unit to a variant
POST /experiments/test     — run hypothesis test on two variant outcome sets
GET  /experiments          — list pre-built experiments
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.learning_loop import (
    APPLY_THRESHOLD_EXPERIMENT,
    DET_WEIGHT_EXPERIMENT,
    ABExperiment,
    hypothesis_test,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])

_EXPERIMENTS: dict[str, ABExperiment] = {
    DET_WEIGHT_EXPERIMENT.experiment_id: DET_WEIGHT_EXPERIMENT,
    APPLY_THRESHOLD_EXPERIMENT.experiment_id: APPLY_THRESHOLD_EXPERIMENT,
}


class AssignRequest(BaseModel):
    experiment_id: str
    unit_id: str  # candidate_id, session_id, etc.


class AssignResponse(BaseModel):
    experiment_id: str
    unit_id: str
    variant_name: str
    variant_description: str
    config: dict


class HypothesisRequest(BaseModel):
    variant_a_name: str = "control"
    variant_b_name: str = "treatment"
    outcomes_a: list[dict]  # each: {"outcome": str | None}
    outcomes_b: list[dict]


@router.get("")
async def list_experiments() -> list[dict]:
    """List all pre-built A/B experiments."""
    return [
        {
            "experiment_id": exp.experiment_id,
            "description": exp.description,
            "variants": [
                {"name": v.name, "description": v.description, "config": v.config}
                for v in exp.variants
            ],
            "traffic_split": exp.traffic_split,
        }
        for exp in _EXPERIMENTS.values()
    ]


@router.post("/assign", response_model=AssignResponse)
async def assign_variant(body: AssignRequest) -> AssignResponse:
    """Deterministically assign a unit to an experiment variant.

    Returns the variant name, description, and config for the unit.
    Assignment is stable: the same unit_id always gets the same variant.
    """
    exp = _EXPERIMENTS.get(body.experiment_id)
    if exp is None:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment '{body.experiment_id}' not found. "
                   f"Available: {list(_EXPERIMENTS.keys())}",
        )
    variant = exp.assign(body.unit_id)
    return AssignResponse(
        experiment_id=body.experiment_id,
        unit_id=body.unit_id,
        variant_name=variant.name,
        variant_description=variant.description,
        config=variant.config,
    )


@router.post("/test")
async def run_hypothesis_test(body: HypothesisRequest) -> dict:
    """Run a two-proportion z-test comparing interview rates between two variants.

    Pass outcome arrays for both variants; each entry is {outcome: str | None}.
    Outcome values: "got_interview", "offer", "rejected", "ghosted", "withdrew", null.
    Returns p_value, significance, and a human-readable summary.
    """
    result = hypothesis_test(
        outcomes_a=body.outcomes_a,
        outcomes_b=body.outcomes_b,
        variant_a_name=body.variant_a_name,
        variant_b_name=body.variant_b_name,
    )
    return {
        "variant_a": result.variant_a,
        "variant_b": result.variant_b,
        "interview_rate_a": result.interview_rate_a,
        "interview_rate_b": result.interview_rate_b,
        "p_value": result.p_value,
        "significant": result.significant,
        "direction": result.direction,
        "summary": result.summary,
    }
