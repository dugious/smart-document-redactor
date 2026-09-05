import pymupdf
import pytest
from smart_redactor.pipeline import analyze_pdf, process_pdf
from smart_redactor.schemas import PageText, ProcessingError
from smart_redactor.extraction.pdf import span_boxes, MAX_BYTES
from smart_redactor.detection.email import detect_email
from smart_redactor.redaction.verification import verify_output


def pdf(lines):
    with pymupdf.open() as doc:
        page = doc.new_page()
        for x, y, value in lines:
            page.insert_text((x, y), value)
        return doc.tobytes()


def text(data):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        return ''.join(p.get_text() for p in doc)


@pytest.mark.parametrize('value', ['demo@example.com', 'first.last+tag@example.org'])
def test_email(value):
    assert list(detect_email(f'Contact ({value}).')) == [(9, 9 + len(value), value)]


@pytest.mark.parametrize('value', ['a..b@example.com', '.a@example.com', 'a@-example.com', 'a@example.c', '12.34', 'a@localhost'])
def test_invalid(value):
    assert not list(detect_email(value))


def test_end_to_end():
    source = pdf([(40, 60, 'Contact: demo@example.com'), (40, 100, 'Keep this public sentence.')])
    analysis, result = process_pdf(source)
    assert len(analysis.entities) == 1
    assert analysis.entities[0].confidence is None
    assert 'demo@example.com' not in text(result)
    assert 'Keep this public sentence.' in text(result)


@pytest.mark.parametrize('second', [(40, 100), (320, 60)])
def test_duplicate_selective_and_columns(second):
    source = pdf([(40, 60, 'demo@example.com'), (*second, 'demo@example.com')])
    analysis = analyze_pdf(source)
    assert len(analysis.entities) == 2
    _, result = process_pdf(source, [analysis.entities[0].entity_id])
    assert text(result).count('demo@example.com') == 1
    _, result = process_pdf(source)
    assert 'demo@example.com' not in text(result)


def test_multiline_mapping():
    analysis = analyze_pdf(pdf([(40, 60, 'First'), (40, 100, 'Last')]))
    page = analysis.pages[0]
    boxes = span_boxes(page, 0, len(page.text))
    assert len(boxes) == 2
    assert boxes[0][3] < boxes[1][1]


def test_mapping_missing():
    with pytest.raises(ProcessingError):
        span_boxes(PageText(1, 'x', [None]), 0, 1)


def test_no_pii():
    source = pdf([(40, 60, 'Public report: London, amount 123.45')])
    analysis, result = process_pdf(source)
    assert not analysis.entities
    assert text(source) == text(result)


def test_scan_and_mixed_scan():
    with pymupdf.open() as doc:
        p = doc.new_page()
        p.insert_text((40, 60), 'Public text')
        p = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
        pix.clear_with(255)
        p.insert_image(pymupdf.Rect(0, 0, 100, 100), pixmap=pix)
        with pytest.raises(ProcessingError, match='OCR'):
            analyze_pdf(doc.tobytes())


def test_blank_page():
    assert analyze_pdf(pdf([])).pages[0].text == ''


@pytest.mark.parametrize('data', [b'', b'hello', b'%PDF-broken', b'%PDF-' + b'x' * MAX_BYTES], ids=['empty', 'not-pdf', 'broken', 'oversized'])
def test_invalid_pdf(data):
    with pytest.raises(ProcessingError):
        analyze_pdf(data)


def test_verification_failure():
    source = pdf([(40, 60, 'demo@example.com')])
    entities = analyze_pdf(source).entities
    with pytest.raises(ProcessingError, match='verification failed'):
        verify_output(source, entities, entities)


def test_bad_selection():
    with pytest.raises(ProcessingError):
        process_pdf(pdf([]), ['stale-id'])


@pytest.mark.parametrize('kind', ['rotation', 'crop', 'encryption', 'annotation'])
def test_unsupported(kind):
    with pymupdf.open(stream=pdf([(40, 60, 'demo@example.com')]), filetype='pdf') as doc:
        if kind == 'rotation':
            doc[0].set_rotation(90)
        elif kind == 'crop':
            doc[0].set_cropbox(pymupdf.Rect(10, 10, 500, 700))
        elif kind == 'annotation':
            doc[0].add_redact_annot(pymupdf.Rect(40, 40, 60, 60))
        data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='fake-owner', user_pw='fake-user') if kind == 'encryption' else doc.tobytes()
        with pytest.raises(ProcessingError):
            analyze_pdf(data)


def test_page_limit():
    with pymupdf.open() as doc:
        for _ in range(51):
            doc.new_page()
        with pytest.raises(ProcessingError):
            analyze_pdf(doc.tobytes())
