from smart_redactor.schemas import Analysis, Entity, PageText, ProcessingError
from smart_redactor.detection.ner import NerBackend, detect_all
from smart_redactor.extraction.pdf import MAX_BYTES, MAX_CHARS


def decode_txt(data: bytes) -> str:
    if not data or len(data) > MAX_BYTES:
        raise ProcessingError('TXT is empty or exceeds 10 MiB.')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ProcessingError('TXT must use UTF-8 encoding.') from None
    if not text or len(text) > MAX_CHARS or any(ord(c) < 32 and c not in '\t\r\n' for c in text):
        raise ProcessingError('TXT is empty, too long, or contains unsupported control characters.')
    return text


def analyze_txt(data: bytes, backend: NerBackend | None = None) -> Analysis:
    text = decode_txt(data)
    entities = [Entity(f'txt:{c.start}:{c.end}:{c.type}', c.type, c.text, c.start, c.end, None, (), c.source, c.confidence)
                for c in detect_all(text, backend)]
    return Analysis([PageText(None, text, [])], entities)


def process_txt(data: bytes, selected_ids: list[str] | None = None, backend: NerBackend | None = None) -> tuple[Analysis, bytes]:
    analysis = analyze_txt(data, backend)
    text = analysis.pages[0].text
    ids = {e.entity_id for e in analysis.entities} if selected_ids is None else set(selected_ids)
    if ids - {e.entity_id for e in analysis.entities}:
        raise ProcessingError('Selection does not belong to this document.')
    selected = [e for e in analysis.entities if e.entity_id in ids]
    # Build from immutable input slices: replacements cannot shift later offsets.
    pieces, cursor = [], 0
    for entity in selected:
        if entity.start < cursor or text[entity.start:entity.end] != entity.text:
            raise ProcessingError('Invalid or overlapping TXT span.')
        pieces.extend([text[cursor:entity.start], f'[{entity.type}]'])
        cursor = entity.end
    pieces.append(text[cursor:])
    output = ''.join(pieces)
    return analysis, output.encode('utf-8')
