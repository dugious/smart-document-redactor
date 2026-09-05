from io import BytesIO
from unittest.mock import patch
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest
from smart_redactor.pipeline import analyze_pdf, process_pdf
from smart_redactor.schemas import ProcessingError
from test_m1 import pdf


def test_ui_initial_render():
    app = AppTest.from_file('../app.py').run()
    assert not app.exception
    assert not app.get('download_button')


def test_ui_upload_redact_download():
    source = BytesIO(pdf([(40, 60, 'demo@example.com')]))
    with patch('streamlit.file_uploader', return_value=source):
        app = AppTest.from_file('../app.py', default_timeout=30).run()
        assert not app.exception
        apply_btn = [b for b in app.button if 'Áp dụng' in b.label][0]
        assert apply_btn.disabled
        app.checkbox[0].check().run()
        apply_btn = [b for b in app.button if 'Áp dụng' in b.label][0]
        apply_btn.click().run()
        assert not app.exception
        assert app.get('download_button')
        assert app.session_state['doc_output'].startswith(b'%PDF-')
    with patch('streamlit.file_uploader', return_value=BytesIO(b'bad file')):
        app.run()
        assert app.error
        assert not app.get('download_button')


def test_verification_failure_blocks_pipeline():
    with patch('smart_redactor.redaction.pdf.verify_output', side_effect=ProcessingError('Verification failed')):
        with pytest.raises(ProcessingError):
            process_pdf(pdf([(40, 60, 'demo@example.com')]))


def test_image_with_text_warns():
    with pymupdf.open(stream=pdf([(40, 60, 'demo@example.com')]), filetype='pdf') as doc:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
        pix.clear_with(255)
        doc[0].insert_image(pymupdf.Rect(40, 100, 100, 160), pixmap=pix)
        assert any('partial' in w for w in analyze_pdf(doc.tobytes()).warnings)
