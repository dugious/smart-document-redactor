import pymupdf
from smart_redactor.schemas import ProcessingError


def preview_pdf(data: bytes, page_number: int, max_side: int = 1100) -> bytes:
    """Render only one page, bounded to avoid full-document image allocation."""
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            if not 1 <= page_number <= len(doc) or not 100 <= max_side <= 1600:
                raise ProcessingError('Invalid preview request.')
            page = doc[page_number - 1]
            largest = max(page.rect.width, page.rect.height)
            if largest <= 0:
                raise ProcessingError('Invalid page dimensions.')
            scale = min(1.5, max_side / largest)
            return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError('Preview could not be rendered.') from None
