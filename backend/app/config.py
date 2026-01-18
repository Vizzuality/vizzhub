from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    github_token: str = ""
    github_org: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ScoringConfig:
    """Loads and provides access to scoring configuration from YAML."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "scoring_config.yaml"
        self._config = self._load_config(config_path)

    def _load_config(self, path: Path) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    @property
    def targets(self) -> dict[str, float]:
        return self._config.get("targets", {})

    @property
    def weights(self) -> dict[str, dict[str, float]]:
        return self._config.get("weights", {})

    @property
    def constants(self) -> dict[str, float]:
        return self._config.get("constants", {})

    def get_target(self, name: str) -> float:
        return self.targets.get(name, 1.0)

    def get_weight(self, group: str, name: str) -> float:
        return self.weights.get(group, {}).get(name, 0.0)

    def get_constant(self, name: str) -> float:
        return self.constants.get(name, 0.0)

    def get_global_weight(self, dimension: str) -> float:
        return self.weights.get("global", {}).get(dimension, 0.0)

    def validate_weights(self) -> dict[str, bool]:
        """Validate that all weight groups sum to 1."""
        results = {}
        for group_name, group_weights in self.weights.items():
            if isinstance(group_weights, dict):
                total = sum(group_weights.values())
                results[group_name] = abs(total - 1.0) < 0.001
        return results


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_scoring_config() -> ScoringConfig:
    return ScoringConfig()
