# -*- coding: utf-8 -*-
"""Kiểm thử lớp AI bằng phản hồi giả (không cần key)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import llm
from core.pipeline import read_files, run_ai_find, make_catalog, catalog_df
from core.ai_review import normalize_and_status

def fake(provider, model, key, system, user, base_url=None):
    if "bo_sung" in user:
        return json.dumps({"bo_sung": [
            {"loai": "Nghị định", "so_hieu": "15/2021/NĐ-CP", "ten": "Quản lý dự án", "ngay_ban_hanh": "",
             "nguyen_van": "theo nghị định mười lăm năm 2021", "vi_tri": "Đoạn 3"},   # AI bịa → không có nguyên văn
            {"loai": "Tiêu chuẩn Việt Nam", "so_hieu": "TCVN 4453:1995", "ten": "", "ngay_ban_hanh": "",
             "nguyen_van": "TCVN 4453:1995", "vi_tri": "Bảng 1"}]})                     # trùng quy tắc → bỏ
    n = user.count("\n") 
    import re
    ids = re.findall(r"^(\d+)\. ", user, flags=re.M)
    return json.dumps({"ket_qua": [{"id": int(i), "so_hieu_day_du": "", "ten_day_du": "Tên AI " + i,
                        "ngay_ban_hanh": "", "tinh_trang": "Không chắc chắn" if int(i) % 2 else "Còn hiệu lực",
                        "van_ban_thay_the": "", "ghi_chu": "ghi chú", "nghi_ngo_sai": "false"} for i in ids]})[:-30]  # cắt cụt cố ý

llm.call_llm = fake
cfg = {"provider": "gemini", "model": "x", "key": "k"}
fi = read_files([(n, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples', n), 'rb').read()) for n in ['DeCuong_TVGS.docx']])
print("warn find:", run_ai_find(cfg, fi, "20/10/2026"))
items = make_catalog(fi)
print("warn norm:", normalize_and_status(cfg, items, "20/10/2026"))
df = catalog_df(items, True)
print(df[["Số hiệu / Mã hiệu", "Nguồn", "Hiệu lực (AI)", "Tên đầy đủ (AI)", "Ghi chú kiểm tra"]].to_string())
# nhánh lỗi
print(llm.balance_json('{"a":[{"b":"c'))
llm.call_llm = llm.__dict__['call_llm']
