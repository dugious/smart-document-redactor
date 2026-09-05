from io import BytesIO
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from smart_redactor.detection.structured import Candidate, detect_structured, luhn, resolve_overlaps
from smart_redactor.pipeline import process_pdf
from smart_redactor.text import process_txt
from test_m1 import pdf, text


@pytest.mark.parametrize('value', ['4111111111111111', '4111 1111 1111 1111', '5555-5555-5555-4444', '378282246310005'])
def test_luhn_valid(value):
    assert luhn(value)


@pytest.mark.parametrize('value', ['4111111111111112', '0000000000000000', '1234', '４１１１１１１１１１１１１１１１', '4111x111111111111', '411111111111111111111'])
def test_luhn_invalid(value):
    assert not luhn(value)


@pytest.mark.parametrize('value', ['+1 202-555-0100', '(202) 555-0100', '202.555.0100 ext. 12', '202-555-0100'])
def test_phone(value):
    assert [(c.type, c.text) for c in detect_structured(value)] == [('PHONE', value)]


@pytest.mark.parametrize('value', ['2025550100', '123-456-7890', 'London', 'Amount 123.45', '2026-09-05', 'ID 1234567890123456789012345', '4111111111111112'])
def test_not_pii(value):
    assert not detect_structured(value)


def test_address_experimental():
    result = detect_structured('Visit 123 Example Street, Apt 4. London is public.')
    assert [(c.type, c.text) for c in result] == [('ADDRESS', '123 Example Street, Apt 4')]


def test_overlap_priority_dedup_adjacency():
    email = Candidate('EMAIL', 0, 10, 'fake-email')
    phone = Candidate('PHONE', 2, 8, 'fake')
    card = Candidate('CREDIT_CARD', 10, 26, 'fake-card')
    assert resolve_overlaps([phone, email, email, card]) == [email, card]
    longer = Candidate('ADDRESS', 0, 20, 'longer')
    shorter = Candidate('ADDRESS', 0, 10, 'shorter')
    assert resolve_overlaps([shorter, longer]) == [longer]


def test_all_types_pdf_txt():
    values = ['demo@example.com', '+1 202-555-0100', '4111 1111 1111 1111', '123 Example Street']
    source = pdf([(40, 60 + n*40, v) for n, v in enumerate(values)] + [(40, 240, 'Public 123.45 London')])
    analysis, output = process_pdf(source)
    assert {e.type for e in analysis.entities} == {'EMAIL', 'PHONE', 'CREDIT_CARD', 'ADDRESS'}
    assert all(v not in text(output) for v in values)
    assert 'Public 123.45 London' in text(output)
    _, output = process_txt('\n'.join(values).encode())
    assert output == b'[EMAIL]\n[PHONE]\n[CREDIT_CARD]\n[ADDRESS]'


def test_ui_type_filter():
    source = BytesIO(b'202-555-0100\ndemo@example.com\n123 Example Street')
    source.name = 'fake.txt'
    with patch('streamlit.file_uploader', return_value=source):
        app = AppTest.from_file('../app.py', default_timeout=30).run()
        # Change type filter in sidebar
        app.multiselect(key='doc_types').set_value(['PHONE']).run()
        assert len(app.session_state['doc_selected_set']) == 1
        app.checkbox[0].check().run()
        apply_btn = [b for b in app.button if 'Áp dụng' in b.label][0]
        apply_btn.click().run()
        assert not app.exception
        assert app.session_state['doc_output'] == b'[PHONE]\ndemo@example.com\n123 Example Street'
        
        # Switch to ADDRESS
        app.multiselect(key='doc_types').set_value(['ADDRESS']).run()
        assert not app.get('download_button')
        assert len(app.session_state['doc_selected_set']) == 1
        assert any('ADDRESS' in warning.value for warning in app.warning)
