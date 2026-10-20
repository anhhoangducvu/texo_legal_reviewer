# -*- coding: utf-8 -*-
"""
LỚP QUY TẮC (không AI) – nhận diện văn bản pháp luật & tiêu chuẩn trong tiếng Việt.

Nhận diện được:
  • Văn bản pháp luật có số ký hiệu đầy đủ: 06/2021/NĐ-CP, 10/2021/TT-BXD, 50/2014/QH13,
    1329/QĐ-BXD, 02/VBHN-BXD, 15/CT-TTg… – kể cả khi KHÔNG có chữ "Nghị định/Thông tư" đứng
    trước (loại văn bản suy ra từ ký hiệu).
  • Dạng viết tắt thiếu ký hiệu: "Nghị định 06/2021", "NĐ 15/2021", "TT 10/2021"… → tự gộp với
    bản ký hiệu đầy đủ nếu nơi khác trong hồ sơ có ghi.
  • Luật/Bộ luật theo tên + năm: "Luật Xây dựng 2014", "Bộ luật Dân sự năm 2015".
  • Tiêu chuẩn, quy chuẩn VN: TCVN, TCVN ISO, QCVN, TCXDVN, TCXD, QCXDVN, 22TCN, TCCS…
    (4453:1995, 5574-2018, 01-1:2018/BYT, 22TCN 272-05).
  • Tiêu chuẩn nước ngoài: ISO, ASTM, BS EN, EN, DIN, ACI, AASHTO, JIS, IEC, NFPA, ASME.

Mỗi lần xuất hiện ghi lại: file, vị trí, nguyên văn, ngữ cảnh, ngày ban hành, trích yếu.
Sau đó `build_catalog` gộp thành danh mục duy nhất + gắn ghi chú kiểm tra.
"""
import re
import unicodedata
from collections import defaultdict, OrderedDict
from urllib.parse import quote_plus

# ----------------------------------------------------------------------------- nhóm
GROUP_ORDER = [
    "Luật / Bộ luật",
    "Nghị định",
    "Thông tư",
    "Quyết định",
    "Văn bản pháp quy khác",
    "Tiêu chuẩn / Quy chuẩn Việt Nam",
    "Tiêu chuẩn nước ngoài",
]
GROUP_SHORT = {
    "Luật / Bộ luật": "Luật",
    "Nghị định": "Nghị định",
    "Thông tư": "Thông tư",
    "Quyết định": "Quyết định",
    "Văn bản pháp quy khác": "VB khác",
    "Tiêu chuẩn / Quy chuẩn Việt Nam": "TCVN/QCVN",
    "Tiêu chuẩn nước ngoài": "TC nước ngoài",
}

TYPE_TO_GROUP = {
    "Luật": "Luật / Bộ luật",
    "Bộ luật": "Luật / Bộ luật",
    "Nghị định": "Nghị định",
    "Thông tư": "Thông tư",
    "Thông tư liên tịch": "Thông tư",
    "Quyết định": "Quyết định",
    "Nghị quyết": "Văn bản pháp quy khác",
    "Chỉ thị": "Văn bản pháp quy khác",
    "Văn bản hợp nhất": "Văn bản pháp quy khác",
    "Pháp lệnh": "Văn bản pháp quy khác",
    "Tiêu chuẩn Việt Nam": "Tiêu chuẩn / Quy chuẩn Việt Nam",
    "Quy chuẩn Việt Nam": "Tiêu chuẩn / Quy chuẩn Việt Nam",
    "Tiêu chuẩn ngành": "Tiêu chuẩn / Quy chuẩn Việt Nam",
    "Tiêu chuẩn cơ sở": "Tiêu chuẩn / Quy chuẩn Việt Nam",
    "Tiêu chuẩn nước ngoài": "Tiêu chuẩn nước ngoài",
}

# ----------------------------------------------------------------------------- regex
_SUFFIX = r"(?:TTLT|VBHN|UBTVQH\d{0,2}|QH\d{0,2}|N[ĐD]|TT|Q[ĐD]|NQ|CT|PL)"
RX_SYMBOL = re.compile(
    r"(?<![\d/])(?P<num>\d{1,5})\s*/\s*(?:(?P<year>(?:19|20)\d{2})\s*/\s*)?"
    r"(?P<suf>" + _SUFFIX + r"(?:\s*-\s*[A-ZĐa-zđ0-9]{1,12}){0,4})(?![A-Za-zĐđ0-9])",
    re.IGNORECASE)

