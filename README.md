# Smart Document Redactor

## M4 — PERSON NER (đã triển khai)

UI chọn Regex only (mặc định), spaCy hoặc Transformers; chỉ chạy một backend NER. PERSON bật mặc định khi chọn NER. Đổi backend/model reset analysis, lựa chọn và output. Structured regex giữ nguyên ở cả hai backend. NER không chuyển LOC thành ADDRESS.

Máy hiện tại đã cài và chạy model thật trên Python 3.13.14: spaCy 3.8.16 + en_core_web_sm 3.8.0; Transformers 4.57.6 + torch 2.14.0 CPU + dslim/bert-base-NER local. Dependencies NLP tùy chọn:

```powershell
uv pip install -e ".[dev,ner]"
uv pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
.\.venv\Scripts\python.exe scripts/download_transformers.py
.\.venv\Scripts\python.exe scripts/smoke_ner.py
```

Hai lệnh tải model cần mạng và không nhận tài liệu người dùng. App chỉ load spaCy đã cài và Transformers từ thư mục local `models/bert-base-NER`, `local_files_only=True`, `trust_remote_code=False`, safetensors. Không tải model ngầm hoặc fallback sang regex rồi giả vờ đã kiểm tra PERSON. Model thiếu/lỗi chặn luồng với thông báo rõ. Cache resource chỉ giữ model; tài liệu ở session memory riêng. Không chia sẻ ứng dụng localhost cho nhiều người dùng; concurrency nhiều phiên chưa kiểm thử.

`requirements-ner-lock.txt` là snapshot môi trường NLP Windows; `requirements-lock.txt` vẫn là snapshot core không NER. Không commit thư mục models. Download script đã pin commit `d1a3e8f13f8c3566299d95fcfc9a8d2382a9affc`; report M5 chứa hashes file model thực tế.

spaCy chunk 8000 ký tự, overlap 400; Transformers cửa sổ tối đa 1600 ký tự rồi thu nhỏ theo số token thật và context limit, overlap tối đa 200. Không silently truncate input quá context. Offset được cộng lại theo trang; dedupe/overlap ưu tiên structured trước PERSON và longest-span. **Overlap không bảo đảm tên vượt ranh giới chunk được nhận đầy đủ**; có thể thiếu ngữ cảnh hoặc dự đoán mảnh tên. spaCy confidence null; Transformers dùng score của aggregated entity, không phải probability đã calibration.

Xác minh M4: **72 pytest tests passed**, dependency check/compileall passed. Test adapter chunks/offsets dùng model giả lập; **đã chạy thêm hai model thật qua TXT và PDF** bằng `scripts/smoke_ner.py`, kiểm tra tên mục tiêu bị loại và địa danh không bị xóa. Smoke này không phải precision/recall benchmark hoặc browser E2E. Transformers báo pooler weights không dùng khi load token classifier; inference và redaction smoke vẫn pass.

Pipeline NER nằm tại `src/smart_redactor/detection/ner.py`, tests `tests/test_m4.py`. Kết quả M5 đã chạy thật: xem phần đánh giá và `evaluation/README.md`.


Công cụ local giúp rà soát tài liệu trước khi chia sẻ. **M3 phát hiện EMAIL, PHONE Bắc Mỹ, CREDIT_CARD qua Luhn và ADDRESS thử nghiệm trong PDF/TXT UTF-8**. Không phải hệ thống kiểm tra tất cả PII hay chứng nhận bảo mật/GDPR.

## M3 — structured PII

