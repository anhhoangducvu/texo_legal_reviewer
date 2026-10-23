# -*- coding: utf-8 -*-
"""
TEXO LEGAL REVIEWER v2 – Trích xuất căn cứ pháp lý & tiêu chuẩn từ hồ sơ (.docx, .pdf)
Phòng Kỹ thuật – Công ty CP TEXO Tư vấn và Đầu tư

Chạy:  streamlit run app.py
"""
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from core import llm
from core.pipeline import (read_files, run_ai_find, make_catalog, file_summary, catalog_df,
                           matrix_df, detail_df)
from core.ai_review import normalize_and_status
from core.export_excel import build_excel
from core.rules import GROUP_ORDER, GROUP_SHORT
from core import ui

APP_VERSION = "2.1"
APP_DIR = Path(__file__).parent
SAVED_KEY_FILE = APP_DIR / ".secrets_local.json"
MAX_FILES = 30

TITLE = "Rà soát căn cứ pháp lý & tiêu chuẩn"
ui.setup("TEXO · Rà soát căn cứ pháp lý & tiêu chuẩn", "⚖️")
ui.gate("Rà soát căn cứ pháp lý")
ui.header(TITLE, "Phòng Kỹ thuật · Trích xuất Luật, Nghị định, Thông tư, tiêu chuẩn – quy chuẩn từ hồ sơ Word/PDF")


