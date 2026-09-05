from smart_redactor.schemas import Analysis, Entity, ProcessingError
from smart_redactor.extraction.pdf import extract_pdf, span_boxes
from smart_redactor.detection.ner import NerBackend, detect_all
from smart_redactor.redaction.pdf import redact_pdf


def analyze_pdf(data: bytes, backend: NerBackend | None = None) -> Analysis:
    pages, warnings = extract_pdf(data)
    entities = []
    for page in pages:
        for candidate in detect_all(page.text, backend):
            entities.append(Entity(f'{page.page}:{candidate.start}:{candidate.end}:{candidate.type}',
                                   candidate.type, candidate.text, candidate.start, candidate.end,
                                   page.page, span_boxes(page, candidate.start, candidate.end),
                                   candidate.source, candidate.confidence))
    return Analysis(pages, entities, warnings)


def process_pdf(data: bytes, selected_ids: list[str] | None = None, backend: NerBackend | None = None) -> tuple[Analysis, bytes]:
    # Reanalyze actual input: never trust stale UI boxes from another upload.
    analysis = analyze_pdf(data, backend)
    ids = {e.entity_id for e in analysis.entities} if selected_ids is None else set(selected_ids)
    if ids - {e.entity_id for e in analysis.entities}:
        raise ProcessingError('Selection does not belong to this document.')
    selected = [e for e in analysis.entities if e.entity_id in ids]
    return analysis, redact_pdf(data, selected, analysis.entities)
