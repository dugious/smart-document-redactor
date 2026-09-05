import hashlib
from pathlib import Path
import streamlit as st
from smart_redactor.pipeline import analyze_pdf, process_pdf
from smart_redactor.text import analyze_txt, process_txt
from smart_redactor.preview import preview_pdf
from smart_redactor.detection.structured import TYPES
from smart_redactor.detection.ner import SpacyBackend, TransformersBackend
from smart_redactor.schemas import ProcessingError


def reset_document():
    for key in list(st.session_state):
        if key.startswith('doc_'):
            del st.session_state[key]


@st.cache_resource(show_spinner=False)
def load_backend(kind, model):
    return SpacyBackend(model) if kind == 'spaCy' else TransformersBackend(model)


st.set_page_config(page_title='Smart Document Redactor', layout='wide')
st.title('Smart Document Redactor — M4')
st.caption('Local PDF / UTF-8 TXT → structured PII + optional PERSON NER → review → redaction.')
backend_kind = st.selectbox('NER backend', ['Regex only', 'spaCy', 'Transformers'])
model_name = ''
if backend_kind != 'Regex only':
    model_name = st.text_input('Model đã cài / thư mục model local', value='en_core_web_sm' if backend_kind == 'spaCy' else 'models/bert-base-NER', key=f'model_{backend_kind}')
    st.caption('Không tự tải model khi xử lý. Xem README để cài/tải trước; model có thể bỏ sót hoặc nhận sai tên người.')
st.warning('Chỉ kiểm tra EMAIL, PHONE Bắc Mỹ có định dạng, CREDIT_CARD qua Luhn và ADDRESS đường phố Mỹ thử nghiệm. Metadata, annotations, attachments và chữ trong ảnh chưa được kiểm tra toàn diện. Không bảo đảm phát hiện hết PII. Preview hiển thị nội dung nhạy cảm trên màn hình.')
file = st.file_uploader('PDF hoặc TXT — tối đa 10 MiB', type=['pdf', 'txt'])
if file is None:
    reset_document()
else:
    data = file.getvalue()
    suffix = Path(getattr(file, 'name', 'document.pdf')).suffix.lower()
    key = hashlib.sha256((suffix + backend_kind + model_name).encode() + data).hexdigest()
    if st.session_state.get('doc_key') != key:
        reset_document()
        st.session_state['doc_key'] = key
    try:
        if suffix not in {'.pdf', '.txt'}:
            raise ProcessingError('Only PDF and TXT are supported.')
        is_pdf = suffix == '.pdf'
        analyze, process = (analyze_pdf, process_pdf) if is_pdf else (analyze_txt, process_txt)
        backend = None if backend_kind == 'Regex only' else load_backend(backend_kind, model_name)
        if backend is None:
            st.info('Regex only: PERSON chưa được kiểm tra.')
        if 'doc_analysis' not in st.session_state:
            st.session_state['doc_analysis'] = analyze(data, backend=backend)
        analysis = st.session_state['doc_analysis']
        for warning in analysis.warnings:
            st.warning(warning)
        available = [kind for kind in TYPES if kind != 'PERSON' or backend is not None]
        enabled = st.multiselect('Nhóm dữ liệu cần che', options=available,
                                 default=[kind for kind in available if kind != 'ADDRESS'], key='doc_types')
        if 'ADDRESS' in enabled:
            st.warning('ADDRESS thử nghiệm: chỉ mẫu số nhà + tên đường + hậu tố kiểu Mỹ; không nhận địa chỉ đầy đủ, thành phố/ZIP hoặc mọi địa danh.')
        visible = [e for e in analysis.entities if e.type in enabled]
        if not visible:
            st.info('Không phát hiện entity trong nhóm đã bật; không có nghĩa tài liệu không chứa PII.')
        st.subheader('Duyệt kết quả')
        st.caption('Chọn ID của từng lần xuất hiện. Cùng nội dung nhưng khác vị trí có ID riêng.')
        st.dataframe([{'ID': e.entity_id, 'Type': e.type, 'Content': e.text, 'Page': e.page,
                       'Start': e.start, 'End': e.end, 'Source': e.source,
                       'Confidence': e.confidence} for e in visible])
        entities = {e.entity_id: e for e in visible}
        group_key = tuple(sorted(enabled))
        if st.session_state.get('doc_group_key') != group_key:
            st.session_state['doc_selected'] = list(entities)
            st.session_state['doc_group_key'] = group_key
            st.session_state.pop('doc_output', None)
        selected = st.multiselect('Các kết quả cần che', options=list(entities), key='doc_selected',
                                  format_func=lambda i: f'{entities[i].text} — trang {entities[i].page or "TXT"} — offset {entities[i].start}')
        selection_key = tuple(sorted(selected))
        if st.session_state.get('doc_output_selection') != selection_key:
            st.session_state.pop('doc_output', None)
        left, right = st.columns(2)
        left.metric('Entity phát hiện trong nhóm đã bật', len(entities))
        right.metric('Entity đã chọn', len(selected))
        st.dataframe([{'Type': kind, 'Detected': sum(e.type == kind for e in visible),
                       'Selected': sum(entities[i].type == kind for i in selected)} for kind in enabled])
        if not selected:
            st.info('Không chọn entity nào: xuất bản không thay thế dữ liệu; không phải tài liệu đã được làm sạch.')
        acknowledged = st.checkbox('Tôi hiểu giới hạn kiểm tra, bao gồm các cảnh báo phía trên.', key='doc_ack')
        if st.button('Áp dụng các lựa chọn', disabled=not acknowledged):
            st.session_state.pop('doc_output', None)
            with st.spinner('Processing and verifying…'):
                _, output = process(data, selected, backend=backend)
                st.session_state['doc_output'] = output
                st.session_state['doc_output_selection'] = selection_key
        output = st.session_state.get('doc_output')
        st.subheader('Preview trước / sau')
        st.caption('Bản sau chỉ xuất hiện sau khi áp dụng; thay lựa chọn sẽ xóa kết quả cũ.')
        before, after = st.columns(2)
        if is_pdf:
            number = st.number_input('Trang preview', min_value=1, max_value=len(analysis.pages), value=1, step=1, key='doc_page')
            with before:
                st.image(preview_pdf(data, int(number)), caption='Trước')
            if output is not None:
                with after:
                    st.image(preview_pdf(output, int(number)), caption='Sau')
        else:
            limit = 20_000
            before.code(analysis.pages[0].text[:limit], language=None)
            if output is not None:
                after.code(output.decode('utf-8')[:limit], language=None)
            st.caption('TXT preview giới hạn 20.000 ký tự; file xuất chứa toàn bộ nội dung.')
        if output is not None:
            st.success('Đã xử lý các lựa chọn. PDF đã qua kiểm tra text; đây không phải chứng nhận làm sạch toàn diện.')
            st.download_button('Tải file đã xử lý', output,
                               'redacted.pdf' if is_pdf else 'redacted.txt',
                               'application/pdf' if is_pdf else 'text/plain; charset=utf-8')
    except ProcessingError as exc:
        st.session_state.pop('doc_output', None)
        st.error(str(exc))
