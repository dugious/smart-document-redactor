import hashlib
from pathlib import Path
import pandas as pd
import streamlit as st
from smart_redactor.pipeline import analyze_pdf, process_pdf
from smart_redactor.text import analyze_txt, process_txt
from smart_redactor.preview import preview_pdf, highlight_txt
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


st.set_page_config(page_title='Smart Redactor · Document workspace', page_icon='▧', layout='wide')
style = (Path(__file__).resolve().parent / 'assets/styles.css').read_text(encoding='utf-8')
st.html(f'<style>{style}</style>')
st.html('''<div class="hero"><span class="eyebrow">SMART DOCUMENT REDACTOR</span>
<h1>Chia sẻ tài liệu.<br>Giữ lại sự riêng tư.</h1>
<p>Phát hiện thông tin nhạy cảm, duyệt từng kết quả và xuất bản đã xử lý — ngay trên máy của bạn.</p>
<span class="local-pill">Xử lý local · Không gọi API suy luận bên ngoài</span></div>
<div class="workflow"><div class="step"><strong>01</strong> Tải tài liệu</div>
<div class="step"><strong>02</strong> Duyệt kết quả</div><div class="step"><strong>03</strong> Kiểm tra & xuất</div></div>''')

with st.sidebar:
    st.header('Smart Redactor')
    st.caption('DOCUMENT WORKSPACE / LOCAL')
    st.divider()
    st.subheader('Cấu hình phát hiện')
    backend_kind = st.selectbox('NER backend', ['Regex only', 'spaCy', 'Transformers'],
                               help='Regex cho dữ liệu có cấu trúc; spaCy hoặc Transformers bổ sung tên người.')
    model_name = ''
    if backend_kind != 'Regex only':
        model_name = st.text_input('Model đã cài / thư mục model local', value='en_core_web_sm' if backend_kind == 'spaCy' else 'models/bert-base-NER', key=f'model_{backend_kind}')
        st.caption('Model phải có sẵn trên máy. Không tự tải khi xử lý tài liệu.')
    st.divider()
    st.caption('PDF có text · TXT UTF-8\n\nTối đa 10 MiB · PDF tối đa 50 trang')
    with st.expander('Phạm vi & giới hạn', expanded=False):
        st.write('Tiếng Anh là ngôn ngữ chính. PHONE Bắc Mỹ có định dạng; CREDIT_CARD kiểm tra Luhn. ADDRESS kiểu Mỹ ở mức thử nghiệm. OCR chưa hỗ trợ.')
        st.write('Metadata, attachments, annotations và chữ trong ảnh chưa được làm sạch toàn diện. Không có bảo đảm pháp lý hoặc phát hiện hết PII.')

st.warning('Cần người dùng rà soát: công cụ có thể bỏ sót PII và không làm sạch mọi lớp nội dung PDF. Preview hiển thị dữ liệu trên màn hình.')
st.subheader('01 / Tải tài liệu')
file = st.file_uploader('Kéo thả PDF hoặc TXT vào đây', type=['pdf', 'txt'], help='Chỉ dùng file đáng tin cậy. TXT phải dùng UTF-8.')

