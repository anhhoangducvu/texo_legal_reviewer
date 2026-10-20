# -*- coding: utf-8 -*-
"""
LỚP AI (tuỳ chọn) – chạy TRÊN NỀN kết quả quy tắc, không thay thế.

  1. find_missing(...)        – "Bắt sót": gửi toàn văn từng file + danh sách quy tắc đã bắt
                                → AI chỉ trả các trích dẫn bị bỏ sót. Mỗi đề xuất được ĐỐI
                                CHIẾU lại với nguyên văn tài liệu (chống AI bịa).
  2. normalize_and_status(...) – "Chuẩn hoá + nhận xét hiệu lực": chỉ gửi DANH MỤC (không gửi
                                toàn văn) → AI điền số hiệu đầy đủ, trích yếu, ngày ban hành,
                                nhận xét tình trạng hiệu lực (tham khảo, phải tra cứu lại).
"""
import re

from . import llm
from .rules import scan_segment, _fold, TYPE_TO_GROUP

CHUNK_CHARS = 45000

SYS_FIND = (
    "Bạn là chuyên viên pháp chế ngành xây dựng Việt Nam. Nhiệm vụ: tìm các trích dẫn VĂN BẢN "
    "QUY PHẠM PHÁP LUẬT (Luật, Bộ luật, Nghị định, Thông tư, Quyết định, Nghị quyết, Chỉ thị, "
    "Văn bản hợp nhất, Pháp lệnh) và TIÊU CHUẨN/QUY CHUẨN (TCVN, QCVN, TCXDVN, 22TCN, ISO, ASTM, "
    "EN, BS, ACI…) trong tài liệu mà danh sách 'ĐÃ PHÁT HIỆN' còn BỎ SÓT. Chỉ lấy trích dẫn có "
    "THẬT trong tài liệu; KHÔNG suy diễn, KHÔNG bổ sung văn bản tài liệu không nhắc tới. "
    "Trả về DUY NHẤT một JSON hợp lệ, không giải thích, không rào ```.")

SCHEMA_FIND = """{
  "bo_sung": [
    {"loai": "Luật|Bộ luật|Nghị định|Thông tư|Thông tư liên tịch|Quyết định|Nghị quyết|Chỉ thị|Văn bản hợp nhất|Pháp lệnh|Tiêu chuẩn Việt Nam|Quy chuẩn Việt Nam|Tiêu chuẩn ngành|Tiêu chuẩn nước ngoài",
     "so_hieu": "số ký hiệu/mã hiệu đúng như tài liệu ghi, vd 06/2021/NĐ-CP hoặc TCVN 4453:1995",
     "ten": "tên/trích yếu nếu tài liệu có ghi, không thì để trống",
     "ngay_ban_hanh": "dd/mm/yyyy nếu tài liệu có ghi",
     "nguyen_van": "trích NGUYÊN VĂN 5-25 chữ từ tài liệu chứa trích dẫn này (chép đúng từng chữ)",
     "vi_tri": "mốc [Trang n]/[Đoạn n] gần nhất nếu có"}
  ]
}"""

SYS_NORM = (
    "Bạn là chuyên viên pháp chế ngành xây dựng Việt Nam. Với từng văn bản trong danh mục, hãy "
    "chuẩn hoá thông tin và nhận xét tình trạng hiệu lực theo hiểu biết của bạn. Kiến thức của "
    "bạn có thể chưa cập nhật các văn bản mới ban hành – khi không chắc chắn hãy ghi 'Không chắc "
    "chắn', TUYỆT ĐỐI không bịa số hiệu văn bản thay thế. Trả về DUY NHẤT một JSON hợp lệ, không "
    "giải thích, không rào ```.")

SCHEMA_NORM = """{
  "ket_qua": [
    {"id": 1,
     "so_hieu_day_du": "số ký hiệu/mã hiệu chuẩn đầy đủ (vd 06/2021/NĐ-CP; TCVN 5574:2018); để trống nếu không chắc",
     "ten_day_du": "tên/trích yếu chính thức ngắn gọn",
     "ngay_ban_hanh": "dd/mm/yyyy hoặc trống",
     "tinh_trang": "Còn hiệu lực|Hết hiệu lực|Hết hiệu lực một phần|Không chắc chắn",
     "van_ban_thay_the": "số hiệu văn bản thay thế/sửa đổi nếu chắc chắn, không thì trống",
     "ghi_chu": "1 câu ngắn: căn cứ nhận xét / lưu ý khi áp dụng",
     "nghi_ngo_sai": "true nếu mục này có vẻ KHÔNG phải văn bản pháp luật/tiêu chuẩn hoặc ghi sai số hiệu"}
  ]
}"""

STATUS_ICON = {"Còn hiệu lực": "🟢", "Hết hiệu lực": "🔴", "Hết hiệu lực một phần": "🟠",
               "Không chắc chắn": "⚪"}


