from decimal import Decimal
from functools import lru_cache

from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = ""
    debug: bool = False
    cors_origins: list[str] = []

    # Security
    jwt_secret_key: str = ""
    jwt_expire_hours: int = 24
    session_secret_key: str = ""
    oauth_encryption_key: str = ""

    # Google OAuth (for user authentication)
    google_client_id: str = ""
    google_client_secret: str = ""
    allowed_google_domain: str = "vizzuality.com"
    initial_admin_email: str = ""

    # Legacy Jira auth (API Token - still supported for simple setups)
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    # OAuth 2.0 for Jira (recommended)
    jira_oauth_client_id: str = ""
    jira_oauth_client_secret: str = ""
    jira_oauth_redirect_uri: str = ""
    jira_oauth_scopes: str = ""

    # GitHub (OAuth client credentials only; PAT stored in DB via integrations)
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    # Google Workspace Admin SDK (ISO module)
    google_workspace_client_id: str = ""
    google_workspace_client_secret: str = ""

    # Redis (for async job queue)
    redis_host: str = ""
    redis_port: int = 6379
    redis_password: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins_production(
        cls, v: list[str], info: ValidationInfo
    ) -> list[str]:
        """Validate CORS origins - reject localhost in production."""
        debug = info.data.get("debug", False)
        if not debug:
            # Production mode - reject localhost origins
            for origin in v:
                if "localhost" in origin or "127.0.0.1" in origin:
                    raise ValueError(
                        f"Localhost origin '{origin}' not allowed in production mode. "
                        "Set DEBUG=true for development or update CORS_ORIGINS."
                    )
        return v


