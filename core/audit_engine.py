import docx
import re

def extract_legal_references(input_path):
    """
    Truy quét toàn bộ văn bản để tìm các mã hiệu Nghị định, Thông tư, Luật...
    Cải tiến Regex để bắt trọn mọi hậu tố và các loại văn bản mới.
    """
    doc = docx.Document(input_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text.append(cell.text)
    
    text = "\n".join(full_text)
    
    # Regex nâng cao: Tổng quát hóa để tránh bỏ sót
    patterns = [
        # Thông tư, Nghị định, Quyết định (Bắt mọi hậu tố viết hoa như TT-BGDĐT, TT-BLĐTBXH...)
        r"(?:Nghị định|Thông tư|Quyết định)(?:\s+số)?\s+\d{1,5}/\d{4}/[A-Z0-9-]+\b",
        # Luật (Dạng số hiệu: Luật số 50/2014/QH13)
        r"Luật(?:\s+số)?\s+\d{1,5}/\d{4}/QH\d{1,2}\b",
        # Luật (Dạng tên gọi: Luật Xây dựng 2014) - Bắt cụm từ bắt đầu bằng chữ hoa và kết thúc bằng năm
        r"Luật\s+[A-ZÀ-Ỹ][a-zà-ỹ\s\w]+[12]\d{3}\b",
        # Tiêu chuẩn, Quy chuẩn (TCVN, QCVN, TCXDVN)
        r"(?:TCVN|TCXDVN|QCVN|TCVN/XD)\s+\d+[:\-\s][12]\d{3}(?:/[A-Z0-9-]+)?",
        # Nghị quyết
        r"Nghị quyết(?:\s+số)?\s+\d+/\d{4}/[A-Z0-9-]+\b"
    ]
    
    found_refs = []
    for p in patterns:
        matches = re.finditer(p, text, flags=re.IGNORECASE)
        for m in matches:
            found_refs.append(m.group(0))
    
    # Loại bỏ trùng lặp và sắp xếp
    unique_refs = sorted(list(set(found_refs)))
    return unique_refs

def audit_legal_status(refs):
    """
    Phân loại nguồn tra cứu: 
    - Tiêu chuẩn/Quy chuẩn -> tieuchuan.vsqi.gov.vn
    - Luật/Thông tư/Nghị định -> thuvienphapluat.vn
    """
    results = []
    for ref in refs:
        # Xác định xem có phải là Tiêu chuẩn/Quy chuẩn hay không
        is_standard = any(std in ref.upper() for std in ["TCVN", "QCVN", "TCXDVN", "TCVN/XD"])
        
        # Chọn domain tra cứu phù hợp
        target_domain = "tieuchuan.vsqi.gov.vn" if is_standard else "thuvienphapluat.vn"
        
        search_query = f"{ref} {target_domain} tình trạng hiệu lực"
        search_link = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        results.append({
            "symbol": ref,
            "link": search_link
        })
    return results
