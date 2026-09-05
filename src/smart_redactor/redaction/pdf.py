import pymupdf
from smart_redactor.schemas import Entity, ProcessingError
from smart_redactor.redaction.verification import verify_output


def redact_pdf(data: bytes, selected: list[Entity], all_entities: list[Entity]) -> bytes:
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            for entity in selected:
                if entity not in all_entities or not entity.boxes or entity.page is None:
                    raise ProcessingError('Invalid redaction selection or missing mapping.')
                for box in entity.boxes:
                    doc[entity.page - 1].add_redact_annot(pymupdf.Rect(box), fill=(0, 0, 0))
            for page in doc:
                # Remove text and overlapping image pixels; vector artwork left unchanged.
                page.apply_redactions(images=2, graphics=0, text=0)
            output = doc.tobytes(garbage=4, deflate=True)
        verify_output(output, selected, all_entities)
        return output
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError('PDF redaction failed.') from None
