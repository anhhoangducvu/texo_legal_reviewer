import docx
import re

def extract_legal_references(input_path):
    """
    Truy quét toàn bộ văn bản để tìm các mã hiệu Nghị định, Thông tư, Luật...
    Ví dụ: 10/2021/NĐ-CP, 06/2021/TT-BXD, Luật Xây dựng 2014...
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
    
    # Regex nâng cao (dùng non-capturing groups để lấy full match)
    patterns = [
        r"(?:Nghị định|Thông tư)(?:\s+số)?\s+\d{1,5}/\d{4}/(?:NĐ-CP|TT-BXD|TT-BTC|QH\d{1,2}|TT-BKHĐT|TT-BNV|NĐ-TTg|TT-BYT|TT-BNNPTNT|TT-BXD)\b",
        r"Luật(?:\s+số)?\s+\d{1,5}/\d{4}/QH\d{1,2}\b",
        r"Quyết định(?:\s+số)?\s+\d+/\d{4}/(?:QĐ-TTg|QĐ-UBND|QĐ-BXD)\b",
        r"(?:TCVN|TCXDVN|QCVN)\s+\d+[:\s][12]\d{3}(?:/BXD|/BTNMT|/BCA|/BCT)?",
        r"Luật\s+[\w\s\d]+[12]\d{3}"
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
    Giai đoạn sau: Kết nối API hoặc Tra cứu Web để kiểm tra trạng thái.
    Hiện tại: Trả về danh sách để người dùng đối soát nhanh qua link.
    """
    results = []
    for ref in refs:
        # Sử dụng Google Search ưu tiên trang thuvienphapluat.vn để đảm bảo luôn tìm thấy văn bản sống
        search_query = f"{ref} thuvienphapluat.vn"
        search_link = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        results.append({
            "symbol": ref,
            "link": search_link
        })
    return results
