# -*- coding: utf-8 -*-
"""Giao diện dùng chung theo bộ app Phòng Kỹ thuật TEXO (Đề cương, Khối lượng, Hồ sơ chất lượng…):
màn hình đăng nhập gọn (logo, tên app, mật khẩu), đầu trang logo + tiêu đề, ô KPI, khung kết luận."""
import base64
import hmac
import os

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOGO = os.path.join(ROOT, "assets", "logo_texo.png")
DEFAULT_PASSWORD = "texo2026"

CSS = """
<style>
/* Chừa chỗ cho thanh công cụ Streamlit, không che tiêu đề / logo */
header[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 3.6rem !important; max-width: 1250px;}
.texo-head {display:flex; align-items:center; gap:16px; border-bottom:3px solid #2E5496;
  padding-bottom:8px; margin-bottom:14px;}
.texo-head img {height:42px; width:auto;}
.texo-head .t1 {font-size:1.45rem; font-weight:700; color:#0C0150; line-height:1.2;}
.texo-head .t2 {font-size:.9rem; color:#595959;}
.kpi {border-top:4px solid #2E5496; background:#EAF0F7; padding:10px 12px; border-radius:4px;
  text-align:center; margin-bottom:10px;}
.kpi .v {font-size:1.9rem; font-weight:700; line-height:1.2;}
.kpi .l {font-weight:600; color:#1F3864;} .kpi .s {font-size:.8rem; color:#595959;}
.ket-luan {border-left:6px solid; padding:10px 14px; border-radius:4px; margin:8px 0 14px 0; color:#1a1a1a;}
.ai-badge {display:inline-block; padding:3px 10px; border-radius:999px; font-size:.82rem; font-weight:600;}
</style>
"""
COLORS = {"red": ("#C00000", "#FDE4E1"), "orange": ("#C45911", "#FFF1DE"), "green": ("#2E7D32", "#E4F3E6"),
          "blue": ("#2E5496", "#EAF0F7"), "grey": ("#3B4656", "#ECEFF4")}


def _password():
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD", DEFAULT_PASSWORD)


def _btn(container, label, **kw):
    """Nút rộng hết khung – chạy được cả Streamlit cũ (use_container_width) lẫn mới (width='stretch')."""
    try:
        return container(label, width="stretch", **kw)
    except TypeError:
        return container(label, use_container_width=True, **kw)


def setup(title, icon="⚖️"):
    st.set_page_config(page_title=title, page_icon=icon, layout="wide",
                       initial_sidebar_state="expanded" if st.session_state.get("_ok") else "collapsed")


def gate(title):
    """Màn hình đăng nhập: logo, tên app, mật khẩu. Chưa đăng nhập thì không hiện thanh bên."""
    if st.session_state.get("_ok"):
        return True
    st.markdown("<style>header[data-testid='stHeader']{background:transparent;}"
                ".block-container{padding-top:4rem !important;}"
                "section[data-testid='stSidebar']{display:none;}</style>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        if os.path.exists(LOGO):
            st.image(LOGO, width=170)
        st.markdown(f"## {title}")
        st.caption("Phòng Kỹ thuật · Công ty CP TEXO Tư vấn và Đầu tư")
        with st.form("login"):
            pw = st.text_input("Mật khẩu", type="password")
            ok = _btn(st.form_submit_button, "Đăng nhập", type="primary")
            if ok:
                if hmac.compare_digest(pw, _password()):
                    st.session_state["_ok"] = True
                    st.rerun()
                else:
                    st.error("Mật khẩu chưa đúng.")
    st.stop()


def logout_button():
    if _btn(st.button, "Đăng xuất"):
        st.session_state.clear()
        st.rerun()


def header(title, subtitle):
    st.markdown(CSS, unsafe_allow_html=True)
    logo = ""
    if os.path.exists(LOGO):
        with open(LOGO, "rb") as f:
            logo = f'<img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}"/>'
    st.markdown(f'<div class="texo-head">{logo}<div><div class="t1">{title}</div>'
                f'<div class="t2">{subtitle}</div></div></div>', unsafe_allow_html=True)


def kpi(col, value, label, sub="", color="blue"):
    fg, bg = COLORS.get(color, COLORS["blue"])
    col.markdown(f'<div class="kpi" style="border-top-color:{fg}; background:{bg}">'
                 f'<div class="v" style="color:{fg}">{value}</div>'
                 f'<div class="l">{label}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def callout(text, color="blue"):
    fg, bg = COLORS.get(color, COLORS["blue"])
    st.markdown(f'<div class="ket-luan" style="border-color:{fg}; background:{bg}">{text}</div>',
                unsafe_allow_html=True)


def badge(text, color="grey"):
    fg, bg = COLORS.get(color, COLORS["grey"])
    st.markdown(f'<span class="ai-badge" style="color:{fg}; background:{bg}">● {text}</span>',
                unsafe_allow_html=True)
