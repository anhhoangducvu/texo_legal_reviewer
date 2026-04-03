import re

def test_extract(text):
    patterns = [
        # Nghị định, Thông tư, Quyết định, Nghị quyết (Unicode)
        r"(?:Nghị định|Thông tư|Quyết định|Nghị quyết)(?:\s+số)?\s+\d{1,5}/\d{4}/[^\s,;.]+?\b",
        
        # Luật có tên dài ở giữa (Ví dụ: Luật Xây dựng ... số 50/2014/QH13)
        r"Luật[^,;]+?số\s+\d{1,5}/\d{4}/QH\d{1,2}\b",
        
        # Luật trực tiếp (Ví dụ: Luật số 50/2014/QH13)
        r"Luật(?:\s+số)?\s+\d{1,5}/\d{4}/QH\d{1,2}\b",
        
        # Luật theo tên (Ví dụ: Luật Xây dựng 2014)
        r"Luật\s+[A-ZÀ-Ỹ][a-zà-ỹ\s\w]+[12]\d{3}\b",
        
        # Tiêu chuẩn, Quy chuẩn
        r"(?:TCVN|TCXDVN|QCVN|TCVN/XD|QCXDVN)\s+\d+[:\-\s][12]\d{3}(?:/[^\s,;.]+)?\b"
    ]
    
    found_refs = []
    for p in patterns:
        matches = re.finditer(p, text, flags=re.IGNORECASE | re.UNICODE)
        for m in matches:
            ref = m.group(0).strip()
            ref = re.sub(r'[\s.;,]+$', '', ref)
            found_refs.append(ref)
    
    return sorted(list(set(found_refs)))

sample_text = """
- Luật Xây dựng của nước Cộng hoà xã hội chủ nghĩa Việt Nam, số 50/2014/QH13 ngày 18/06/2014; và số 62/2020/QH14 ngày 17/06/2020 sửa đổi, bổ sung một số điều của luật Xây dựng.
- Nghị định số 06/2021/NĐ-CP ngày 26/01/2021 của Chính Phủ về Quản lý chất lượng, thi công xây dựng và bảo trì công trình xây dựng. 
- Nghị định số 175/2024/NĐ-CP ngày 30/12/2024 Chính Phủ về : Quy định chi tiết một số điều và biện pháp thi hành Luật Xây dựng về quản lý hoạt động xây dựng.
- Nghị định 35/2023/NĐ-CP ngày 20/06/2023 của chính phủ về sửa đổi, bổ sung các Nghị định lĩnh vực quản lý nhà nước Bộ Xây dựng.
- Thông tư 10/2021/TT-BXD Hướng dẫn một số điều và biện pháp thi hành Nghị định số 06/2021/NĐ-CP ngày 26/01/2021.
- Thông tư 06/2021/TT-BXD ngày 30/06/2021 của Bộ xây dựng quy định về phân cấp công trình xây dựng và hướng dẫn áp dụng trong quản lý hoạt động đầu tư xây dựng;
- Nghị định số 145/2020/NĐ-CP ngày 14/12/2020 Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật lao động về điều kiện lao động và quan hệ lao động
"""

results = test_extract(sample_text)
print(f"Tìm thấy {len(results)} văn bản:")
for r in results:
    print(f" - {r}")
