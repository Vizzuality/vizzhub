"""Configuration endpoints."""

from fastapi import APIRouter

from app.api.deps import ScoringConfigDep
from app.models.config import (
    ConstantsConfig,
    GlobalWeights,
    ScoringConfigModel,
    TargetsConfig,
)

router = APIRouter()


@router.get("", response_model=ScoringConfigModel)
async def get_scoring_config(config: ScoringConfigDep) -> ScoringConfigModel:
    """Get current scoring configuration."""
    return ScoringConfigModel(
        targets=TargetsConfig(
            defect_density=config.get_target("defect_density"),
            escaped_rate=config.get_target("escaped_rate"),
            mttr_hours=config.get_target("mttr_hours"),
            spi=config.get_target("spi"),
            cpi=config.get_target("cpi"),
            lead_time_days=config.get_target("lead_time_days"),
            flow_efficiency=config.get_target("flow_efficiency"),
            high_vuln_count=int(config.get_target("high_vuln_count")),
            gov_exceptions=int(config.get_target("gov_exceptions")),
            pr_no_review_ratio=config.get_target("pr_no_review_ratio"),
        ),
        global_weights=GlobalWeights(
            time=config.get_global_weight("time"),
            cost=config.get_global_weight("cost"),
            quality=config.get_global_weight("quality"),
            value=config.get_global_weight("value"),
            satisfaction=config.get_global_weight("satisfaction"),
            flow=config.get_global_weight("flow"),
            engineering=config.get_global_weight("engineering"),
            risk=config.get_global_weight("risk"),
        ),
        constants=ConstantsConfig(
            sev1_cap=int(config.get_constant("sev1_cap")),
            grace_days=int(config.get_constant("grace_days")),
        ),
        weight_validation=config.validate_weights(),
    )


@router.get("/validate")
async def validate_config(config: ScoringConfigDep) -> dict[str, bool | dict]:
    """Validate that all weight groups sum to 1."""
    validation = config.validate_weights()
    all_valid = all(validation.values())
    return {
        "valid": all_valid,
        "groups": validation,
    }
