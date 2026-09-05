from dataclasses import dataclass, field

Box = tuple[float, float, float, float]


class ProcessingError(ValueError):
    """Safe, content-free message suitable for display to a user."""


@dataclass(frozen=True)
class Entity:
    entity_id: str
    type: str
    text: str
    start: int
    end: int
    page: int | None
    boxes: tuple[Box, ...]
    source: str = "regex"
    confidence: float | None = None


@dataclass
class PageText:
    page: int | None
    text: str
    char_boxes: list[Box | None]


@dataclass
class Analysis:
    pages: list[PageText]
    entities: list[Entity]
    warnings: list[str] = field(default_factory=list)
