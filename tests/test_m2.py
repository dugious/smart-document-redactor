from io import BytesIO
from unittest.mock import patch
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest
from smart_redactor.text import analyze_txt, process_txt
from smart_redactor.preview import preview_pdf
from smart_redactor.schemas import ProcessingError
from test_m1 import pdf


def test_txt_selective_unicode_crlf():
    source = 'Xin chào\r\ndemo@example.com\r\ndemo@example.com'.encode('utf-8')
    analysis = analyze_txt(source)
    assert all(e.page is None and not e.boxes and e.confidence is None for e in analysis.entities)
    _, result = process_txt(source, [analysis.entities[1].entity_id])
    assert result.decode() == 'Xin chào\r\ndemo@example.com\r\n[EMAIL]'
    _, result = process_txt(source)
    assert result.decode() == 'Xin chào\r\n[EMAIL]\r\n[EMAIL]'
    assert process_txt(source, [])[1] == source


def test_txt_no_pii_and_bom():
    assert process_txt(b'Public 123.45')[1] == b'Public 123.45'
    assert process_txt(b'\xef\xbb\xbfdemo@example.com')[1] == b'[EMAIL]'


@pytest.mark.parametrize('data', [b'', b'\xff', b'hello\x00world', b'\xef\xbb\xbf'])
def test_invalid_txt(data):
    with pytest.raises(ProcessingError):
        analyze_txt(data)


def test_txt_stale_selection():
    with pytest.raises(ProcessingError):
        process_txt(b'demo@example.com', ['bad'])


def test_preview_bounded_and_after():
    data = preview_pdf(pdf([(40, 60, 'demo@example.com')]), 1, max_side=500)
    pix = pymupdf.Pixmap(data)
    assert data.startswith(b'\x89PNG')
    assert max(pix.width, pix.height) <= 501
    with pytest.raises(ProcessingError):
        preview_pdf(pdf([]), 2)


def test_ui_selection_invalidates_and_txt_preview():
    source = BytesIO(b'demo@example.com demo@example.com')
    source.name = 'synthetic.txt'
    with patch('streamlit.file_uploader', return_value=source):
        app = AppTest.from_file('../app.py', default_timeout=30).run()
        assert not app.exception
        first = app.multiselect[1].value[0]
        app.multiselect[1].set_value([first]).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        assert not app.exception
        assert app.session_state['doc_output'] == b'[EMAIL] demo@example.com'
        assert len(app.code) == 2
        app.multiselect[1].set_value([]).run()
        assert not app.get('download_button')
        assert len(app.code) == 1
        app.button[0].click().run()
        assert app.session_state['doc_output'] == source.getvalue()
    replacement = BytesIO(b'public only')
    replacement.name = 'second.txt'
    with patch('streamlit.file_uploader', return_value=replacement):
        app.run()
        assert not app.exception
        assert not app.get('download_button')
        assert not app.checkbox[0].value
        assert not app.multiselect[1].value
