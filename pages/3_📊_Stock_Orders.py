import streamlit as st
import pandas as pd

st.set_page_config(page_title="Stock Orders", page_icon="📊", layout="wide")

st.title("📊 Warehouse Stock & Purchase Orders")
st.write("Live overview of low-stock items and automated supplier routing.")
st.divider()

st.subheader("⚠️ Low Stock Alerts")
# Creating some fake data for the mockup
mock_data = pd.DataFrame({
    "SKU": ["A1-FOAM-03", "CU-BUN-PKG", "TH-POSTER-A4"],
    "Description": ["A1 3mm Foamex Boards", "Craft Union Standard Packaging", "Tim Hortons A4 Promo Paper"],
    "Current Qty": [15, 50, 120],
    "Minimum Threshold": [50, 200, 500],
    "Suggested Order": [100, 500, 1000]
})

st.dataframe(mock_data, use_container_width=True)

st.divider()
st.subheader("Generate Purchase Order")
supplier = st.selectbox("Select Supplier", ["Tropicana Wholesale", "Antalis", "Premier Paper"])

if st.button(f"Generate PO for {supplier}"):
    st.success(f"Purchase order for {supplier} has been drafted and sent to the management approval queue.")
