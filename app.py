import streamlit as st
import os
import pandas as pd
from pandas import DataFrame
from core.audit_engine import extract_legal_references, audit_legal_status

# --- CONFIG ---
st.set_page_config(page_title="TEXO Legal Reviewer", page_icon="🏛️", layout="wide")

# --- STYLE PREMIUM ---
st.markdown("""
<style>
    /* --- TỐI ƯU HÓA CSS CHO CẢ 2 CHẾ ĐỘ --- */
    h1, h2, h3, h4, .main-header { color: #FFD700 !important; }
    
    .main-header { 
        font-weight: 800; 
        font-size: 32px; 
        text-align: center; 
        border-bottom: 2px solid #FFD700; 
        padding-bottom: 10px; 
        margin-bottom: 20px; 
    }
    
    .stButton>button { 
        background: linear-gradient(135deg, #152A4A 0%, #1e3a8a 100%) !important; 
        color: #FFD700 !important; 
        border: 1px solid #FFD700 !important; 
        border-radius: 12px; 
        font-weight: bold; 
        height: 3.5em; 
        width: 100%; 
    }
    .stButton>button:hover { 
        background: #FFD700 !important; 
        color: #0A1931 !important; 
        transform: scale(1.02); 
        transition: 0.2s; 
    }
    
    .footer { text-align: center; color: #888; font-size: 12px; margin-top: 50px; border-top: 1px solid rgba(255, 215, 0, 0.1); padding-top: 20px; }
</style>
""", unsafe_allow_html=True)

# --- AUTH ---
def check_password():
    if "authenticated" not in st.session_state: st.session_state.authenticated = False
    if st.session_state.authenticated: return True
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #FFD700;'>🏦 TEXO LEGAL REVIEWER</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Mật khẩu truy cập:", type="password")
        if st.button("XÁC THỰC"):
            if pwd == "texo2026":
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("❌ Truy cập không hợp lệ.")
    return False

if not check_password(): st.stop()

# --- MAIN ---
st.markdown("<div class='main-header'>🏛️ RÀ SOÁT VĂN BẢN PHÁP LUẬT & TIÊU CHUẨN</div>", unsafe_allow_html=True)

# --- UPLOAD SECTION ---
st.markdown("### 📥 Tải hồ sơ rà soát")
doc_file = st.file_uploader("Tải hồ sơ (.docx) để AI bóc tách căn cứ pháp lý", type=["docx"])

st.markdown("---")

# --- ANALYSIS SECTION ---
if doc_file:
    st.info(f"📁 Đã nhận hồ sơ: **{doc_file.name}**")
    if st.button("🚀 BẮT ĐẦU RÀ SOÁT PHÁP LÝ"):
        with st.spinner("AI đang bóc tách căn cứ pháp lý..."):
            try:
                ta = f"t_{doc_file.name}"
                with open(ta, "wb") as f:
                    f.write(doc_file.getbuffer())
                
                refs = extract_legal_references(ta)
                if refs:
                    df = DataFrame(audit_legal_status(refs))
                    st.success(f"✅ Đã tìm thấy {len(df)} văn bản pháp quy.")
                    
                    # --- TỔNG HỢP (METRICS) ---
                    st.markdown("### 📊 Tổng hợp Căn cứ Pháp lý")
                    
                    std_rx = "TCVN|QCVN|Tiêu chuẩn|Quy chuẩn|ISO|ASTM|BS|EN|JIS|ASME|QCXDVN|TCXDVN|QĐ"
                    groups = [
                        ("Luật", "Luật"), 
                        ("Nghị định", "Nghị định"), 
                        ("Thông tư", "Thông tư"), 
                        (std_rx, "Quy chuẩn/Tiêu chuẩn")
                    ]
                    
                    m_cols = st.columns(len(groups))
                    collected_indices = []
                    group_data = []

                    for i, (key, label) in enumerate(groups):
                        sub = df[df['symbol'].str.contains(key, case=False, na=False, regex=True)]
                        m_cols[i].metric(label, f"{len(sub)} VB")
                        collected_indices.extend(sub.index)
                        group_data.append((label, sub))
                    
                    # --- DOWNLOAD SECTION ---
                    import io
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Base_Legal_Audit')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 TẢI BÁO CÁO RÀ SOÁT (EXCEL)",
                        data=excel_data,
                        file_name=f"Bao_cao_Phap_ly_{doc_file.name.replace('.docx', '')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.markdown("---")
                    st.markdown("### 📜 Chi tiết Danh mục")

                    for label, sub in group_data:
                        if not sub.empty:
                            with st.expander(f"📂 {label.upper()} ({len(sub)})", expanded=False):
                                st.dataframe(sub[["symbol", "link"]], 
                                           column_config={"link": st.column_config.LinkColumn("Tra cứu hiệu lực")}, 
                                           hide_index=True, use_container_width=True)
                    
                    other_df = df.drop(index=list(set(collected_indices)))
                    if not other_df.empty:
                        with st.expander(f"📂 NHÓM KHÁC ({len(other_df)})", expanded=False):
                            st.dataframe(other_df[["symbol", "link"]], 
                                       column_config={"link": st.column_config.LinkColumn("Tra cứu hiệu lực")}, 
                                       hide_index=True, use_container_width=True)
                else:
                    st.warning("🧐 Không tìm thấy căn cứ pháp lý nào trong tài liệu.")
                
                if os.path.exists(ta): os.remove(ta)
            except Exception as e:
                st.error(f"❌ Lỗi rà soát: {e}")
else:
    st.markdown("<div style='height: 150px; border: 2px dashed #94a3b8; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #64748b; font-weight: 500;'>Vui lòng tải lên hồ sơ (.docx) để bắt đầu phân tích</div>", unsafe_allow_html=True)

st.markdown("<div class='footer'>TEXO Engineering Department | Legal Audit Intelligence | Hoàng Đức Vũ</div>", unsafe_allow_html=True)
