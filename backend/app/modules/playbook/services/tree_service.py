"""Tree operations for playbook nodes.

Delegates to core TreeService, re-exports for backward compatibility.
"""

from app.core.services.tree_service import MAX_DEPTH, TreeService, generate_slug
from app.modules.playbook.models.node import PlaybookNodeDB

_tree = TreeService(PlaybookNodeDB)

ensure_unique_slug = _tree.ensure_unique_slug
get_next_position = _tree.get_next_position
validate_depth = _tree.validate_depth
validate_not_circular = _tree.validate_not_circular

__all__ = [
    "MAX_DEPTH",
    "generate_slug",
    "ensure_unique_slug",
    "get_next_position",
    "validate_depth",
    "validate_not_circular",
]
