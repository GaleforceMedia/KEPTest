import streamlit as st
import pandas as pd
import time

st.set_page_config(page_title="Collation Prep", page_icon="⚙️", layout="wide")

st.title("⚙️ Collation Machine Setup")
st.write("Upload raw client mailing lists to automatically format, deduplicate, and sort them for the digital presses.")
st.divider()

uploaded_file = st.file_uploader("Upload Mailing List (.csv or .xlsx)", type=["csv", "xlsx"])

if uploaded_file:
    st.success(f"Loaded {uploaded_file.name}")
    
    col1, col2 = st.columns(2)
    with col1:
         st.selectbox("Target Machine", ["Standard Encloser", "High-Speed Folder/Inserter", "Manual Fulfillment"])
    with col2:
         st.selectbox("Sorting Logic", ["Sort by Postcode (Mailsort)", "Sort by Job Segment", "Alphabetical"])
         
    if st.button("Process & Deduplicate Data"):
        with st.spinner("Running deduplication and formatting..."):
            time.sleep(2) # Fake loading time for the mockup
            st.success("Data processed! 12 duplicates removed. Ready for print.")
            st.download_button("⬇️ Download Formatted Machine File", data="mock_data", file_name="KEP_Collation_Ready.csv")