def _chunks(text, size=CHUNK_CHARS):
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        j = min(len(text), i + size)
        if j < len(text):
            k = text.rfind("\n", i + size // 2, j)
            j = k if k > i else j
        out.append(text[i:j])
        i = j
    return out


def _squash(s):
    return re.sub(r"[\s\W_]+", "", _fold(s))


def find_missing(cfg, filename, text, known_displays, today):
    """Trả (danh_sách_occurrence_AI, [cảnh báo])."""
    occs, warns = [], []
    plain = _squash(text)
    known_list = "\n".join(f"- {d}" for d in known_displays) or "(chưa có)"
    parts = _chunks(text)
    for idx, part in enumerate(parts, 1):
        user = (f"Hôm nay: {today}. Tài liệu: {filename} (phần {idx}/{len(parts)}).\n\n"
                f"ĐÃ PHÁT HIỆN (lớp quy tắc) – KHÔNG liệt kê lại:\n{known_list}\n\n"
                f"Trả JSON theo schema:\n{SCHEMA_FIND}\n\n"
                f"=== NỘI DUNG TÀI LIỆU ===\n{part}")
        res = llm.ask_json(cfg["provider"], cfg["model"], cfg["key"], user, cfg.get("base_url"), SYS_FIND)
        if not res.get("ok"):
            warns.append(f"{filename} – phần {idx}: {res.get('error')}")
            continue
        if res.get("truncated"):
            warns.append(f"{filename} – phần {idx}: phản hồi AI có thể bị cắt cụt, có thể thiếu mục cuối.")
        for it in (res["data"].get("bo_sung") or []):
            if not isinstance(it, dict):
                continue
            so = str(it.get("so_hieu") or "").strip()
            nv = str(it.get("nguyen_van") or "").strip()
            if not so:
                continue
            loc = str(it.get("vi_tri") or "").strip(" []") or "(AI)"
            verified = bool(nv) and _squash(nv) in plain
            if not verified:
                # chấp nhận nếu chính số hiệu xuất hiện nguyên văn
                verified = _squash(so) in plain
            # chạy lại bộ quy tắc trên câu AI trích để chuẩn hoá khoá
            parsed = scan_segment(nv or so, loc, filename) or scan_segment(so, loc, filename)
            if parsed:
                for p in parsed:
                    p["source"] = "AI"
                    p["ai_verified"] = verified
                    if it.get("ten") and not p.get("title"):
                        p["title"] = str(it["ten"])[:220]
                    if it.get("ngay_ban_hanh") and not p.get("date"):
                        p["date"] = str(it["ngay_ban_hanh"])
                    occs.append(p)
            else:
                vtype = str(it.get("loai") or "Văn bản pháp quy khác")
                if vtype not in TYPE_TO_GROUP:
                    vtype = "Văn bản pháp quy khác"
                occs.append(dict(key="AI|" + _squash(so).upper(), kind="ai", vtype=vtype, symbol=so,
                                 num="", year="", name="", date=str(it.get("ngay_ban_hanh") or ""),
                                 title=str(it.get("ten") or "")[:220], raw=so, context=nv,
                                 file=filename, loc=loc, source="AI", ai_verified=verified))
    return occs, warns


def normalize_and_status(cfg, catalog_items, today, extra_notes=""):
    """catalog_items: list mục danh mục. Ghi kết quả thẳng vào từng mục. Trả [cảnh báo]."""
    warns = []
    batch = 50
    for b in range(0, len(catalog_items), batch):
        items = catalog_items[b:b + batch]
        lines = []
        for i, c in enumerate(items, 1):
            ctx = c["occ"][0].get("context", "")[:220] if c.get("occ") else ""
            lines.append(f"{i}. [{c['vtype']}] {c['display']} | ngày ghi trong hồ sơ: {c.get('date') or '-'} "
                         f"| trích yếu ghi trong hồ sơ: {c.get('title') or '-'} | ngữ cảnh: {ctx}")
        notes = f"\nTHÔNG TIN CẬP NHẬT DO NGƯỜI DÙNG CUNG CẤP (ưu tiên áp dụng):\n{extra_notes}\n" if extra_notes.strip() else ""
        user = (f"Hôm nay: {today}.{notes}\nDANH MỤC (id. [loại] số hiệu | …):\n" + "\n".join(lines) +
                f"\n\nTrả JSON theo schema (đủ {len(items)} mục, giữ đúng id):\n{SCHEMA_NORM}")
        res = llm.ask_json(cfg["provider"], cfg["model"], cfg["key"], user, cfg.get("base_url"), SYS_NORM)
        if not res.get("ok"):
            warns.append(f"Chuẩn hoá/hiệu lực (mục {b + 1}–{b + len(items)}): {res.get('error')}")
            continue
        if res.get("truncated"):
            warns.append(f"Chuẩn hoá/hiệu lực (mục {b + 1}–{b + len(items)}): phản hồi có thể bị cắt cụt.")
        for r in (res["data"].get("ket_qua") or []):
            try:
                i = int(r.get("id")) - 1
            except Exception:
                continue
            if not (0 <= i < len(items)):
                continue
            c = items[i]
            st_ = str(r.get("tinh_trang") or "Không chắc chắn").strip()
            if st_ not in STATUS_ICON:
                st_ = "Không chắc chắn"
            c["ai_status"] = st_
            c["ai_fullsymbol"] = str(r.get("so_hieu_day_du") or "").strip()
            c["ai_fullname"] = str(r.get("ten_day_du") or "").strip()
            c["ai_date"] = str(r.get("ngay_ban_hanh") or "").strip()
            c["ai_replaced_by"] = str(r.get("van_ban_thay_the") or "").strip()
            c["ai_note"] = str(r.get("ghi_chu") or "").strip()
            sus = r.get("nghi_ngo_sai")
            c["ai_suspect"] = sus is True or str(sus).lower() == "true"
    return warns