- Bộ chọn nhóm mặc định bật EMAIL, PHONE, CREDIT_CARD; ADDRESS phải bật chủ động. Bảng thống kê theo loại và lựa chọn từng occurrence. Thay nhóm reset danh sách occurrence về tất cả kết quả thuộc nhóm mới và hủy output cũ.
- PHONE: chỉ NANP/Bắc Mỹ có dấu phân cách, area/exchange bắt đầu 2–9, có thể có mã +1 và extension. Không nhận số trần 10 chữ số hoặc mọi số quốc tế. Đây là kiểm tra cấu trúc, không xác minh số có thật/được cấp phát.
- CREDIT_CARD: 13–19 chữ số ASCII, có thể cách bởi space/hyphen, kiểm tra checksum Luhn và loại chuỗi một chữ số lặp. Luhn không xác minh issuer hoặc tài khoản; ID không phải thẻ vẫn có thể vượt qua checksum. Chuỗi sai checksum có thể vẫn nhạy cảm nhưng không được phát hiện.
- ADDRESS (thử nghiệm): số nhà + 1–4 từ tên đường viết hoa đầu từ + hậu tố Street/St/Road/Rd/Avenue/Ave/Lane/Ln/Drive/Dr/Boulevard/Blvd/Court/Ct, tùy chọn Apt/Suite/Unit. Không nhận đầy đủ city/state/ZIP, PO box, địa chỉ quốc tế hoặc địa chỉ lowercase; có false positives. Địa danh đơn lẻ không tự động là PII.
- Overlap xử lý trước bộ lọc nhóm: CREDIT_CARD > EMAIL > PHONE > ADDRESS; cùng ưu tiên chọn span dài hơn, rồi start sớm hơn và tie-break cố định. Trùng span bị loại; span kề nhau được giữ. Không gộp vùng. Bỏ một nhóm không diễn giải lại span bị nhóm đó lấn át thành loại khác.
- Tất cả detector structured dùng `source=regex`, confidence null. Chưa có NER. Giới hạn PHONE/ADDRESS nhằm giữ phạm vi vừa sức, không phải hỗ trợ tiếng Anh toàn cầu.
- Logic: `src/smart_redactor/detection/structured.py`; tests bổ sung `tests/test_m3.py`. Không thêm dependencies.

Kết quả kiểm tra sau M3: **65 tests passed** trên Python 3.13.14 / Windows. Đã test integration cả bốn loại qua PDF redaction và TXT labels, Luhn hợp lệ/sai, số tiền/ngày/địa danh không bị coi là PII, overlap và bộ lọc nhóm UI. Chưa chạy browser E2E thủ công hoặc benchmark trên tập gán nhãn.

## M2 — duyệt và preview

- Upload PDF hoặc TXT; bảng hiển thị entity ID, nội dung, trang, offset, nguồn và confidence null.
- Chọn từng occurrence qua multiselect; các nhóm EMAIL, PHONE, CREDIT_CARD mặc định bật, ADDRESS tùy chọn ở M3.
- Thống kê số phát hiện và đã chọn theo từng nhóm. Chọn rỗng xuất bản không thay thế dữ liệu, có cảnh báo rõ.
- Nút **Áp dụng các lựa chọn** tạo output. Đổi lựa chọn lập tức gỡ output/download cũ; đổi file reset lựa chọn và xác nhận giới hạn.
- PDF preview render một trang trước/sau bằng PNG, kích thước giới hạn; không gửi PDF lên viewer ngoài. Preview này không phải chứng minh sanitization.
- TXT preview trước/sau giới hạn 20.000 ký tự; download vẫn đủ nội dung. UTF-8/UTF-8 BOM được chấp nhận, output UTF-8 không BOM; giữ Unicode và CRLF trong nội dung. Giới hạn 300.000 ký tự và 10 MiB; encoding khác hoặc control characters không hỗ trợ bị từ chối.
- TXT thay span đã chọn bằng `[EMAIL]` từ các lát cắt input không đổi, không global replace. Không dùng kiểm tra absence toàn cục cho TXT vì occurrence không chọn phải được giữ.
- Phân tích được giữ riêng trong Streamlit session memory, không dùng shared cache. Preview chứa PII, cần chú ý người nhìn màn hình.
- `src/smart_redactor/text.py`: decode/detection/replacement TXT. `preview.py`: renderer PNG một trang. `tests/test_m2.py`: TXT Unicode/CRLF/BOM, duplicate selection, encoding lỗi, bounded preview, UI invalidation và thay file.

Kết quả kiểm tra sau M2: **40 tests passed** trên Python 3.13.14 / Windows. Đây là functional tests, không phải precision/recall benchmark; chưa kiểm thử browser upload/download thủ công.

## Chạy nhanh (Windows PowerShell)

Đã kiểm tra trên Windows, Python **3.13.14**. Chọn bản mới đang có trên máy thay Python 3.11 theo yêu cầu; chưa kiểm tra Python 3.14 hoặc khả năng tương thích NER ở milestone sau.

