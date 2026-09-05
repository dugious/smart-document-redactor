import html
import pymupdf
from smart_redactor.schemas import Entity, ProcessingError

COLOR_MAP = {
    'PERSON': (0.13, 0.53, 0.82),      # Blue
    'EMAIL': (0.05, 0.58, 0.45),       # Teal / Emerald
    'PHONE': (0.85, 0.45, 0.12),       # Orange
    'CREDIT_CARD': (0.82, 0.20, 0.20), # Red
    'ADDRESS': (0.55, 0.32, 0.72),     # Purple
}

CSS_COLOR_MAP = {
    'PERSON': '#2185d0',
    'EMAIL': '#087f6c',
    'PHONE': '#d97706',
    'CREDIT_CARD': '#dc2626',
    'ADDRESS': '#7c3aed',
}


def preview_pdf(data: bytes, page_number: int, max_side: int = 1100,
                highlight_entities: list[Entity] | None = None) -> bytes:
    """Render only one page as bounded PNG; optionally draw colored outline boxes on entities."""
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            if not 1 <= page_number <= len(doc) or not 100 <= max_side <= 1600:
                raise ProcessingError('Invalid preview request.')
            page = doc[page_number - 1]
            if highlight_entities:
                for entity in highlight_entities:
                    if entity.page == page_number:
                        color = COLOR_MAP.get(entity.type, (0.4, 0.4, 0.4))
                        for box in entity.boxes:
                            rect = pymupdf.Rect(box)
                            page.draw_rect(rect, color=color, width=1.5, fill=None)
            largest = max(page.rect.width, page.rect.height)
            if largest <= 0:
                raise ProcessingError('Invalid page dimensions.')
            scale = min(1.5, max_side / largest)
            return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError('Preview could not be rendered.') from None


def highlight_txt(text: str, entities: list[Entity], max_chars: int = 20_000) -> str:
    """Render HTML with colored badges over highlighted entity spans; escape all other text."""
    bounded = text[:max_chars]
    visible_entities = [e for e in entities if e.start < max_chars]
    # Sort by start offset
    visible_entities = sorted(visible_entities, key=lambda e: (e.start, e.end))
    
    pieces = []
    cursor = 0
    for entity in visible_entities:
        if entity.start < cursor:
            continue  # Skip overlapping in display
        end = min(entity.end, max_chars)
        # Text before entity
        pieces.append(html.escape(bounded[cursor:entity.start]))
        # Entity with colored background badge
        ent_text = html.escape(bounded[entity.start:end])
        color = CSS_COLOR_MAP.get(entity.type, '#4b5563')
        badge = (f'<mark style="background-color: {color}22; color: {color}; '
                 f'border: 1px solid {color}88; border-radius: 4px; padding: 2px 4px; font-weight: 600;" '
                 f'title="{entity.type} [{entity.source}]">{ent_text}'
                 f'<span style="font-size: 0.7em; margin-left: 4px; opacity: 0.85; text-transform: uppercase;">'
                 f'({entity.type})</span></mark>')
        pieces.append(badge)
        cursor = end
    pieces.append(html.escape(bounded[cursor:]))
    html_content = ''.join(pieces).replace('\n', '<br>')
    return (f'<div style="font-family: monospace; font-size: 0.88rem; line-height: 1.6; '
            f'background: #ffffff; padding: 16px; border: 1px solid #dce7e4; '
            f'border-radius: 10px; max-height: 500px; overflow-y: auto;">{html_content}</div>')