_KW = r"(?:Bộ\s+luật|Luật|Nghị\s+định|Thông\s+tư\s+liên\s+tịch|Thông\s+tư|Quyết\s+định|Nghị\s+quyết|Chỉ\s+thị|Văn\s+bản\s+hợp\s+nhất|Pháp\s+lệnh)"
RX_KW_BEFORE = re.compile(r"(?P<kw>" + _KW + r")\s*(?:số\s*(?:hiệu\s*)?)?[:.]?\s*$", re.IGNORECASE)

RX_SHORT = re.compile(
    r"(?<![\w/])(?P<kw>Nghị\s+định|NĐ|Thông\s+tư|TT|Quyết\s+định|QĐ|Nghị\s+quyết|NQ)\s*(?:số\s*)?"
    r"(?P<num>\d{1,5})\s*/\s*(?P<year>(?:19|20)\d{2})(?!\s*/\s*[A-Za-zĐđ0-9])(?!\d)",
    re.IGNORECASE)

RX_LAW_NAME = re.compile(
    r"(?<![\wÀ-ỹ])(?P<kw>Bộ\s+luật|Luật)\s+(?P<name>[A-ZĐÀ-Ỹ][^\n,;:()\d/\"“”]{1,80}?)\s+"
    r"(?:năm\s+)?(?P<year>(?:19|20)\d{2})(?![\d/])")

RX_VN_STD = re.compile(
    r"(?<![A-Za-z0-9])(?P<pre>TCVN\s*ISO(?:\s*/\s*IEC)?|TCVN|QCVN|TCXDVN|TCXD|QCXDVN|QCXD|TCCS|\d{2}\s*TCN|TCN)"
    r"\s*(?P<num>\d{1,5}(?:[.\-]\d{1,4}(?=\s*[.\-:]))*)"
    r"(?:\s*(?P<sep>[:\-])\s*(?P<year>(?:19|20)\d{2}|\d{2})(?!\d))?"
    r"(?:\s*/\s*(?P<agency>B[A-ZĐ]{1,8}|[A-ZĐ]{2,8}))?(?![A-Za-z0-9])")

RX_FOREIGN = [
    ("ISO", re.compile(r"(?<![A-Za-z/])ISO(?:\s*/\s*IEC)?\s*\d{3,5}(?:-\d+)*(?:\s*:\s*(?:19|20)\d{2})?")),
    ("ASTM", re.compile(r"(?<![A-Za-z])ASTM\s*[A-G]\s?\d{1,4}(?:\.\d+)?M?(?:\s*/\s*[A-G]?\s?\d{1,4}M?)?(?:\s*-\s*\d{2,4}[a-z]?\d?)?")),
    ("EN", re.compile(r"(?<![A-Za-z])(?:BS\s+EN|DIN\s+EN|NF\s+EN|EN)\s*\d{3,5}(?:-\d+)*(?:\s*\+\s*A\d)?(?:\s*:\s*(?:19|20)\d{2})?")),
    ("BS", re.compile(r"(?<![A-Za-z])BS\s*\d{3,5}(?:-\d+)*(?:\s*:\s*(?:19|20)\d{2})?")),
    ("DIN", re.compile(r"(?<![A-Za-z])DIN\s*\d{3,5}(?:-\d+)*")),
    ("ACI", re.compile(r"(?<![A-Za-z])ACI\s*\d{3}(?:\.\d)?R?(?:\s*-\s*\d{2})?")),
    ("AASHTO", re.compile(r"(?<![A-Za-z])AASHTO\s*(?:LRFD|[MT]\s?\d{1,3})")),
    ("JIS", re.compile(r"(?<![A-Za-z])JIS\s*[A-Z]\s?\d{4}(?:\s*:\s*(?:19|20)\d{2})?")),
    ("IEC", re.compile(r"(?<![A-Za-z/])IEC\s*\d{4,5}(?:-\d+)*(?:\s*:\s*(?:19|20)\d{2})?")),
    ("NFPA", re.compile(r"(?<![A-Za-z])NFPA\s*\d{2,4}")),
    ("ASME", re.compile(r"(?<![A-Za-z])ASME\s*[A-Z]{0,2}\s?\d{1,3}(?:\.\d+)+")),
    ("Eurocode", re.compile(r"(?<![A-Za-z])Eurocode\s*\d")),
]

