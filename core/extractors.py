# -*- coding: utf-8 -*-
"""
Đọc nội dung tài liệu thành danh sách "đoạn" có vị trí, để lớp quy tắc và lớp AI dùng chung.

Mỗi đoạn: {"loc": "Trang 3" | "Đoạn 12" | "Bảng 2" | "Header"..., "text": "..."}

Hỗ trợ:
  - .docx : thân văn bản (đoạn + bảng + textbox, theo đúng thứ tự), header, footer,
            chú thích cuối trang (footnote) nếu có.
  - .pdf  : PDF có lớp chữ (PyMuPDF; dự phòng pypdf). Trang không có chữ được đánh dấu
            là "trang scan" để cảnh báo (bản này chưa OCR).
"""
import io
import re
import unicodedata
import zipfile

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SUPPORTED_EXT = ("docx", "pdf")


class ExtractResult(dict):
    """dict gồm: segments, kind, pages, warnings, scanned_pages, chars"""


def clean_text(s: str) -> str:
    """Chuẩn hoá Unicode (NFC – PDF tiếng Việt hay ra dạng tổ hợp NFD), khoảng trắng lạ."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace(" ", " ").replace("​", "").replace("﻿", "")
    s = s.replace("–", "-").replace("—", "-").replace("‐", "-").replace("‑", "-")
    s = s.replace("：", ":")
    return s


# --------------------------------------------------------------------------- DOCX
def _para_text(p_el) -> str:
    parts = []
    for node in p_el.iter():
        tag = node.tag
        if tag == W_NS + "t" and node.text:
            parts.append(node.text)
        elif tag in (W_NS + "tab",):
            parts.append(" ")
        elif tag in (W_NS + "br", W_NS + "cr"):
            parts.append(" ")
    return "".join(parts)


def _iter_body_blocks(body_el):
    """Duyệt thân văn bản theo thứ tự; trả (kiểu, chỉ số, text)."""
    p_no, t_no = 0, 0
    for child in body_el:
        if child.tag == W_NS + "p":
            p_no += 1
            txt = _para_text(child)
            if txt.strip():
                yield f"Đoạn {p_no}", txt
        elif child.tag == W_NS + "tbl":
            t_no += 1
            rows = []
            for tr in child.iter(W_NS + "tr"):
                cells = []
                for tc in tr.findall(W_NS + "tc"):
                    ctext = " ".join(_para_text(p) for p in tc.iter(W_NS + "p"))
                    cells.append(ctext.strip())
                # bỏ ô trùng do gộp ô
                dedup = []
                for c in cells:
                    if c and (not dedup or dedup[-1] != c):
                        dedup.append(c)
                if dedup:
                    rows.append(" | ".join(dedup))
            for r_i, row in enumerate(rows, 1):
                yield f"Bảng {t_no} – dòng {r_i}", row
        elif child.tag == W_NS + "sdt":  # content control bao quanh nội dung
            for p in child.iter(W_NS + "p"):
                p_no += 1
                txt = _para_text(p)
                if txt.strip():
                    yield f"Đoạn {p_no}", txt


def extract_docx(data: bytes) -> ExtractResult:
    import docx  # python-docx

    warnings = []
    segs = []
    doc = docx.Document(io.BytesIO(data))
    for loc, txt in _iter_body_blocks(doc.element.body):
        segs.append({"loc": loc, "text": clean_text(txt)})

    seen_hf = set()
    for s_i, section in enumerate(doc.sections, 1):
        for label, part in (("Header", section.header), ("Footer", section.footer)):
            try:
                if part.is_linked_to_previous and s_i > 1:
                    continue
                txt = " ".join(p.text for p in part.paragraphs)
                for tbl in part.tables:
                    for row in tbl.rows:
                        txt += " " + " ".join(c.text for c in row.cells)
                txt = clean_text(txt).strip()
                if txt and txt not in seen_hf:
                    seen_hf.add(txt)
                    segs.append({"loc": f"{label} (mục {s_i})", "text": txt})
            except Exception:
                pass

    # Footnote / endnote (python-docx chưa hỗ trợ trực tiếp → đọc XML)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name, label in (("word/footnotes.xml", "Chú thích"), ("word/endnotes.xml", "Chú thích cuối")):
                if name in z.namelist():
                    from lxml import etree
                    root = etree.fromstring(z.read(name))
                    for i, fn in enumerate(root, 1):
                        txt = " ".join(_para_text(p) for p in fn.iter(W_NS + "p")).strip()
                        if txt:
                            segs.append({"loc": f"{label} {i}", "text": clean_text(txt)})
    except Exception:
        warnings.append("Không đọc được phần chú thích (footnote) – bỏ qua.")

    chars = sum(len(s["text"]) for s in segs)
    return ExtractResult(segments=segs, kind="DOCX", pages=None,
                         warnings=warnings, scanned_pages=[], chars=chars)


# --------------------------------------------------------------------------- PDF
def _join_pdf_lines(txt: str) -> str:
    """Nối các dòng bị ngắt trong PDF thành đoạn liền, giữ ranh giới đoạn (dòng trống)."""
    txt = clean_text(txt)
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    paras = re.split(r"\n\s*\n", txt)
    out = []
    for p in paras:
        p = re.sub(r"-\n(?=[A-ZĐ])", "-", p)  # NĐ-\nCP → NĐ-CP
        p = re.sub(r"\s*\n\s*", " ", p)
        p = re.sub(r"[ \t]{2,}", " ", p).strip()
        if p:
            out.append(p)
    return "\n".join(out)


def extract_pdf(data: bytes) -> ExtractResult:
    warnings, segs, scanned = [], [], []
    pages = 0
    try:
        import pymupdf  # PyMuPDF

        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise ValueError("PDF có mật khẩu – không đọc được.")
            pages = pdf.page_count
            for i, page in enumerate(pdf, 1):
                raw = page.get_text("text", sort=True) or ""
                txt = _join_pdf_lines(raw)
                if len(txt.strip()) < 15:
                    if page.get_images():
                        scanned.append(i)
                    continue
                segs.append({"loc": f"Trang {i}", "text": txt})
    except ImportError:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ValueError("PDF có mật khẩu – không đọc được.")
        pages = len(reader.pages)
        for i, page in enumerate(reader.pages, 1):
            txt = _join_pdf_lines(page.extract_text() or "")
            if len(txt.strip()) < 15:
                scanned.append(i)
                continue
            segs.append({"loc": f"Trang {i}", "text": txt})

    if pages and len(scanned) == pages:
        warnings.append("PDF dạng ảnh scan (không có lớp chữ) – bản này chưa hỗ trợ OCR, "
                        "không trích xuất được. Hãy dùng bản Word/PDF gốc.")
    elif scanned:
        shown = ", ".join(map(str, scanned[:15])) + ("…" if len(scanned) > 15 else "")
        warnings.append(f"{len(scanned)} trang chỉ có ảnh scan, không đọc được chữ (trang {shown}).")

    chars = sum(len(s["text"]) for s in segs)
    return ExtractResult(segments=segs, kind="PDF", pages=pages,
                         warnings=warnings, scanned_pages=scanned, chars=chars)


# --------------------------------------------------------------------------- chung
def extract_any(filename: str, data: bytes) -> ExtractResult:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "docx":
        return extract_docx(data)
    if ext == "pdf":
        return extract_pdf(data)
    if ext == "doc":
        raise ValueError("File Word cũ (.doc) chưa hỗ trợ – hãy lưu lại dạng .docx rồi tải lên.")
    raise ValueError(f"Định dạng .{ext} chưa hỗ trợ (chỉ nhận .docx, .pdf).")


def full_text(result: ExtractResult) -> str:
    """Ghép toàn văn kèm mốc vị trí – dùng cho AI."""
    out, last = [], None
    for s in result["segments"]:
        loc = s["loc"].split(" – ")[0]
        if loc != last:
            out.append(f"\n[{loc}]")
            last = loc
        out.append(s["text"])
    return "\n".join(out).strip()
