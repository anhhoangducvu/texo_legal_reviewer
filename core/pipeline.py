# -*- coding: utf-8 -*-
"""Điều phối: đọc nhiều file → quét quy tắc → (tuỳ chọn) AI → danh mục + bảng hiển thị."""
from collections import OrderedDict

import pandas as pd

from .extractors import extract_any, full_text
from .rules import scan_document, build_catalog, sort_key, GROUP_ORDER, GROUP_SHORT
from . import ai_review


def read_files(files):
    """files: list (tên, bytes). Trả list kết quả từng file."""
    out = []
    for name, data in files:
        item = dict(name=name, size=len(data), kind="", pages=None, warnings=[], error="",
                    segments=[], occ=[], text="")
        try:
            ex = extract_any(name, data)
            item.update(kind=ex["kind"], pages=ex["pages"], warnings=list(ex["warnings"]),
                        segments=ex["segments"])
            item["text"] = full_text(ex)
            item["occ"] = scan_document(ex["segments"], name)
            if not item["occ"] and ex["chars"] > 0:
                item["warnings"].append("Không phát hiện căn cứ pháp lý/tiêu chuẩn nào theo quy tắc.")
        except Exception as e:  # noqa
            item["error"] = str(e)[:300]
        out.append(item)
    return out


def run_ai_find(cfg, file_items, today, progress=None):
    warns = []
    for n, it in enumerate(file_items, 1):
        if it["error"] or not it["text"]:
            continue
        if progress:
            progress(n, len(file_items), it["name"])
        rule_cat = build_catalog([dict(o) for o in it["occ"]])
        known = [c["display"] for c in rule_cat.values()]
        ai_occ, w = ai_review.find_missing(cfg, it["name"], it["text"], known, today)
        warns += w
        rule_keys = {o["key"] for o in it["occ"]} | set(rule_cat.keys())
        new = [o for o in ai_occ if o["key"] not in rule_keys]
        # bỏ trùng trong chính kết quả AI
        seen = set()
        for o in new:
            if o["key"] in seen:
                continue
            seen.add(o["key"])
            it["occ"].append(o)
    return warns


def make_catalog(file_items):
    occ = []
    for it in file_items:
        occ.extend(it["occ"])
    cat = build_catalog(occ)
    items = sorted(cat.values(), key=sort_key)
    for i, c in enumerate(items, 1):
        c["stt"] = i
    return items


def file_summary(file_items, items):
    rows = []
    for it in file_items:
        counts = OrderedDict((g, 0) for g in GROUP_ORDER)
        n = 0
        for c in items:
            if it["name"] in c["files"]:
                counts[c["group"]] += 1
                n += 1
        warn = "; ".join(([f"LỖI: {it['error']}"] if it["error"] else []) + it["warnings"])
        row = {"Tên file": it["name"], "Định dạng": it["kind"] or "-",
               "Số trang": str(it["pages"]) if it["pages"] else "–", "Tổng số văn bản": n}
        for g in GROUP_ORDER:
            row[GROUP_SHORT[g]] = counts[g]
        row["Cảnh báo"] = warn
        rows.append(row)
    return pd.DataFrame(rows)


def catalog_df(items, with_ai=False):
    rows = []
    for c in items:
        r = OrderedDict()
        r["STT"] = c["stt"]
        r["Số hiệu / Mã hiệu"] = c["display"]
        r["Tra cứu hiệu lực"] = c["link"]
        r["Nhóm"] = c["group"]
        r["Loại"] = c["vtype"]
        r["Tên – trích yếu (theo hồ sơ)"] = c["title"]
        r["Ngày ban hành"] = c["date"]
        r["Số file"] = c["n_files"]
        r["Số lần trích"] = c["n_occ"]
        r["File trích dẫn"] = "; ".join(f"{f} ({n})" for f, n in c["files"].items())
        r["Ghi chú kiểm tra"] = "\n".join(c["flags"])
        r["Nguồn"] = " + ".join(sorted(c["sources"], key=lambda s: s != "Quy tắc"))
        if with_ai:
            st = c.get("ai_status", "")
            r["Hiệu lực (AI)"] = (ai_review.STATUS_ICON.get(st, "") + " " + st).strip()
            r["Số hiệu chuẩn (AI)"] = c.get("ai_fullsymbol", "")
            r["Tên đầy đủ (AI)"] = c.get("ai_fullname", "")
            r["VB thay thế/sửa đổi (AI)"] = c.get("ai_replaced_by", "")
            note = c.get("ai_note", "")
            if c.get("ai_suspect"):
                note = ("🚩 AI nghi ngờ ghi sai/không phải văn bản. " + note).strip()
            r["Nhận xét AI"] = note
        rows.append(r)
    return pd.DataFrame(rows)


def matrix_df(items, file_items):
    names = [it["name"] for it in file_items if not it["error"]]
    rows = []
    for c in items:
        r = OrderedDict([("STT", c["stt"]), ("Số hiệu / Mã hiệu", c["display"]),
                         ("Tra cứu hiệu lực", c["link"]), ("Nhóm", GROUP_SHORT.get(c["group"], c["group"]))])
        for nm in names:
            r[nm] = c["files"].get(nm, 0) or None
        r["Tổng"] = c["n_occ"]
        rows.append(r)
    df = pd.DataFrame(rows)
    for nm in names:
        if nm in df.columns:
            df[nm] = df[nm].astype("Int64")
    return df


def detail_df(items):
    rows = []
    for c in items:
        for o in c["occ"]:
            rows.append(OrderedDict([
                ("Văn bản", c["display"]), ("Tra cứu hiệu lực", c["link"]),
                ("File", o["file"]), ("Vị trí", o["loc"]),
                ("Nhóm", GROUP_SHORT.get(c["group"], c["group"])), ("Nguyên văn", o["raw"]),
                ("Ngữ cảnh", o.get("context", "")),
                ("Nguồn", o["source"] + ("" if o["source"] != "AI" else
                                         (" ✓ có nguyên văn" if o.get("ai_verified") else " ⚠ chưa đối chiếu được"))),
            ]))
    df = pd.DataFrame(rows)
    if not df.empty:
        df.insert(0, "STT", range(1, len(df) + 1))
    return df
