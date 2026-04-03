import docx
import re

def extract_legal_references(input_path):
    """
    Truy quét toàn diện file Word bao gồm: Paragraphs, Tables, Headers, Footers.
    Sử dụng Regex Unicode để không bỏ sót văn bản tiếng Việt.
    """
    doc = docx.Document(input_path)
    full_text = []

    # 1. Quét nội dung chính
    for para in doc.paragraphs:
        full_text.append(para.text)
    
    # 2. Quét bảng biểu
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text.append(cell.text)
                
    # 3. Quét Header & Footer (Nơi thường để căn cứ pháp lý)
    for section in doc.sections:
        for header_para in section.header.paragraphs:
            full_text.append(header_para.text)
        for footer_para in section.footer.paragraphs:
            full_text.append(footer_para.text)
    
    text = "\n".join(full_text)
    
    # Bộ Regex "Siêu lọc" - Hỗ trợ đầy đủ tiếng Việt và cấu trúc phức tạp
    patterns = [
        # Nghị định, Thông tư, Quyết định, Nghị quyết (Hỗ trợ Unicode cho NĐ-CP, TT-BXD...)
        r"(?:Nghị định|Thông tư|Quyết định|Nghị quyết)(?:\s+số)?\s+\d{1,5}/\d{4}/[^\s,;.]+?\b",
        
        # Luật có tên dài ở giữa (Ví dụ: Luật Xây dựng ... số 50/2014/QH13)
        # Bắt từ "Luật" đến khi thấy "số x/y/QH"
        r"Luật[^,;]+?số\s+\d{1,5}/\d{4}/QH\d{1,2}\b",
        
        # Luật trực tiếp (Ví dụ: Luật số 50/2014/QH13)
        r"Luật(?:\s+số)?\s+\d{1,5}/\d{4}/QH\d{1,2}\b",
        
        # Luật theo tên (Ví dụ: Luật Xây dựng 2014)
        r"Luật\s+[A-ZÀ-Ỹ][a-zà-ỹ\s\w]+[12]\d{3}\b",
        
        # Tiêu chuẩn, Quy chuẩn (Bao gồm cả TCVN/XD, QCVN...)
        r"(?:TCVN|TCXDVN|QCVN|TCVN/XD|QCXDVN)\s+\d+[:\-\s][12]\d{3}(?:/[^\s,;.]+)?\b"
    ]
    
    found_refs = []
    for p in patterns:
        matches = re.finditer(p, text, flags=re.IGNORECASE | re.UNICODE)
        for m in matches:
            ref = m.group(0).strip()
            # Làm sạch các ký tự dư thừa ở cuối
            ref = re.sub(r'[\s.;,]+$', '', ref)
            found_refs.append(ref)
    
    # Loại bỏ trùng lặp và sắp xếp
    unique_refs = sorted(list(set(found_refs)))
    return unique_refs

def audit_legal_status(refs):
    """
    Phân loại nguồn tra cứu chính xác.
    """
    results = []
    for ref in refs:
        # Tiêu chuẩn/Quy chuẩn -> VSQI
        is_standard = any(std in ref.upper() for std in ["TCVN", "QCVN", "TCXDVN", "TCVN/XD", "QCXDVN", "TIÊU CHUẨN", "QUY CHUẨN"])
        
        target_domain = "tieuchuan.vsqi.gov.vn" if is_standard else "thuvienphapluat.vn"
        
        search_query = f"{ref} {target_domain} tình trạng hiệu lực"
        search_link = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        results.append({
            "symbol": ref,
            "link": search_link
        })
    return results
