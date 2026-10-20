# ⚖️ TEXO Legal Reviewer v2

**Rà soát căn cứ pháp lý & tiêu chuẩn trong hồ sơ** – Phòng Kỹ thuật, Công ty CP TEXO Tư vấn và Đầu tư.

Tải một hoặc nhiều hồ sơ (`.docx`, `.pdf`), app tự trích xuất toàn bộ Luật, Nghị định, Thông tư,
Quyết định, văn bản pháp quy khác, tiêu chuẩn – quy chuẩn Việt Nam và tiêu chuẩn nước ngoài, gộp
thành **danh mục**, **ma trận văn bản × file** và **báo cáo Excel** in được ngay.

## Điểm mới so với bản 1

| | Bản 1 | Bản 2 |
|---|---|---|
| Định dạng | Chỉ `.docx` | `.docx` + `.pdf` có lớp chữ (báo trang scan) |
| Số file mỗi lần | 1 | Nhiều file (tối đa 30) |
| Nhận diện | 5 mẫu regex | Số ký hiệu đầy đủ (kể cả không có chữ "Nghị định" đứng trước), dạng viết tắt `NĐ 06/2021`, Luật theo tên + năm, TCVN/QCVN/TCXDVN/22TCN/TCCS, ISO/ASTM/EN/BS/ACI/AASHTO/JIS/IEC/NFPA |
| Thông tin kèm | Mã hiệu + link | Ngày ban hành, trích yếu, vị trí (trang/đoạn/bảng), ngữ cảnh, số lần trích, file nào trích |
| Kiểm tra cách ghi | – | Thiếu số ký hiệu, thiếu năm tiêu chuẩn, trích nhiều phiên bản, ngày ghi không thống nhất, năm số hiệu ≠ năm ban hành |
| AI | – | Tuỳ chọn: bắt sót + chuẩn hoá + nhận xét hiệu lực (Claude / Gemini / OpenAI / tương thích OpenAI) |
| Giao diện | Một phần tiếng Việt | Hoàn toàn tiếng Việt, có hướng dẫn |
| Báo cáo | 1 sheet | Excel 4 sheet A4 ngang: Tổng hợp, Danh mục, Ma trận, Chi tiết |

## Chạy tại máy

```bash
pip install -r requirements.txt
streamlit run app.py
```
Mật khẩu mặc định: `texo2026` (đổi bằng `APP_PASSWORD` trong `.streamlit/secrets.toml` hoặc biến môi trường).

## Đưa lên GitHub & Streamlit Community Cloud

1. Tạo repo mới (vd `texo_legal_reviewer_v2`), đẩy toàn bộ thư mục này lên (file `.gitignore` đã chặn key AI và secrets).
2. Vào <https://share.streamlit.io> → **New app** → chọn repo, nhánh `main`, file `app.py`.
3. Mục **Advanced settings → Secrets** dán:
   ```toml
   APP_PASSWORD = "mật-khẩu-của-anh"
   ```
4. Deploy. Lần sau chỉ cần push code, app tự cập nhật.

> Trên Cloud **không** nên dùng chức năng "Lưu key tại máy" – mỗi người dán key của mình trong phiên.

## Bật AI (tuỳ chọn)

1. Thanh bên trái → **Bật AI** → chọn nhà cung cấp → dán API key (loại *tương thích OpenAI* phải điền Base URL, vd `https://openrouter.ai/api/v1`).
2. Bấm **Lấy danh sách model** → chọn model → **Kiểm tra kết nối**.
3. Chọn việc giao cho AI:
   - **Bắt sót trích dẫn** – gửi *toàn văn* tài liệu; AI chỉ bổ sung mục quy tắc bỏ sót, mỗi mục được đối chiếu lại nguyên văn (không thấy nguyên văn → gắn ⚠).
   - **Chuẩn hoá + nhận xét hiệu lực** – chỉ gửi *danh mục*; AI điền số hiệu chuẩn, tên đầy đủ, 🟢/🟠/🔴/⚪ hiệu lực, văn bản thay thế. Có ô "Thông tin cập nhật gửi kèm AI" để nhắc AI các văn bản mới.
4. Không có key hoặc lỗi API → app tự chạy bằng bộ quy tắc, không bị chặn.

⚠️ Nhận xét hiệu lực của AI chỉ để tham khảo; luôn tra cứu lại bằng link 🔎.

## Cấu trúc

```
app.py                 Giao diện Streamlit
core/extractors.py     Đọc DOCX (thân, bảng, header/footer, chú thích) và PDF (PyMuPDF, dự phòng pypdf)
core/rules.py          Bộ quy tắc nhận diện + gộp danh mục + ghi chú kiểm tra
core/ai_review.py      Lớp AI: bắt sót, chuẩn hoá, nhận xét hiệu lực
core/llm.py            Gọi REST 4 nhà cung cấp, lấy danh sách model, vá JSON bị cắt
core/pipeline.py       Điều phối nhiều file, dựng các bảng
core/export_excel.py   Báo cáo Excel A4 ngang
tests/                 Kiểm thử quy tắc và lớp AI (phản hồi giả lập)
```

Kiểm thử: `python tests/test_rules.py` và `python tests/test_ai_mock.py`.

## Giới hạn hiện tại
- Chưa OCR PDF scan; chưa đọc `.doc` (Word cũ) – lưu lại thành `.docx`.
- Luật chỉ ghi tên, không có năm/số hiệu (vd "theo Luật Xây dựng") không được bắt bằng quy tắc – bật AI để bắt sót.