# =============================================================================== API KEY lưu tại máy
def load_saved():
    try:
        return json.loads(SAVED_KEY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_key(provider, key, base_url):
    data = load_saved()
    data[provider] = {"key": key, "base_url": base_url}
    SAVED_KEY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_saved():
    try:
        SAVED_KEY_FILE.unlink()
    except Exception:
        pass


# =============================================================================== SIDEBAR – AI
ss = st.session_state
ss.setdefault("models", {})
ss.setdefault("result", None)

with st.sidebar:
    st.markdown("### 🤖 Trợ lý AI (tùy chọn)")
    prov_keys = list(llm.PROVIDERS.keys())
    provider = st.selectbox("Nhà cung cấp", ["(Không dùng AI)"] + prov_keys,
                            format_func=lambda k: llm.PROVIDERS[k]["label"] if k in llm.PROVIDERS else k)
    ai_on = provider != "(Không dùng AI)"
    cfg = None
    ai_find = ai_norm = False
    extra_notes = ""
    if not ai_on:
        st.caption("Đang chạy bằng bộ quy tắc – miễn phí, dữ liệu không rời máy.")
    else:
        saved = load_saved().get(provider, {})
        key = st.text_input("API key", value=saved.get("key", ""), type="password")
        base_url = ""
        if llm.PROVIDERS[provider]["needs_base_url"]:
            base_url = st.text_input("Base URL", value=saved.get("base_url", ""),
                                     placeholder="https://openrouter.ai/api/v1")
        if st.button("Lấy danh sách model", disabled=not key):
            with st.spinner("Đang lấy danh sách model…"):
                ok, res = llm.list_models(provider, key.strip(), base_url.strip() or None)
            if ok and res:
                ss.models[provider] = res
            elif ok:
                st.warning("Key hợp lệ nhưng không có model nào khả dụng.")
            else:
                st.error(res)
        models = ss.models.get(provider, [])
        model = None
        if models:
            default = llm.pick_default(models)
            model = st.selectbox("Model", models, index=models.index(default) if default in models else 0)
            if st.button("Kiểm tra kết nối"):
                with st.spinner("Đang gọi thử…"):
                    ok, msg = llm.test_connection(provider, model, key.strip(), base_url.strip() or None)
                (st.success if ok else st.error)(("Kết nối được: " if ok else "") + msg)
        st.caption(llm.PROVIDERS[provider]["note"])

        st.markdown("**Việc giao cho AI**")
        ai_find = st.checkbox("🔍 Bắt sót trích dẫn (gửi toàn văn)", value=True,
                              help="AI đọc toàn văn từng file, bổ sung trích dẫn mà bộ quy tắc bỏ sót. "
                                   "Mỗi đề xuất được đối chiếu lại với nguyên văn tài liệu.")
        ai_norm = st.checkbox("🧭 Chuẩn hoá + nhận xét hiệu lực (chỉ gửi danh mục)", value=True,
                              help="AI điền số hiệu đầy đủ, tên chính thức, nhận xét còn/hết hiệu lực. "
                                   "Chỉ gửi danh mục văn bản, không gửi toàn văn. Kết quả chỉ để tham khảo.")
        if ai_norm:
            extra_notes = st.text_area("Thông tin cập nhật gửi kèm AI", height=90,
                                       placeholder="VD: Văn bản A đã được thay thế bởi văn bản B từ ngày …",
                                       help="AI có thể chưa biết văn bản mới ban hành. Ghi chú ở đây được "
                                            "gửi kèm để AI ưu tiên áp dụng.")

        luu = st.checkbox("Lưu key trên máy này", value=bool(saved.get("key")))
        if luu and key:
            if saved.get("key") != key.strip() or saved.get("base_url", "") != base_url.strip():
                save_key(provider, key.strip(), base_url.strip())
        elif not luu and SAVED_KEY_FILE.exists():
            delete_saved()
        st.caption("⚠️ Bật AI thì nội dung tài liệu được gửi tới nhà cung cấp đã chọn – không dùng với hồ sơ mật. "
                   "Chỉ lưu key trên máy cá nhân, không lưu trên Streamlit Cloud.")

        if key and model and (provider != "openai_compat" or base_url.strip()):
            cfg = {"provider": provider, "model": model, "key": key.strip(), "base_url": base_url.strip() or None}
        else:
            st.info("Nhập key và chọn model để bật AI.")
        if not (ai_find or ai_norm):
            cfg = None

    st.divider()
    if cfg:
        ui.badge(f"AI sẵn sàng – {cfg['model']}", "green")
    elif ai_on:
        ui.badge("Chưa đủ cấu hình AI → chạy bằng quy tắc", "orange")
    else:
        ui.badge("Chế độ quy tắc (không AI)", "grey")
    st.caption("")
    ui.logout_button()
    st.caption(f"Rà soát căn cứ pháp lý v{APP_VERSION} · Xây dựng: Hoàng Đức Vũ")

# =============================================================================== TRANG CHỦ
with st.expander("📘 Hướng dẫn sử dụng"):
    st.markdown("""
**App làm được gì:** đọc `.docx` (cả bảng, header, footer, chú thích) và `.pdf` có lớp chữ; tải tối đa 30 file cùng lúc, gộp trùng thành danh mục và ma trận văn bản × file; cảnh báo thiếu số ký hiệu, thiếu năm, nhiều phiên bản, ngày lệch; AI tùy chọn để bắt sót, chuẩn hoá tên, nhận xét hiệu lực.

1. **Tải hồ sơ**: kéo thả một hoặc nhiều file `.docx` / `.pdf` vào ô bên dưới.
2. **(Tuỳ chọn) Trợ lý AI** ở thanh bên trái: chọn nhà cung cấp → dán API key → *Lấy danh sách model* → *Kiểm tra kết nối*.
3. Bấm **Bắt đầu rà soát**. Kết quả gồm:
   - **Danh mục văn bản**: mỗi văn bản một dòng, có ngày ban hành, trích yếu, file nào trích, ghi chú kiểm tra, link tra cứu hiệu lực.
   - **Theo từng file**: số văn bản mỗi nhóm trong từng file, cảnh báo đọc file.
   - **Ma trận VB × File**: xem nhanh văn bản nào được trích ở file nào.
   - **Chi tiết trích dẫn**: vị trí (trang/đoạn/bảng) và câu ngữ cảnh của từng lần trích.
4. Bấm **Tải báo cáo Excel** để lưu toàn bộ kết quả (khổ A4 ngang, in được ngay).

**Lưu ý**
- PDF dạng **ảnh scan** (không bôi đen chọn được chữ) chưa đọc được – app sẽ báo trang nào là scan.
- File Word cũ `.doc` cần mở bằng Word và *Lưu thành* `.docx` trước.
- Tình trạng hiệu lực luôn phải tra cứu lại tại nguồn chính thức (nút 🔎 trong danh mục). Nhận xét của AI chỉ để tham khảo.
""")

st.markdown("##### 📥 Tải hồ sơ cần rà soát")
uploads = st.file_uploader("Chọn hoặc kéo thả file (.docx, .pdf) – có thể chọn nhiều file",
                           type=["docx", "pdf"], accept_multiple_files=True)
if uploads and len(uploads) > MAX_FILES:
    st.warning(f"Anh/chị đã chọn {len(uploads)} file; app xử lý {MAX_FILES} file đầu tiên.")
    uploads = uploads[:MAX_FILES]

run = st.button("🚀 Bắt đầu rà soát", type="primary", disabled=not uploads, use_container_width=True)

# =============================================================================== XỬ LÝ
if run and uploads:
    today = datetime.now().strftime("%d/%m/%Y")
    files = [(u.name, u.getvalue()) for u in uploads]
    warnings = []
    prog = st.progress(0.0, text="Đang đọc file…")
    file_items = read_files(files)
    prog.progress(0.35, text="Đã quét xong bằng bộ quy tắc.")
    mode_text = "Quy tắc (không AI)"
    if cfg and cfg.get("key"):
        mode_text = f"Quy tắc + AI ({llm.PROVIDERS[cfg['provider']]['label']} – {cfg['model']})"
        if ai_find:
            def _p(n, total, name):
                prog.progress(0.35 + 0.4 * (n - 1) / max(total, 1), text=f"AI đang đọc {name} ({n}/{total})…")
            warnings += run_ai_find(cfg, file_items, today, _p)
    items = make_catalog(file_items)
    if cfg and cfg.get("key") and ai_norm and items:
        prog.progress(0.8, text="AI đang chuẩn hoá & nhận xét hiệu lực…")
        warnings += normalize_and_status(cfg, items, today, extra_notes)
    prog.progress(1.0, text="Hoàn tất.")
    for it in file_items:
        if it["error"]:
            warnings.append(f"{it['name']}: {it['error']}")
    with_ai = bool(cfg and ai_norm)
    sum_df = file_summary(file_items, items)
    cat_df = catalog_df(items, with_ai=with_ai)
    mat_df = matrix_df(items, file_items)
    det_df = detail_df(items)
    xlsx = build_excel(file_items, items, sum_df, cat_df, mat_df, det_df, mode_text, warnings)
    ss.result = dict(items=items, file_items=[{k: v for k, v in it.items() if k not in ("segments", "text")}
                                              for it in file_items],
                     sum_df=sum_df, cat_df=cat_df, mat_df=mat_df, det_df=det_df, xlsx=xlsx,
                     warnings=warnings, mode=mode_text, with_ai=with_ai,
                     stamp=datetime.now().strftime("%Y%m%d_%H%M"))
    prog.empty()

# =============================================================================== KẾT QUẢ
R = ss.result
if R:
    items = R["items"]
    st.markdown("---")
    head_l, head_r = st.columns([3, 1.2])
    head_l.markdown(f"#### 📊 Kết quả rà soát – {len(R['file_items'])} file")
    head_l.caption(f"Chế độ: {R['mode']}")
    head_r.download_button("📥 Tải báo cáo Excel", data=R["xlsx"], type="primary", use_container_width=True,
                           file_name=f"TEXO_RaSoat_CanCuPhapLy_{R['stamp']}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if not items:
        st.warning("Không tìm thấy căn cứ pháp lý/tiêu chuẩn nào trong các file đã tải.")
    n_pq = sum(1 for c in items if c["group"] in GROUP_ORDER[:5])
    n_vn = sum(1 for c in items if c["group"] == GROUP_ORDER[5])
    n_nn = sum(1 for c in items if c["group"] == GROUP_ORDER[6])
    n_flag = sum(1 for c in items if c["flags"])
    k = st.columns(5)
    ui.kpi(k[0], len(items), "Tổng văn bản", f"{len(R['file_items'])} file đã đọc")
    ui.kpi(k[1], n_pq, "Văn bản pháp quy", "Luật, NĐ, TT, QĐ…")
    ui.kpi(k[2], n_vn, "TC / QC Việt Nam", "TCVN, QCVN, TCXDVN…")
    ui.kpi(k[3], n_nn, "TC nước ngoài", "ISO, ASTM, EN, BS…")
    ui.kpi(k[4], n_flag, "Cần lưu ý", "ghi cách trích chưa chuẩn", "orange" if n_flag else "green")
    if n_flag:
        ui.callout(f"⚠️ Có <b>{n_flag}</b> văn bản ghi chưa chuẩn (thiếu số ký hiệu, thiếu năm, nhiều phiên bản…) – "
                   "xem cột <i>Ghi chú kiểm tra</i> ở tab Danh mục.", "orange")
    else:
        ui.callout("✅ Không phát hiện cách ghi trích dẫn bất thường. Vẫn cần tra cứu lại hiệu lực bằng nút 🔎.", "green")

    tabs = st.tabs(["📋 Danh mục văn bản", "📁 Theo từng file", "🔢 Ma trận VB × File",
                    "📍 Chi tiết trích dẫn", f"⚠️ Cảnh báo ({len(R['warnings'])})"])
    link_cfg = {"STT": st.column_config.NumberColumn("STT", width="small", pinned=True),
                "Số hiệu / Mã hiệu": st.column_config.TextColumn("Số hiệu / Mã hiệu", pinned=True),
                "Văn bản": st.column_config.TextColumn("Văn bản", pinned=True),
                "Tra cứu hiệu lực": st.column_config.LinkColumn("Tra cứu", display_text="🔎 Tra cứu",
                                                               width="small", pinned=True,
                                                               help="Bấm để mở trang tra cứu tình trạng hiệu lực")}

    with tabs[0]:
        f1, f2, f3 = st.columns([2, 2, 1])
        groups = f1.multiselect("Lọc theo nhóm", GROUP_ORDER, default=[],
                                placeholder="Tất cả nhóm")
        q = f2.text_input("Tìm theo số hiệu / tên", placeholder="VD: 06/2021, TCVN 5574, đấu thầu…")
        only_flag = f3.checkbox("Chỉ mục cần lưu ý", value=False)
        df = R["cat_df"].copy()
        if groups:
            df = df[df["Nhóm"].isin(groups)]
        if q:
            ql = q.lower()
            df = df[df.apply(lambda r: ql in " ".join(str(v) for v in r.values).lower(), axis=1)]
        if only_flag:
            df = df[df["Ghi chú kiểm tra"].astype(str).str.len() > 0]
        st.caption(f"Hiển thị {len(df)}/{len(R['cat_df'])} văn bản")
        st.dataframe(df, hide_index=True, use_container_width=True, column_config=link_cfg, height=520)
        if R["with_ai"]:
            st.caption("🟢 còn hiệu lực • 🟠 hết hiệu lực một phần • 🔴 hết hiệu lực • ⚪ không chắc chắn — "
                       "nhận xét của AI chỉ để tham khảo, luôn tra cứu lại bằng nút 🔎.")

    with tabs[1]:
        st.dataframe(R["sum_df"], hide_index=True, use_container_width=True)
        for fi in R["file_items"]:
            mine = [c for c in items if fi["name"] in c["files"]]
            icon = "❌" if fi["error"] else ("⚠️" if fi["warnings"] else "✅")
            with st.expander(f"{icon} {fi['name']} — {len(mine)} văn bản"):
                if fi["error"]:
                    st.error(fi["error"])
                for w in fi["warnings"]:
                    st.warning(w)
                for g in GROUP_ORDER:
                    sub = [c for c in mine if c["group"] == g]
                    if sub:
                        st.markdown(f"**{g}** ({len(sub)})")
                        st.markdown("\n".join(f"- {c['display']}" + (f" — *{c['title']}*" if c['title'] else "")
                                              + (f" &nbsp;🚩 {'; '.join(c['flags'])}" if c['flags'] else "")
                                              for c in sub))

    with tabs[2]:
        st.caption("Số trong ô = số lần văn bản được trích trong file đó.")
        st.dataframe(R["mat_df"], hide_index=True, use_container_width=True, height=520, column_config=link_cfg)

    with tabs[3]:
        st.dataframe(R["det_df"], hide_index=True, use_container_width=True, height=520, column_config=link_cfg)

    with tabs[4]:
        if R["warnings"]:
            for w in R["warnings"]:
                st.warning(w)
        else:
            st.success("Không có cảnh báo khi xử lý.")
elif not uploads:
    st.info("Tải một hoặc nhiều hồ sơ ở trên để bắt đầu.")