```powershell
cd C:\Users\DELL\smart-document-redactor
uv venv --python 3.13
uv pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe examples/generate_samples.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Không có uv: dùng Python 3.13 tạo `python -m venv .venv`, sau đó `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`. Dependency trực tiếp được pin trong pyproject; requirements-lock.txt là snapshot dependency đầy đủ trên Windows, không phải lock đa nền tảng có hash.

Mở http://127.0.0.1:8501, upload `examples/synthetic-input.pdf`, xem danh sách, chọn các occurrences cần che, xác nhận giới hạn, chọn **Áp dụng các lựa chọn**, xem preview rồi tải output. Server chỉ bind localhost; telemetry Streamlit tắt trong `.streamlit/config.toml`. Chạy từ root project để nạp cấu hình.

M1 không tải model. Cài thư viện cần mạng; xử lý không gọi API bên ngoài. Không cache tài liệu toàn cục, không chủ động ghi upload hoặc nội dung PII vào log. Bytes được giữ trong session memory; không có cam kết xóa an toàn RAM/swap/browser cache. Chỉ script examples chủ động ghi tài liệu giả ra đĩa.

## Pipeline

```text
Upload PDF bytes
  → limits / encrypted / geometry / scan checks
  → pdfplumber chars → page text + per-character boxes
  → regex email + conservative syntax validation
  → exact span → per-line boxes
  → PyMuPDF redaction annotations → apply_redactions
  → new PDF bytes (garbage=4, deflate=True, non-incremental)
  → reopen / text extraction / region verification
  → download
