import streamlit as st
import pandas as pd
from fpdf import FPDF
import io

st.set_page_config(page_title="Label Maker", page_icon="🏷️", layout="wide")

# --- KEP BRANDING CSS ---
st.markdown("""
    <style>
    .stButton>button { background-color: #000000; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏷️ Bulk Label Maker")
st.write("Upload a spreadsheet, map your columns, and generate perfectly aligned PDFs for standard Avery label sheets.")
st.divider()

# --- PRECISE AVERY MEASUREMENTS (in mm) ---
TEMPLATES = {
    "21-Up (L7060 / L7160) | 63.5 x 38.1mm": {
        "cols": 3, "rows": 7,
        "margin_top": 15.1, "margin_left": 7.2,
        "label_width": 63.5, "label_height": 38.1,
        "pitch_x": 66.0, "pitch_y": 38.1
    },
    "10-Up (L7173) | 99.1 x 57.0mm": {
        "cols": 2, "rows": 5,
        "margin_top": 6.0, "margin_left": 4.6,
        "label_width": 99.1, "label_height": 57.0,
        "pitch_x": 101.6, "pitch_y": 57.0
    },
    "2-Up (L7068 / L7168) | 199.6 x 143.5mm": {
        "cols": 1, "rows": 2,
        "margin_top": 5.0, "margin_left": 5.2,
        "label_width": 199.6, "label_height": 143.5,
        "pitch_x": 199.6, "pitch_y": 143.5
    },
    "1-Up (L7167) | 199.6 x 289.1mm": {
        "cols": 1, "rows": 1,
        "margin_top": 4.0, "margin_left": 5.2,
        "label_width": 199.6, "label_height": 289.1,
        "pitch_x": 199.6, "pitch_y": 289.1
    }
}

col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.subheader("1. Setup")
    uploaded_file = st.file_uploader("Upload Data (.csv or .xlsx)", type=["csv", "xlsx"])
    template_choice = st.selectbox("Select Avery Template", list(TEMPLATES.keys()))

with col2:
    st.subheader("2. Map Data")
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            columns = ["--- Leave Blank ---"] + list(df.columns)
            
            st.write("Select which column should print on each line of the label:")
            
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                line1 = st.selectbox("Line 1 (e.g., FAO / Name)", columns, index=0)
                line2 = st.selectbox("Line 2 (e.g., Company)", columns, index=0)
                line3 = st.selectbox("Line 3 (e.g., Address 1)", columns, index=0)
            with m_col2:
                line4 = st.selectbox("Line 4 (e.g., Address 2)", columns, index=0)
                line5 = st.selectbox("Line 5 (e.g., Town)", columns, index=0)
                line6 = st.selectbox("Line 6 (e.g., Postcode)", columns, index=0)

            st.write(" ")
            if st.button("Generate Print-Ready Labels"):
                if all(line == "--- Leave Blank ---" for line in [line1, line2, line3, line4, line5, line6]):
                    st.warning("Please map at least one column to print.")
                else:
                    with st.spinner("Generating PDF..."):
                        specs = TEMPLATES[template_choice]
                        pdf = FPDF(unit='mm', format='A4')
                        pdf.set_auto_page_break(auto=False)
                        pdf.add_page()
                        pdf.set_font("Arial", size=10)

                        col_idx = 0
                        row_idx = 0

                        for index, row in df.iterrows():
                            # Calculate exact physical placement
                            x = specs["margin_left"] + (col_idx * specs["pitch_x"])
                            y = specs["margin_top"] + (row_idx * specs["pitch_y"])

                            # Gather text
                            lines_to_print = []
                            for line_col in [line1, line2, line3, line4, line5, line6]:
                                if line_col != "--- Leave Blank ---":
                                    val = str(row.get(line_col, "")).strip()
                                    if val and val.lower() != 'nan':
                                        lines_to_print.append(val)

                            # Print the text block
                            # Dynamic Top Padding: If it's a massive label (like 2-up), push the text down a bit further so it's not clinging to the top edge.
                            padding_top = 5 if specs["label_height"] < 60 else 15
                            text_y = y + padding_top 
                            
                            for text in lines_to_print:
                                pdf.set_xy(x + 5, text_y) # 5mm internal padding from the left border
                                
                                # Safety truncation so it doesn't bleed horizontally
                                max_chars = int(specs["label_width"] / 2.5) 
                                pdf.cell(specs["label_width"] - 10, 4, text[:max_chars], ln=True)
                                text_y += 4.5

                            # Grid logic
                            col_idx += 1
                            if col_idx >= specs["cols"]:
                                col_idx = 0
                                row_idx += 1

                            if row_idx >= specs["rows"]:
                                pdf.add_page()
                                col_idx = 0
                                row_idx = 0

                        # Output PDF
                        pdf_bytes = pdf.output(dest='S').encode('latin-1')
                        
                        st.success(f"✅ Generated {len(df)} labels perfectly mapped for {template_choice.split('|')[0].strip()}!")
                        st.download_button(
                            label="⬇️ Download Labels (PDF)",
                            data=pdf_bytes,
                            file_name=f"KEP_Labels_{template_choice.split(' ')[0]}.pdf",
                            mime="application/pdf"
                        )
        except Exception as e:
            st.error(f"Error reading file: {e}")
    else:
        st.info("Upload a spreadsheet to begin mapping your label data.")