class ScoringConfig:
    """
    Provides access to scoring configuration from database.

    Configuration is loaded from the config_parameters table and cached in memory.
    Call load_from_db() to refresh from database.
    """

    # Parameter name mappings: internal name -> DB name
    _TARGET_NAMES = {
        "defect_density": "target_defect_density",
        "escaped_rate": "target_escaped_rate",
        "mttr_hours": "target_mttr_hours",
        "spi": "target_spi",
        "cpi": "target_cpi",
        "milestones_on_time": "target_milestones_on_time",
        "lead_time_days": "target_lead_time_days",
        "high_vuln_count": "target_high_vuln_count",
        "gov_exceptions": "target_gov_exceptions",
        "pr_no_review_ratio": "target_pr_no_review_ratio",
        "pr_size_lines": "target_pr_size_lines",
        "review_turnaround_hours": "target_review_turnaround_hours",
        "deployment_frequency": "target_deployment_frequency",
        "change_failure_rate": "target_change_failure_rate",
        "post_contract_tasks": "target_post_contract_tasks",
        "test_maturity": "target_test_maturity",
        "architecture": "target_architecture",
        "pm_satisfaction": "target_pm_satisfaction",
        "client_satisfaction": "target_client_satisfaction",
        "story_review_ratio": "target_story_review_ratio",
        "commitment_reliability": "target_commitment_reliability",
    }

    _CONSTANT_NAMES = {
        "sev1_cap": "const_sev1_cap",
        "grace_days": "const_grace_days",
    }

    _IDEAL_NAMES = {
        "spi": "ideal_spi",
        "cpi": "ideal_cpi",
    }

    # Weight group mappings: (group, internal_name) -> DB name
    _WEIGHT_NAMES = {
        # Global weights
        ("global", "time"): "weight_global_time",
        ("global", "cost"): "weight_global_cost",
        ("global", "quality"): "weight_global_quality",
        ("global", "value"): "weight_global_value",
        ("global", "satisfaction"): "weight_global_satisfaction",
        ("global", "flow"): "weight_global_flow",
        ("global", "engineering"): "weight_global_engineering",
        ("global", "risk"): "weight_global_risk",
        # Time weights
        ("time", "spi"): "weight_time_spi",
        ("time", "milestones"): "weight_time_milestones",
        # Cost weights
        ("cost", "cpi"): "weight_cost_cpi",
        ("cost", "variance"): "weight_cost_variance",
        # Quality weights
        ("quality", "defect_density"): "weight_quality_defect_density",
        ("quality", "escaped_rate"): "weight_quality_escaped_rate",
        ("quality", "mttr"): "weight_quality_mttr",
        ("quality", "story_review"): "weight_quality_story_review",
        ("quality", "governance"): "weight_quality_governance",
        ("quality", "pr_review"): "weight_quality_pr_review",
        ("quality", "change_failure_rate"): "weight_quality_change_failure_rate",
        ("quality", "post_contract_tasks"): "weight_quality_post_contract_tasks",
        # Value weights
        ("value", "okr_impact"): "weight_value_okr_impact",
        # Satisfaction weights
        ("satisfaction", "client_survey"): "weight_satisfaction_client_survey",
        ("satisfaction", "pm_estimation"): "weight_satisfaction_pm_estimation",
        # Client survey weights
        ("client_survey", "understanding"): "weight_survey_understanding",
        ("client_survey", "proactivity"): "weight_survey_proactivity",
        ("client_survey", "communication"): "weight_survey_communication",
        ("client_survey", "time"): "weight_survey_time",
        ("client_survey", "response"): "weight_survey_response",
        ("client_survey", "quality"): "weight_survey_quality",
        ("client_survey", "expectations"): "weight_survey_expectations",
        ("client_survey", "recommend"): "weight_survey_recommend",
        # Flow weights
        ("flow", "lead_time"): "weight_flow_lead_time",
        ("flow", "commitment_reliability"): "weight_flow_commitment_reliability",
        ("flow", "pr_size"): "weight_flow_pr_size",
        ("flow", "review_turnaround"): "weight_flow_review_turnaround",
        ("flow", "deployment_frequency"): "weight_flow_deployment_frequency",
        # Engineering weights
        ("engineering", "test_maturity"): "weight_engineering_test_maturity",
        ("engineering", "pr_review"): "weight_engineering_pr_review",
        ("engineering", "architecture"): "weight_engineering_architecture",
        # Risk weights
        ("risk", "pr_no_review"): "weight_risk_pr_no_review",
        ("risk", "high_vulns"): "weight_risk_high_vulns",
        # Test maturity weights
        ("test_maturity", "e2e"): "weight_test_e2e",
        ("test_maturity", "unit"): "weight_test_unit",
        ("test_maturity", "accessibility"): "weight_test_accessibility",
        ("test_maturity", "security"): "weight_test_security",
        ("test_maturity", "frontend"): "weight_test_frontend",
    }

    def __init__(self, config_dict: dict[str, Decimal] | None = None):
        """
        Initialize ScoringConfig.

        Args:
            config_dict: Dict mapping parameter names to values.
                        If None, must call load_from_db() before using.
        """
        self._config: dict[str, Decimal] = config_dict or {}

    def load_from_dict(self, config_dict: dict[str, Decimal]) -> None:
        """Load configuration from a dictionary."""
        self._config = config_dict

    def get_target(self, name: str) -> float:
        """Get a target value by internal name."""
        db_name = self._TARGET_NAMES.get(name, f"target_{name}")
        value = self._config.get(db_name)
        if value is None:
            return 1.0
        return float(value)

    def get_weight(self, group: str, name: str) -> float:
        """Get a weight value by group and internal name."""
        db_name = self._WEIGHT_NAMES.get((group, name))
        if db_name is None:
            return 0.0
        value = self._config.get(db_name)
        if value is None:
            return 0.0
        return float(value)

    def get_constant(self, name: str) -> float:
        """Get a constant value by internal name."""
        db_name = self._CONSTANT_NAMES.get(name, f"const_{name}")
        value = self._config.get(db_name)
        if value is None:
            return 0.0
        return float(value)

    def get_ideal(self, name: str) -> float:
        """Get an ideal value by internal name."""
        db_name = self._IDEAL_NAMES.get(name, f"ideal_{name}")
        value = self._config.get(db_name)
        if value is None:
            return 1.0
        return float(value)

    def get_global_weight(self, dimension: str) -> float:
        """Get a global dimension weight."""
        return self.get_weight("global", dimension)

    def get_all_weights(self) -> dict[str, float]:
        """Get all weights as a flat dictionary for snapshotting."""
        return {
            db_name: float(self._config.get(db_name, 0))
            for db_name in self._WEIGHT_NAMES.values()
        }

    def get_all_targets(self) -> dict[str, float]:
        """Get all targets as a flat dictionary for snapshotting."""
        result = {}
        for db_name in self._TARGET_NAMES.values():
            result[db_name] = float(self._config.get(db_name, 1.0))
        for db_name in self._IDEAL_NAMES.values():
            result[db_name] = float(self._config.get(db_name, 1.0))
        for db_name in self._CONSTANT_NAMES.values():
            result[db_name] = float(self._config.get(db_name, 0))
        return result

    def validate_weights(self) -> dict[str, bool]:
        """Validate that all weight groups sum to 1."""
        groups = {
            "Global Weights": [
                "time",
                "cost",
                "quality",
                "value",
                "satisfaction",
                "flow",
                "engineering",
                "risk",
            ],
            "Time Weights": ["spi", "milestones"],
            "Cost Weights": ["cpi", "variance"],
            "Quality Weights": [
                "defect_density",
                "escaped_rate",
                "mttr",
                "story_review",
                "governance",
                "pr_review",
                "change_failure_rate",
                "post_contract_tasks",
            ],
            "Value Weights": ["okr_impact"],
            "Satisfaction Weights": ["client_survey", "pm_estimation"],
            "Client Survey Weights": [
                "understanding",
                "proactivity",
                "communication",
                "time",
                "response",
                "quality",
                "expectations",
                "recommend",
            ],
            "Flow Weights": [
                "lead_time",
                "commitment_reliability",
                "pr_size",
                "review_turnaround",
                "deployment_frequency",
            ],
            "Engineering Weights": ["test_maturity", "pr_review", "architecture"],
            "Risk Weights": ["pr_no_review", "high_vulns"],
            "Test Maturity Weights": [
                "e2e",
                "unit",
                "accessibility",
                "security",
                "frontend",
            ],
        }

        # Map display names to internal group names
        group_key_map = {
            "Global Weights": "global",
            "Time Weights": "time",
            "Cost Weights": "cost",
            "Quality Weights": "quality",
            "Value Weights": "value",
            "Satisfaction Weights": "satisfaction",
            "Client Survey Weights": "client_survey",
            "Flow Weights": "flow",
            "Engineering Weights": "engineering",
            "Risk Weights": "risk",
            "Test Maturity Weights": "test_maturity",
        }

        results = {}
        for display_name, weight_names in groups.items():
            group_key = group_key_map[display_name]
            total = sum(self.get_weight(group_key, name) for name in weight_names)
            results[display_name] = abs(total - 1.0) < 0.001

        return results


# Global config instance - must be initialized at startup
_scoring_config: ScoringConfig | None = None


async def load_scoring_config_from_db() -> ScoringConfig:
    """
    Load scoring config from database.

    This should be called at app startup to initialize the global config.
    """
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.modules.scorecard.models.config import ConfigParameter

    async with async_session_maker() as db:
        result = await db.execute(select(ConfigParameter))
        parameters = result.scalars().all()

        config_dict = {p.name: p.value for p in parameters}

    global _scoring_config
    _scoring_config = ScoringConfig(config_dict)
    return _scoring_config


def get_scoring_config() -> ScoringConfig:
    """
    Get the global scoring config instance.

    Must call load_scoring_config_from_db() at startup before using.
    """
    global _scoring_config
    if _scoring_config is None:
        # Fallback for tests - create empty config
        _scoring_config = ScoringConfig({})
    return _scoring_config


def set_scoring_config(config: ScoringConfig) -> None:
    """Set the global scoring config (for testing)."""
    global _scoring_config
    _scoring_config = config


@lru_cache
def get_settings() -> Settings:
    return Settings()