if file is None:
    reset_document()
    a, b = st.columns(2)
    with a:
        st.html('<div class="empty-card"><h3>Bắt đầu với tài liệu mẫu</h3><p>Chọn <strong>examples/structured-input.txt</strong> để thử email, điện thoại và số thẻ giả.</p><p>Muốn nhận diện tên người? Chọn spaCy hoặc Transformers ở thanh bên.</p></div>')
    with b:
        st.html('<div class="empty-card"><h3>Bạn quyết định điều gì được che</h3><p>Duyệt từng lần xuất hiện, giữ lại nội dung cần thiết và đối chiếu trước / sau khi xuất.</p><p>Không có kết quả phát hiện không đồng nghĩa tài liệu không chứa PII.</p></div>')
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
        
        st.caption(f'{suffix.upper().lstrip(".")} · {len(data) / 1024:.1f} KiB · {len(analysis.pages)} trang/phần văn bản')
        st.subheader('02 / Duyệt kết quả')
        
        available = [kind for kind in TYPES if kind != 'PERSON' or backend is not None]
        with st.sidebar:
            st.subheader('Nhóm dữ liệu')
            enabled = st.multiselect('Nhóm dữ liệu cần che', options=available,
                                     default=[kind for kind in available if kind != 'ADDRESS'], key='doc_types')
        if 'ADDRESS' in enabled:
            st.warning('ADDRESS thử nghiệm: chỉ mẫu số nhà + tên đường + hậu tố kiểu Mỹ; không nhận địa chỉ đầy đủ, thành phố/ZIP hoặc mọi địa danh.')
        
        visible = [e for e in analysis.entities if e.type in enabled]
        if not visible:
            st.info('Không phát hiện entity trong nhóm đã bật; không có nghĩa tài liệu không chứa PII.')
        
        entities = {e.entity_id: e for e in visible}
        group_key = tuple(sorted(enabled))
        
        # Initialize default selection state when file or category filter changes
        if st.session_state.get('doc_group_key') != group_key:
            st.session_state['doc_selected_set'] = set(entities.keys())
            st.session_state['doc_group_key'] = group_key
            st.session_state.pop('doc_output', None)
            st.session_state.pop('doc_df_editor', None)
        
        current_selected_set = st.session_state.get('doc_selected_set', set(entities.keys()))

        st.caption('Bật / tắt checkbox trong bảng bên dưới để chọn cụ thể từng lần xuất hiện cần che.')
        
        # Build interactive DataFrame for data editor
        df_rows = []
        for e in visible:
            df_rows.append({
                'Che': e.entity_id in current_selected_set,
                'Loại': e.type,
                'Nội dung': e.text,
                'Trang': str(e.page) if e.page is not None else 'TXT',
                'Offset': f'[{e.start}:{e.end}]',
                'Nguồn': e.source,
                'Confidence': f'{e.confidence:.2f}' if e.confidence is not None else '-',
                '_id': e.entity_id,
            })
        
        df = pd.DataFrame(df_rows)
        
        btn_col1, btn_col2, _ = st.columns([1.2, 1.2, 6])
        with btn_col1:
            if st.button('Chọn tất cả', width='stretch'):
                st.session_state['doc_selected_set'] = set(entities.keys())
                st.session_state.pop('doc_output', None)
                st.rerun()
        with btn_col2:
            if st.button('Bỏ chọn tất cả', width='stretch'):
                st.session_state['doc_selected_set'] = set()
                st.session_state.pop('doc_output', None)
                st.rerun()

        edited_df = st.data_editor(
            df,
            column_config={
                'Che': st.column_config.CheckboxColumn('Che?', default=True, help='Tick để áp dụng redaction/thay nhãn'),
                'Loại': st.column_config.TextColumn('Loại', disabled=True),
                'Nội dung': st.column_config.TextColumn('Nội dung phát hiện', disabled=True),
                'Trang': st.column_config.TextColumn('Trang', disabled=True, width='small'),
                'Offset': st.column_config.TextColumn('Span', disabled=True, width='small'),
                'Nguồn': st.column_config.TextColumn('Nguồn', disabled=True, width='small'),
                'Confidence': st.column_config.TextColumn('Score', disabled=True, width='small'),
                '_id': None,  # Hide ID column
            },
            disabled=['Loại', 'Nội dung', 'Trang', 'Offset', 'Nguồn', 'Confidence'],
            hide_index=True,
            width='stretch',
            key='doc_df_editor'
        )
        
        # Extract selected IDs from edited DataFrame
        if not edited_df.empty and 'Che' in edited_df.columns:
            selected_ids = list(edited_df[edited_df['Che']]['_id'])
        else:
            selected_ids = []
            
        selected_set = set(selected_ids)
        if selected_set != st.session_state.get('doc_selected_set'):
            st.session_state['doc_selected_set'] = selected_set
            st.session_state.pop('doc_output', None)

        selected = list(selected_set)
        selection_key = tuple(sorted(selected))
        if st.session_state.get('doc_output_selection') != selection_key:
            st.session_state.pop('doc_output', None)
            
        left, right = st.columns(2)
        left.metric('Entity phát hiện trong nhóm đã bật', len(entities))
        right.metric('Entity đã chọn để che', len(selected))
        
        st.dataframe([{'Type': kind, 'Detected': sum(e.type == kind for e in visible),
                       'Selected': sum(entities[i].type == kind for i in selected if i in entities)} for kind in enabled],
                     width='stretch')
        
        if not selected:
            st.info('Không chọn entity nào: xuất bản không thay thế dữ liệu; không phải tài liệu đã được làm sạch.')
        
        acknowledged = st.checkbox('Tôi hiểu giới hạn kiểm tra, bao gồm các cảnh báo phía trên.', key='doc_ack')
        if st.button('Áp dụng các lựa chọn', disabled=not acknowledged, type='primary', width='stretch'):
            st.session_state.pop('doc_output', None)
            with st.spinner('Processing and verifying…'):
                _, output = process(data, selected, backend=backend)
                st.session_state['doc_output'] = output
                st.session_state['doc_output_selection'] = selection_key
        
        output = st.session_state.get('doc_output')
        
        st.subheader('03 / Kiểm tra & xuất')
        st.caption('Đã có bản xử lý — hãy đối chiếu trước khi tải xuống.' if output is not None else 'Chưa có bản xuất cho lựa chọn hiện tại. Xác nhận giới hạn và nhấn Áp dụng ở trên.')
        
        # Entities to highlight in the "Before" preview
        highlight_list = [entities[i] for i in selected if i in entities]

        before, after = st.columns(2)
        before.markdown('#### Bản gốc (có đánh dấu vùng phát hiện)')
        after.markdown('#### Bản đã xử lý')
        
        if is_pdf:
            number = st.number_input('Trang preview', min_value=1, max_value=len(analysis.pages), value=1, step=1, key='doc_page')
            with before:
                st.image(preview_pdf(data, int(number), highlight_entities=highlight_list), caption=f'Trang {number} - Bản gốc có khung màu')
            if output is not None:
                with after:
                    st.image(preview_pdf(output, int(number)), caption=f'Trang {number} - Bản đã redact')
            else:
                with after:
                    st.html('<div class="empty-card"><h3>Chờ áp dụng lựa chọn</h3><p>Preview sau xử lý sẽ xuất hiện tại đây. Đổi lựa chọn sẽ gỡ bản cũ để tránh tải nhầm.</p></div>')
        else:
            with before:
                st.html(highlight_txt(analysis.pages[0].text, highlight_list))
            if output is not None:
                with after:
                    limit = 20_000
                    st.code(output.decode('utf-8')[:limit], language=None)
            else:
                with after:
                    st.html('<div class="empty-card"><h3>Chờ áp dụng lựa chọn</h3><p>Preview sau xử lý sẽ xuất hiện tại đây. Đổi lựa chọn sẽ gỡ bản cũ để tránh tải nhầm.</p></div>')
            st.caption('TXT preview giới hạn 20.000 ký tự; file xuất chứa toàn bộ nội dung.')
            
        if output is not None:
            st.success('Đã xử lý các lựa chọn. PDF đã qua kiểm tra text; đây không phải chứng nhận làm sạch toàn diện.')
            st.download_button('Tải file đã xử lý', output,
                               'redacted.pdf' if is_pdf else 'redacted.txt',
                               'application/pdf' if is_pdf else 'text/plain; charset=utf-8',
                               type='primary', width='stretch')
    except ProcessingError as exc:
        st.session_state.pop('doc_output', None)
        st.error(str(exc))