```

Giao diện nằm ở `app.py`; logic độc lập trong `src/smart_redactor/`. Không database, authentication hay service backend riêng.

## Quyết định kỹ thuật

- Offset `[start,end)` theo từng trang; page bắt đầu từ 1. Entity có `entity_id, type, text, start, end, page, boxes, source, confidence`.
- Text và bảng tọa độ sinh cùng nhau từ pdfplumber chars. Ký tự phân cách tổng hợp có box null. Không tìm chuỗi toàn cục để che mọi lần xuất hiện.
- Entity ID dựa vào trang và offset, chỉ có nghĩa trong tài liệu đó. Pipeline phân tích lại bytes trước khi xuất để không tin boxes cũ từ UI.
- Mapper gom ký tự gần nhau trên cùng dòng; nhiều dòng có nhiều rectangle. Không dùng rectangle lớn bao trùm cả vùng giữa các dòng.
- M3 xử lý overlap theo thứ tự ưu tiên công bố ở trên; có unit test cho trùng lặp, chồng lấn và adjacency.
- Confidence regex là null. Không có confidence được bịa cho NER chưa triển khai.
- Redaction loại text thật bằng `apply_redactions`, không chỉ phủ màu. Pixel ảnh chồng vùng được xử lý theo chế độ PyMuPDF images=2; vector artwork không xóa.
- Kiểm tra lại: khi mọi occurrence của một giá trị được chọn, kiểm tra giá trị không còn trong text toàn tài liệu; luôn kiểm tra vùng mục tiêu rỗng. Entity không chọn phải còn ở vùng của nó. API và UI M2 hỗ trợ lựa chọn occurrence riêng.
- File lỗi/mapping lỗi/verification lỗi: dừng, không trả PDF thành công. PDF có annotation redaction tồn tại sẵn bị từ chối để không áp dụng nhầm vùng người dùng chưa chọn.

## Ví dụ giả

Input chứa `demo@example.com` hai lần và `Public amount: 123.45 - keep this text`. Output mẫu loại bỏ hai email, giữ câu công khai. Mở hai PDF trong `examples/` để đối chiếu. Ảnh/GIF thao tác UI chưa ghi; không dùng ảnh giả làm bằng chứng đã demo.

## Test

`tests/test_m1.py`: email và dấu câu, cú pháp sai, redaction end-to-end, hai occurrence cùng chuỗi (khác dòng/hai cột), che một occurrence, nhiều dòng mapping, missing mapping, no PII, scan/mixed scan, blank, dung lượng, số trang, encrypted, rotated/cropped, annotation có sẵn và verification failure.

`tests/test_app.py`: initial render, mocked upload → xác nhận → xử lý → download control, thay file lỗi không giữ output cũ, verification fail đóng luồng, cảnh báo ảnh kèm text. Đây là Streamlit AppTest với uploader mock, **không thay thế browser E2E cho thao tác upload/download thật**.

Fixture chỉ dùng dữ liệu tổng hợp. Test multiline kiểm tra mapper, không tuyên bố detector tự nối email bị ngắt dòng.

## Giới hạn quan trọng

- 10 MiB, 50 trang, 300.000 glyph. Giới hạn glyph được kiểm tra sau khi parser đọc trang: không phải sandbox chống PDF độc hại hoặc decompression bomb. Chỉ demo file đáng tin cậy.
- Từ chối PDF mã hóa, rotation/crop/nonzero origin, glyph quay/chồng lấn/encoding không hỗ trợ. Thiết kế bảo thủ có thể từ chối cả tài liệu hợp lệ.
- Trang không có text nhưng có ảnh/vector bị từ chối vì không kiểm tra được; trang trắng được chấp nhận. Trang có text kèm ảnh/vector cảnh báo coverage không đầy đủ. Heuristic này không phải detector scan toàn diện.
- Reading order dựa hàng hình học: chưa giải quyết layout nhiều cột tổng quát. Test hai cột chỉ chứng minh mapping hai email đơn giản. Font phức tạp, ligature, kerning, text ẩn, nội dung ngoài cấu trúc parser hiểu có thể thiếu hoặc gây từ chối.
- Regex email ASCII bảo thủ; không RFC-complete, không DNS; không email quốc tế hoặc tự nối email xuống dòng. **False negative vẫn có thể xảy ra.** PERSON được hỗ trợ ở M4 khi bật NER; PHONE/CARD/ADDRESS có các giới hạn riêng ở phần đầu README.
- Trích xuất lại text là kiểm tra giới hạn, không chứng minh PDF đã được sanitize toàn diện. Metadata, annotations, attachments, form fields, ảnh và các content layer khác **chưa được làm sạch đầy đủ**; có thể chứa PII. Garbage collection không thay thế sanitization.
- Redaction theo vùng có thể ảnh hưởng ký tự/nội dung chồng nhau. Output cần được người dùng xem lại; không cam kết bảo toàn layout hoàn hảo.
- PyMuPDF có điều khoản AGPL/commercial: kiểm tra license hiện hành trước khi phân phối hoặc dùng thương mại. Project chưa đặt license riêng.

## Đánh giá và roadmap

| Backend | Dataset | Precision / Recall / F1 | Runtime |
|---|---|---|---|
| spaCy + regex | 24 synthetic test docs, 35 entities | micro 92.86% / 74.29% / 82.54% | median 0.150s / dataset |
| Transformers + regex | cùng tập test | micro 96.77% / 85.71% / 90.91% | median 2.405s / dataset |

**Đã đo, không phải số mục tiêu.** PERSON F1: spaCy 78.26%, Transformers 100% nhưng chỉ có 13 PERSON gold — không suy rộng sang tài liệu thực tế. 6 dev / 24 test, 1.440 ký tự test; không fine-tune, không tune sau xem test. PHONE và ADDRESS có false negatives được giữ nguyên trong đánh giá.

Chi tiết precision/recall/F1 từng loại, counts, model revision, machine và giới hạn: [evaluation/README.md](evaluation/README.md). Raw reports tại `evaluation/results/`, có hashes dataset/source/model. CPU Windows11/Python3.13.14, 8 logical CPUs, ~11.77GiB RAM; warmup excluded, 3 inference runs, model load tách riêng. Không phải timing PDF redaction/UI.

```powershell
.\.venv\Scripts\python.exe evaluation/run.py --backend spacy
.\.venv\Scripts\python.exe evaluation/run.py --backend transformers
```

Toàn bộ suite sau M5: **75 tests passed**. Browser E2E thủ công và ảnh/GIF demo vẫn chưa thực hiện.

Thời gian pytest không phải benchmark inference. Dữ liệu tổng hợp không đại diện tài liệu thực tế.

- M2 (đã triển khai): duyệt từng occurrence, preview trước/sau, TXT labels và thống kê EMAIL.
- M3 (đã triển khai): PHONE Bắc Mỹ có định dạng, CREDIT_CARD + Luhn, ADDRESS thử nghiệm, overlap rules và bộ chọn nhóm.
- M4 (đã triển khai): spaCy baseline / Transformers tùy chọn, chunking text dài, local-only model loading; smoke hai model thật pass.
- M5: evaluation đã hoàn thành (gold dev/test, metrics, real runs, provenance); **demo GIF/browser E2E còn chưa làm**.
- Sau MVP: OCR và tiếng Việt.

## CV — mô tả đúng phần M1 đã xây

- Xây dựng ứng dụng Streamlit chạy local để phát hiện email và loại bỏ text nhạy cảm trong PDF bằng PyMuPDF redaction.
- Thiết kế ánh xạ character offsets sang bounding boxes bằng pdfplumber, hỗ trợ xử lý độc lập từng lần xuất hiện và xác minh text sau redaction.
- Viết unit/integration test với PDF tổng hợp cho chuỗi lặp, mapping nhiều dòng, PDF không có PII và các trường hợp không được hỗ trợ.
