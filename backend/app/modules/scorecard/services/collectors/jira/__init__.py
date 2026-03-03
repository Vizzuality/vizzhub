"""
Jira collectors package.

Each indicator has its own module with:
- SPEC documentation at the top
- collect_* function for data collection
- calculate_* function for computation (where applicable)
"""

from app.modules.scorecard.services.collectors.jira.client import JiraClient
from app.modules.scorecard.services.collectors.jira.collector import JiraCollector
from app.modules.scorecard.services.collectors.jira.commitment_reliability import (
    collect_commitment_reliability,
)
from app.modules.scorecard.services.collectors.jira.defect_density import (
    calculate_defect_density,
    collect_defect_density,
)
from app.modules.scorecard.services.collectors.jira.escaped_rate import (
    calculate_escaped_rate,
    collect_escaped_rate,
)
from app.modules.scorecard.services.collectors.jira.lead_time import collect_lead_time
from app.modules.scorecard.services.collectors.jira.mttr import collect_mttr
from app.modules.scorecard.services.collectors.jira.story_review_ratio import (
    calculate_story_review_ratio,
    collect_story_review_ratio,
)

__all__ = [
    # Main classes
    "JiraClient",
    "JiraCollector",
    # defect_density
    "collect_defect_density",
    "calculate_defect_density",
    # escaped_rate
    "collect_escaped_rate",
    "calculate_escaped_rate",
    # mttr
    "collect_mttr",
    # story_review_ratio
    "collect_story_review_ratio",
    "calculate_story_review_ratio",
    # commitment_reliability
    "collect_commitment_reliability",
    # lead_time
    "collect_lead_time",
]
