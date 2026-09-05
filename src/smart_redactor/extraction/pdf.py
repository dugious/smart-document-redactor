from io import BytesIO
import math
import pdfplumber
import pymupdf
from smart_redactor.schemas import Box, PageText, ProcessingError

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 50
MAX_CHARS = 300_000


def span_boxes(page: PageText, start: int, end: int) -> tuple[Box, ...]:
    if not 0 <= start < end <= len(page.text) or len(page.text) != len(page.char_boxes):
        raise ProcessingError('Invalid entity mapping.')
    groups: list[list[float]] = []
    for char, box in zip(page.text[start:end], page.char_boxes[start:end]):
        if box is None:
            if not char.isspace():
                raise ProcessingError('Entity contains unmapped characters.')
            continue
        x0, y0, x1, y1 = box
        if groups and abs(groups[-1][1] - y0) < 2 and -1 <= x0 - groups[-1][2] <= 5:
            groups[-1][2] = max(groups[-1][2], x1)
            groups[-1][3] = max(groups[-1][3], y1)
        else:
            groups.append([x0, y0, x1, y1])
    if not groups:
        raise ProcessingError('Entity has no mapped region.')
    return tuple(tuple(g) for g in groups)


def extract_pdf(data: bytes) -> tuple[list[PageText], list[str]]:
    if not data or len(data) > MAX_BYTES:
        raise ProcessingError('File is empty or exceeds 10 MiB.')
    if not data.startswith(b'%PDF-'):
        raise ProcessingError('Expected a PDF file.')
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            if doc.needs_pass:
                raise ProcessingError('Encrypted PDF is unsupported.')
            if not 0 < len(doc) <= MAX_PAGES:
                raise ProcessingError('PDF must contain 1–50 pages.')
            for page in doc:
                if any(a.type[0] == pymupdf.PDF_ANNOT_REDACT for a in page.annots() or []):
                    raise ProcessingError('PDF contains existing redaction annotations; unsupported.')
                if page.rotation or page.cropbox != page.mediabox or page.mediabox.x0 or page.mediabox.y0:
                    raise ProcessingError('Rotated/cropped/nonzero-origin PDF is unsupported in M1.')
        pages, warnings = [], []
        count = 0
        with pdfplumber.open(BytesIO(data)) as pdf:
            for number, page in enumerate(pdf.pages, 1):
                chars = page.chars
                count += len(chars)
                if count > MAX_CHARS:
                    raise ProcessingError('PDF exceeds character processing limit.')
                if not chars:
                    if page.images or page.curves or page.lines or page.rects:
                        raise ProcessingError(f'Page {number}: non-text content cannot be inspected; OCR is unsupported.')
                    pages.append(PageText(number, '', []))
                    continue
                if page.images:
                    warnings.append(f'Page {number}: images are not inspected; coverage is partial.')
                if page.curves or page.lines or page.rects:
                    warnings.append(f'Page {number}: vector content is not inspected.')
                # Top-left coordinates match unrotated, uncropped PyMuPDF pages.
                # Geometric row ordering is sufficient for M1 emails, not general reading order.
                rows: list[list[dict]] = []
                for char in sorted(chars, key=lambda c: (c['top'], c['x0'])):
                    box = (char['x0'], char['top'], char['x1'], char['bottom'])
                    if (not char.get('upright', True) or not all(math.isfinite(v) for v in box)
                            or box[0] < 0 or box[1] < 0 or box[2] > page.width or box[3] > page.height
                            or box[2] <= box[0] or box[3] <= box[1]
                            or len(char['text']) != 1 or char['text'] == '\ufffd'):
                        raise ProcessingError(f'Page {number}: unsupported glyph geometry or encoding.')
                    if rows and abs(rows[-1][0]['top'] - char['top']) < 2:
                        rows[-1].append(char)
                    else:
                        rows.append([char])
                text, mapping = [], []
                for row in rows:
                    if text:
                        text.append('\n'); mapping.append(None)
                    previous = None
                    for char in sorted(row, key=lambda c: c['x0']):
                        if previous is not None and char['x0'] < previous['x1'] - 1:
                            raise ProcessingError(f'Page {number}: overlapping glyphs unsupported.')
                        if previous is not None and char['x0'] - previous['x1'] > 2:
                            text.append(' '); mapping.append(None)
                        text.append(char['text'])
                        mapping.append((char['x0'], char['top'], char['x1'], char['bottom']))
                        previous = char
                pages.append(PageText(number, ''.join(text), mapping))
        return pages, warnings
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError('PDF could not be safely extracted.') from None