RX_DATE_AFTER = re.compile(
    r"^\s*[,(]?\s*(?:được\s+)?(?:ban\s+hành\s+|ký\s+)?ngày\s*(?P<d>\d{1,2})\s*(?:/|-|\.|\s+tháng\s+)\s*"
    r"(?P<m>\d{1,2})\s*(?:/|-|\.|\s+năm\s+)\s*(?P<y>(?:19|20)\d{2})", re.IGNORECASE)

RX_TITLE_STOP = re.compile(r"[;\n]|\.\s|\.$|,?\s(?:và\s+)?(?=(?:Nghị định|Thông tư|Quyết định|TCVN|QCVN)\s+(?:số\s+)?\d)")


def _norm_space(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _fold(s):
    """Bỏ dấu + chữ thường – để so khớp tên luật."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return _norm_space(s.replace("đ", "d").replace("Đ", "D").lower())


def norm_suffix(suf):
    suf = re.sub(r"\s*-\s*", "-", suf.strip()).upper()
    parts = suf.split("-")
    head = parts[0]
    head = {"ND": "NĐ", "QD": "QĐ"}.get(head, head)
    parts[0] = head
    parts = ["TTg" if x == "TTG" else x for x in parts]
    return "-".join(parts)


def type_from_suffix(suf):
    head = suf.split("-")[0]
    if head == "TTLT":
        return "Thông tư liên tịch"
    if head == "VBHN":
        return "Văn bản hợp nhất"
    if head.startswith("UBTVQH") or head == "PL":
        return "Pháp lệnh"
    if head.startswith("QH"):
        return "Luật"
    return {"NĐ": "Nghị định", "TT": "Thông tư", "QĐ": "Quyết định",
            "NQ": "Nghị quyết", "CT": "Chỉ thị"}.get(head, "Văn bản pháp quy khác")


KW_TO_TYPE = {"bộ luật": "Bộ luật", "luật": "Luật", "nghị định": "Nghị định", "nđ": "Nghị định",
              "thông tư liên tịch": "Thông tư liên tịch", "thông tư": "Thông tư", "tt": "Thông tư",
              "quyết định": "Quyết định", "qđ": "Quyết định", "nghị quyết": "Nghị quyết",
              "nq": "Nghị quyết", "chỉ thị": "Chỉ thị", "văn bản hợp nhất": "Văn bản hợp nhất",
              "pháp lệnh": "Pháp lệnh"}


def _kw_type(kw):
    return KW_TO_TYPE.get(_norm_space(kw).lower())


def search_link(display, group):
    is_std = group in ("Tiêu chuẩn / Quy chuẩn Việt Nam", "Tiêu chuẩn nước ngoài")
    if group == "Tiêu chuẩn nước ngoài":
        q = f"\"{display}\" standard status"
    else:
        domain = "tieuchuan.vsqi.gov.vn" if is_std else "thuvienphapluat.vn"
        q = f"\"{display}\" {domain} tình trạng hiệu lực"
    return "https://www.google.com/search?q=" + quote_plus(q)


def _context(text, a, b, pad=90):
    s = max(0, a - pad)
    e = min(len(text), b + pad)
    return ("…" if s > 0 else "") + _norm_space(text[s:e]) + ("…" if e < len(text) else "")


def _date_after(text, pos):
    m = RX_DATE_AFTER.match(text[pos:pos + 70])
    if not m:
        return "", pos
    d, mo, y = int(m.group("d")), int(m.group("m")), m.group("y")
    if not (1 <= d <= 31 and 1 <= mo <= 12):
        return "", pos
    return f"{d:02d}/{mo:02d}/{y}", pos + m.end()


def _title_after(text, pos):
    tail = text[pos:pos + 260]
    if re.match(r"^\s*[,;]", tail):
        return ""
    tail = re.sub(r"^\s*[,:\-–)]*\s*", "", tail)
    m = RX_TITLE_STOP.search(tail)
    if m:
        tail = tail[:m.start()]
    tail = _norm_space(tail).strip(" ,:-")
    tail = re.sub(r"^(?:của\s+)?(?:Chính\s+phủ|Quốc\s+hội|Thủ\s+tướng(?:\s+Chính\s+phủ)?)\s*", "", tail, flags=re.IGNORECASE)
    tail = re.sub(r"^(?:về|quy\s+định\s+về)\s*:?\s*", "", tail, flags=re.IGNORECASE).strip(" ,:-")
    if tail.startswith("(") or re.match(r"^(?:và|hoặc|,)\b", tail):
        return ""
    if tail and not tail.lower().startswith("của "):
        tail = tail[0].upper() + tail[1:]
    if len(tail) < 12 or len(tail.split()) < 3:
        return ""
    if len(tail) > 220:
        tail = tail[:220].rsplit(" ", 1)[0] + "…"
    return tail


def _law_name_before(text, pos):
    window = text[max(0, pos - 180):pos]
    idx = max(window.rfind("Luật "), window.rfind("luật "))
    if idx == -1:
        return ""
    is_bo = window[max(0, idx - 4):idx].lower().endswith("bộ ")
    name = window[idx + 5:]
    name = "".join(ch for ch in name if not unicodedata.category(ch).startswith("S"))
    name = re.sub(r"\s{2,}", " ", name)
    if ";" in name or RX_SYMBOL.search(name):
        return ""
    name = re.split(r"\s+(?:của|ngày|được|đã)\s|[;\n]", name)[0]
    name = re.sub(r"[\s,]*(?:số\s*(?:hiệu)?)?\s*[:.]?\s*$", "", name, flags=re.IGNORECASE).strip(" ,")
    if not name or len(name.split()) > 14 or not re.match(r"[A-ZĐÀ-Ỹa-zđà-ỹ]", name):
        return ""
    if name.lower().startswith("số"):
        return ""
    return ("Bộ luật " if is_bo else "Luật ") + name


# ----------------------------------------------------------------------------- quét
def scan_segment(text, loc, filename):
    """Trả danh sách lần xuất hiện trong 1 đoạn."""
    occ = []
    taken = []  # các khoảng ký tự đã nhận

    def overlap(a, b):
        return any(a < y and b > x for x, y in taken)

    # 1) Số ký hiệu đầy đủ
    for m in RX_SYMBOL.finditer(text):
        num, year, suf = m.group("num"), m.group("year"), norm_suffix(m.group("suf"))
        head = suf.split("-")[0]
        # QH/NĐ/TT bắt buộc có năm; QĐ/CT/VBHN có thể không có năm
        if head in ("NĐ", "TT", "TTLT", "NQ") and not year and not suf.startswith("NQ-"):
            continue
        if head.startswith("QH") and not year:
            continue
        symbol = f"{int(num):02d}/{year}/{suf}" if year else f"{int(num):02d}/{suf}"
        before = text[max(0, m.start() - 40):m.start()]
        kwm = RX_KW_BEFORE.search(before)
        vtype = type_from_suffix(suf)
        start = m.start()
        if kwm:
            kt = _kw_type(kwm.group("kw"))
            if kt == "Bộ luật" and vtype == "Luật":
                vtype = "Bộ luật"
            start = m.start() - (len(before) - kwm.start())
        date, after = _date_after(text, m.end())
        name = _law_name_before(text, m.start()) if vtype in ("Luật", "Bộ luật") else ""
        title = _title_after(text, after)
        occ.append(dict(key="SYM|" + symbol.upper(), kind="symbol", vtype=vtype, symbol=symbol,
                        num=str(int(num)), year=year or (date[-4:] if date else ""),
                        name=name, date=date, title=title, raw=_norm_space(text[start:m.end()]),
                        context=_context(text, start, m.end()), file=filename, loc=loc, source="Quy tắc"))
        taken.append((start, m.end()))

    # 2) Dạng rút gọn thiếu ký hiệu
    for m in RX_SHORT.finditer(text):
        if overlap(m.start(), m.end()):
            continue
        vtype = _kw_type(m.group("kw")) or "Văn bản pháp quy khác"
        num, year = str(int(m.group("num"))), m.group("year")
        date, after = _date_after(text, m.end())
        occ.append(dict(key=f"SHORT|{vtype}|{num}|{year}", kind="short", vtype=vtype,
                        symbol=f"{int(num):02d}/{year}", num=num, year=year, name="", date=date,
                        title=_title_after(text, after), raw=_norm_space(m.group(0)),
                        context=_context(text, m.start(), m.end()), file=filename, loc=loc, source="Quy tắc"))
        taken.append((m.start(), m.end()))

    # 3) Luật theo tên + năm
    for m in RX_LAW_NAME.finditer(text):
        if overlap(m.start(), m.end()):
            continue
        name = _norm_space(m.group("name"))
        name = re.sub(r"\s+(?:số|năm|ban hành|sửa đổi.*)$", "", name, flags=re.IGNORECASE)
        if len(name.split()) > 10:
            continue
        kw = "Bộ luật" if m.group("kw").lower().startswith("bộ") else "Luật"
        full = f"{kw} {name}"
        occ.append(dict(key=f"LAW|{_fold(full)}|{m.group('year')}", kind="lawname", vtype=kw,
                        symbol="", num="", year=m.group("year"), name=full, date="", title="",
                        raw=_norm_space(m.group(0)), context=_context(text, m.start(), m.end()),
                        file=filename, loc=loc, source="Quy tắc"))
        taken.append((m.start(), m.end()))

    # 4) Tiêu chuẩn / quy chuẩn Việt Nam
    for m in RX_VN_STD.finditer(text):
        if overlap(m.start(), m.end()):
            continue
        pre = re.sub(r"\s+", " ", m.group("pre")).upper().replace(" / ", "/")
        pre = re.sub(r"^(\d{2})\s*TCN$", r"\1TCN", pre)
        pre = re.sub(r"TCVN\s*ISO", "TCVN ISO", pre)
        num = m.group("num")
        year = m.group("year") or ""
        if len(year) == 2:
            year = ("19" if int(year) >= 50 else "20") + year
        agency = (m.group("agency") or "").upper()
        if pre.startswith("QCVN") or pre.startswith("QCXD"):
            vtype = "Quy chuẩn Việt Nam"
        elif "TCN" in pre and not pre.startswith("TCVN"):
            vtype = "Tiêu chuẩn ngành"
        elif pre == "TCCS":
            vtype = "Tiêu chuẩn cơ sở"
        else:
            vtype = "Tiêu chuẩn Việt Nam"
        code = f"{pre} {num}" + (f":{year}" if year else "") + (f"/{agency}" if agency else "")
        base = f"{pre} {num}"
        occ.append(dict(key="STD|" + code.upper(), kind="std", vtype=vtype, symbol=code, num=num,
                        year=year, base=base.upper(), name="", date="",
                        title="",
                        raw=_norm_space(m.group(0)), context=_context(text, m.start(), m.end()),
                        file=filename, loc=loc, source="Quy tắc"))
        taken.append((m.start(), m.end()))

    # 5) Tiêu chuẩn nước ngoài
    for fam, rx in RX_FOREIGN:
        for m in rx.finditer(text):
            if overlap(m.start(), m.end()):
                continue
            code = re.sub(r"\s*:\s*", ":", _norm_space(m.group(0)))
            code = re.sub(r"\s*-\s*", "-", code)
            ym = re.search(r":((?:19|20)\d{2})$", code)
            base = re.sub(r":\d{4}$", "", code).upper()
            occ.append(dict(key="FSTD|" + code.upper().replace(" ", ""), kind="fstd",
                            vtype="Tiêu chuẩn nước ngoài", symbol=code, num="", base=base.replace(" ", ""),
                            year=ym.group(1) if ym else "", name="", date="", title="",
                            raw=code, context=_context(text, m.start(), m.end()), file=filename,
                            loc=loc, source="Quy tắc"))
            taken.append((m.start(), m.end()))
    return occ


def scan_document(segments, filename):
    out = []
    for seg in segments:
        out.extend(scan_segment(seg["text"], seg["loc"], filename))
    return out


# ----------------------------------------------------------------------------- gộp danh mục
def _display(d):
    if d["kind"] in ("std", "fstd", "ai"):
        return d["symbol"]
    if d["kind"] == "lawname":
        return f"{d['name']} ({d['year']})" if d["year"] else d["name"]
    if d["kind"] == "short":
        return f"{d['vtype']} {d['symbol']}"
    if d["vtype"] in ("Luật", "Bộ luật") and d.get("name"):
        return f"{d['name']} số {d['symbol']}"
    return f"{d['vtype']} {d['symbol']}"


def build_catalog(occurrences):
    """Gộp các lần xuất hiện thành danh mục văn bản duy nhất (OrderedDict key → mục)."""
    # 1. ánh xạ dạng rút gọn → ký hiệu đầy đủ; tên luật → ký hiệu
    full_by_short = {}
    law_by_name = {}
    for o in occurrences:
        if o["kind"] == "symbol" and o["year"]:
            full_by_short.setdefault((o["vtype"].replace(" liên tịch", ""), o["num"], o["year"]), o["key"])
        if o["kind"] == "symbol" and o.get("name"):
            law_by_name.setdefault((_fold(o["name"]), o["year"]), o["key"])
            # "Luật Xây dựng số 50/2014" -> cũng khớp với "Luật Xây dựng 2014"
    for o in occurrences:
        if o["kind"] == "short":
            k = full_by_short.get((o["vtype"].replace(" liên tịch", ""), o["num"], o["year"]))
            if k:
                o["merged_from"] = o["raw"]
                o["key"] = k
        elif o["kind"] == "lawname":
            k = law_by_name.get((_fold(o["name"]), o["year"]))
            if k:
                o["merged_from"] = o["raw"]
                o["key"] = k

    cat = OrderedDict()
    for o in occurrences:
        k = o["key"]
        if k not in cat:
            cat[k] = dict(key=k, kind=o["kind"], vtype=o["vtype"], symbol=o["symbol"], name=o.get("name", ""),
                          year=o.get("year", ""), base=o.get("base", ""), dates=[], titles=[],
                          files=OrderedDict(), occ=[], sources=set(), variants=set(), flags=[],
                          ai_note="", ai_status="", ai_replaced_by="", ai_fullname="")
        c = cat[k]
        # bản đầy đủ thắng bản rút gọn
        if c["kind"] in ("short", "lawname") and o["kind"] == "symbol":
            c.update(kind="symbol", vtype=o["vtype"], symbol=o["symbol"], year=o["year"])
        if o.get("name") and not c["name"]:
            c["name"] = o["name"]
        if o.get("date"):
            c["dates"].append(o["date"])
        if o.get("title"):
            c["titles"].append(o["title"])
        c["files"][o["file"]] = c["files"].get(o["file"], 0) + 1
        c["occ"].append(o)
        c["sources"].add(o["source"])
        c["variants"].add(o["raw"])

    # 2. thông tin hiển thị + ghi chú kiểm tra
    bases = defaultdict(set)
    for c in cat.values():
        if c["kind"] in ("std", "fstd") and c["base"]:
            bases[c["base"]].add(c["symbol"])

    for c in cat.values():
        c["group"] = TYPE_TO_GROUP.get(c["vtype"], "Văn bản pháp quy khác")
        c["display"] = _display(c)
        dates = list(OrderedDict.fromkeys(c["dates"]))
        c["date"] = dates[0] if dates else ""
        titles = sorted(set(c["titles"]), key=len, reverse=True)
        c["title"] = titles[0] if titles else ""
        if c["kind"] == "symbol" and c["vtype"] in ("Luật", "Bộ luật") and c["name"] and c["title"] == c["name"]:
            c["title"] = ""
        flags = []
        if c["kind"] == "short":
            flags.append("Thiếu số ký hiệu đầy đủ (vd …/NĐ-CP, …/TT-BXD)")
        if c["kind"] == "lawname":
            flags.append("Chỉ ghi tên + năm, chưa ghi số hiệu Luật")
        if c["kind"] in ("std", "fstd") and not c["year"] and c["vtype"] != "Tiêu chuẩn nước ngoài":
            flags.append("Không ghi năm ban hành tiêu chuẩn")
        if c["kind"] in ("std", "fstd") and len(bases.get(c["base"], ())) > 1:
            others = sorted(bases[c["base"]] - {c["symbol"]})
            flags.append("Hồ sơ trích nhiều phiên bản: " + ", ".join(others))
        if len(dates) > 1:
            flags.append("Ngày ban hành ghi không thống nhất: " + "; ".join(dates))
        if c["kind"] == "symbol" and c["year"] and c["date"] and c["date"][-4:] != c["year"] \
                and "/" in c["symbol"] and c["symbol"].split("/")[1] == c["year"]:
            flags.append(f"Năm trong số hiệu ({c['year']}) khác năm ngày ban hành ({c['date']}) – kiểm tra lại")
        if c["sources"] == {"AI"}:
            flags.append("🤖 Do AI phát hiện (quy tắc bỏ sót)")
            if not any(o.get("ai_verified") for o in c["occ"]):
                flags.append("⚠ Không thấy nguyên văn trong tài liệu – kiểm tra kỹ, có thể AI suy diễn")
        c["flags"] = flags
        c["link"] = search_link(c["symbol"] if c["kind"] in ("symbol", "std", "fstd", "ai") else c["display"], c["group"])
        c["n_occ"] = len(c["occ"])
        c["n_files"] = len(c["files"])
    return cat


def sort_key(c):
    g = GROUP_ORDER.index(c["group"]) if c["group"] in GROUP_ORDER else 99
    if c["group"] in ("Tiêu chuẩn / Quy chuẩn Việt Nam", "Tiêu chuẩn nước ngoài"):
        return (g, 0, c["display"])
    y = c.get("year") or "0000"
    return (g, -int(y) if y.isdigit() else 0, c["display"])
