import pymupdf
from smart_redactor.schemas import Entity, ProcessingError


def verify_output(output: bytes, selected: list[Entity], all_entities: list[Entity]) -> None:
    try:
        with pymupdf.open(stream=output, filetype='pdf') as doc:
            text = '\n'.join(page.get_text() for page in doc)
            selected_ids = {e.entity_id for e in selected}
            for entity in all_entities:
                if entity.entity_id not in selected_ids:
                    remaining = ''.join(doc[entity.page - 1].get_textbox(pymupdf.Rect(box)) for box in entity.boxes)
                    if entity.text not in remaining:
                        raise ProcessingError('Output verification failed: unselected entity changed.')
            for entity in selected:
                # Global absence is valid only if every occurrence of this value was selected.
                unselected = any(e.text == entity.text and e.entity_id not in selected_ids for e in all_entities)
                if not unselected and entity.text in text:
                    raise ProcessingError('Output verification failed: selected content remains.')
                page = doc[entity.page - 1]
                for box in entity.boxes:
                    if page.get_textbox(pymupdf.Rect(box)).strip():
                        raise ProcessingError('Output verification failed: target region is not empty.')
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError('Output could not be verified.') from None
