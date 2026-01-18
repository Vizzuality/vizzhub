from pydantic import BaseModel


class TargetsConfig(BaseModel):
    """Target values for normalization."""

    defect_density: float
    escaped_rate: float
    mttr_hours: float
    spi: float
    cpi: float
    lead_time_days: float
    flow_efficiency: float
    high_vuln_count: int
    gov_exceptions: int
    pr_no_review_ratio: float


class GlobalWeights(BaseModel):
    """Global dimension weights."""

    time: float
    cost: float
    quality: float
    value: float
    satisfaction: float
    flow: float
    engineering: float
    risk: float


class ConstantsConfig(BaseModel):
    """System constants."""

    sev1_cap: int
    grace_days: int


class ScoringConfigModel(BaseModel):
    """Complete scoring configuration."""

    targets: TargetsConfig
    global_weights: GlobalWeights
    constants: ConstantsConfig
    weight_validation: dict[str, bool]
