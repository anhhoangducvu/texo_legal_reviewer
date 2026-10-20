# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.rules import scan_segment, build_catalog, sort_key

SAMPLE = """- Luật Xây dựng của nước Cộng hoà xã hội chủ nghĩa Việt Nam, số 50/2014/QH13 ngày 18/06/2014; và số 62/2020/QH14 ngày 17/06/2020 sửa đổi, bổ sung một số điều của luật Xây dựng.
- Nghị định số 06/2021/NĐ-CP ngày 26/01/2021 của Chính Phủ về Quản lý chất lượng, thi công xây dựng và bảo trì công trình xây dựng.
- Nghị định số 175/2024/NĐ-CP ngày 30/12/2024 Chính Phủ về : Quy định chi tiết một số điều và biện pháp thi hành Luật Xây dựng về quản lý hoạt động xây dựng.
- Thông tư 10/2021/TT-BXD Hướng dẫn một số điều và biện pháp thi hành Nghị định số 06/2021/NĐ-CP ngày 26/01/2021.
- Quyết định số 1329/QĐ-BXD ngày 19/12/2016 của Bộ Xây dựng công bố định mức sử dụng vật liệu.
- Theo NĐ 06/2021 và Thông tư 10/2021, Luật Đấu thầu năm 2023, Bộ luật Dân sự 2015, Luật Xây dựng 2014.
- Văn bản hợp nhất 02/VBHN-BXD; Thông tư liên tịch 04/2017/TTLT-BXD-BTC; Chỉ thị 15/CT-TTg.
- Nghị định 15/2021/ND-CP (viết không dấu); Nghị định 99/2021/NĐ-CP ngày 11/11/2020.
- Thi công theo TCVN 4453:1995, TCVN 4453-1995, TCVN 9394 : 2012, TCVN 5574:2012 và TCVN 5574-2018; QCVN 06:2022/BXD; QCVN 01-1:2018/BYT; 22TCN 272-05; TCXDVN 371:2006; TCVN 10304:2014; TCVN 4091; TCVN ISO 9001:2015.
- Nước ngoài: ASTM C39/C39M-21, ASTM A615, BS EN 1992-1-1:2004, EN 206, ACI 318-19, ISO 9001:2015, AASHTO LRFD, JIS G3112, IEC 60364-5-52, NFPA 13.
- Ngày 26/01/2021, tỷ lệ 1/2 không phải văn bản. Khối lượng 12/2020 m3.
"""
occ = scan_segment(SAMPLE, "Đoạn 1", "test.docx")
cat = build_catalog(occ)
for c in sorted(cat.values(), key=sort_key):
    print(f"[{c['group'][:14]:14}] {c['display']:<45} | date={c['date']:<10} | title={c['title'][:50]!r} | flags={c['flags']}")
print(len(cat))
