import streamlit as st
import base64

st.set_page_config(page_title="KEP Portal Home", page_icon="🏠", layout="wide")
KEP_BLUE = "#004B87"

# --- CUSTOM BLUE HEADER ---
def render_header():
    try:
        with open("logo.svg", "rb") as image_file:
            base64_svg = base64.b64encode(image_file.read()).decode("utf-8")
        header_html = f"""
        <div style="background-color: {KEP_BLUE}; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <img src="data:image/svg+xml;base64,{base64_svg}" alt="KEP Print Group Logo" style="max-height: 70px;">
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)
    except FileNotFoundError:
        st.markdown(f"""
        <div style="background-color: {KEP_BLUE}; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h1 style="color: white; margin: 0; font-family: Arial, sans-serif;">KEP Print Group</h1>
        </div>
        """, unsafe_allow_html=True)

render_header()

# --- HOMEPAGE DASHBOARD ---
st.title("Welcome to the KEP CSR Portal")
st.write("Use the sidebar on the left to navigate between different production tools.")
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.info("📦 **Pick Lists & Dispatch**\n\nGenerate PDFs and DHL CSVs for M&P, Tim Hortons, and Craft Union.")
with col2:
    st.warning("⚙️ **Collation Machine Prep**\n\nFormat raw mailing lists for the print room. *(Mockup)*")
with col3:
    st.success("📊 **Stock & Inventory**\n\nReview low stock and generate Tropicana POs. *(Mockup)*")
