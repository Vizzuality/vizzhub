"""
Base collector interface.

Design Principle: Collectors ONLY collect data. They do not interpret, normalize,
or assign meaning to the data. All scoring logic belongs in normalizers and calculators.

This separation ensures:
- Easier auditing of scoring logic
- Clear separation of concerns
- Changes to scoring don't require collector updates
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Abstract base class for data collectors."""

    @abstractmethod
    async def collect(self, **kwargs: Any) -> dict[str, Any]:
        """
        Collect raw data from the source.

        Returns:
            dict: Raw data as collected, without interpretation.
                  Callers should not assume the data is validated or normalized.
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the collector can connect to its data source."""
        pass
