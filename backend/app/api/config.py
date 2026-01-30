"""Configuration endpoints."""

import logging

from fastapi import APIRouter, Request
from pydantic import ValidationError

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, limiter
from app.core.error_handler import ValidationErrorHandler
from app.models.config import (
    ConfigParameterResponse,
    ConfigParameterUpdate,
    ConstantsConfig,
    GlobalWeights,
    IdealsConfig,
    ScoringConfigModel,
    TargetsConfig,
)
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=ScoringConfigModel)
@limiter.limit("100/minute")
async def get_scoring_config(
    request: Request, current_user: CurrentUser, config: ScoringConfigDep
) -> ScoringConfigModel:
    """Get current scoring configuration. Requires authentication."""
    return ScoringConfigModel(
        targets=TargetsConfig(
            defect_density=config.get_target("defect_density"),
            escaped_rate=config.get_target("escaped_rate"),
            mttr_hours=config.get_target("mttr_hours"),
            spi=config.get_target("spi"),
            cpi=config.get_target("cpi"),
            lead_time_days=config.get_target("lead_time_days"),
            high_vuln_count=int(config.get_target("high_vuln_count")),
            gov_exceptions=int(config.get_target("gov_exceptions")),
            pr_no_review_ratio=config.get_target("pr_no_review_ratio"),
            story_review_ratio=config.get_target("story_review_ratio"),
            client_satisfaction=config.get_target("client_satisfaction"),
            architecture=config.get_target("architecture"),
            commitment_reliability=config.get_target("commitment_reliability"),
            milestones_on_time=config.get_target("milestones_on_time"),
            test_maturity=config.get_target("test_maturity"),
            pm_satisfaction=config.get_target("pm_satisfaction"),
            deployment_frequency=config.get_target("deployment_frequency"),
            change_failure_rate=config.get_target("change_failure_rate"),
            pr_size_lines=config.get_target("pr_size_lines"),
            review_turnaround_hours=config.get_target("review_turnaround_hours"),
            post_contract_tasks=int(config.get_target("post_contract_tasks")),
            budget_variance=config.get_target("budget_variance"),
            governance_compliance=config.get_target("governance_compliance"),
            okr_impact=config.get_target("okr_impact"),
        ),
        ideals=IdealsConfig(
            spi=config.get_ideal("spi"),
            cpi=config.get_ideal("cpi"),
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
@limiter.limit("100/minute")
async def validate_config(
    request: Request, current_user: CurrentUser, db: DBSession
) -> dict[str, bool | list[str]]:
    """Validate that all weight groups sum to 1. Requires authentication."""
    errors = await ConfigService.validate_weight_groups(db)
    return {"valid": len(errors) == 0, "errors": errors}


@router.get("/parameters")
@limiter.limit("100/minute")
async def get_config_parameters(
    request: Request, current_user: CurrentUser, db: DBSession
) -> dict[str, list[ConfigParameterResponse]]:
    """Get all config parameters grouped by category. Requires authentication."""
    parameters = await ConfigService.get_all_parameters(db)

    # Convert to response models
    response = {}
    for category, params in parameters.items():
        response[category] = [
            ConfigParameterResponse.model_validate(p) for p in params
        ]

    return response


@router.put("/parameters")
@limiter.limit("10/minute")
async def update_config_parameters(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    updates: list[ConfigParameterUpdate],
) -> dict[str, str]:
    """Update multiple config parameters. Validates weight groups. Requires authentication."""
    try:
        await ConfigService.update_parameters(db, updates)
        return {"status": "success"}
    except (ValidationError, ValueError) as e:
        raise ValidationErrorHandler.to_http_exception(e)
    except Exception as e:
        logger.exception("Unexpected error updating config parameters")
        raise ValidationErrorHandler.to_http_exception(e)
