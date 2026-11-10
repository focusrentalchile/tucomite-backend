"""Building wall and sales feed domain records."""

from dataclasses import dataclass


WALL_KIND_WALL = "wall"
WALL_KIND_SALE = "sale"
WALL_KINDS = frozenset({WALL_KIND_WALL, WALL_KIND_SALE})


class BuildingWallPostNotFound(Exception):
    """Raised when a wall post id does not exist."""


class InvalidBuildingWallKind(Exception):
    """Raised when the post kind is not wall or sale."""


@dataclass(frozen=True, slots=True)
class BuildingWallPostRecord:
    """One public post on the building wall or sales board."""

    id: str
    client_id: str
    author_user_id: str
    author_name: str
    kind: str
    body: str
    title: str | None
    price: str | None
    image_name: str | None
    image_url: str | None
    created_at: str
