"""Public interface for the events module.

Other modules should import from here, never from events internals.
"""

from app.modules.events.services.event_service import list_events, load_attendee_details
from app.modules.events.services.stats_service import get_stats

__all__ = ["get_stats", "list_events", "load_attendee_details"]
