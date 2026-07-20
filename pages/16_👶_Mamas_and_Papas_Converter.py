import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="M&P Converter", page_icon="👶", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px;}
    .stat-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; font-size: 16px;}
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("👶 Mamas & Papas Spreadsheet Converter")
st.write("Upload the Mamas & Papas allocation sheet to automatically generate the KEP dispatch-ready file.")
st.divider()

col_upload, col_summary = st.columns([1, 2], gap="large")

with col_upload:
    st.subheader("1. Upload Matrix")
    uploaded_file = st.file_uploader("Upload Client File (.xlsx)", type=["xlsx"])

with col_summary:
    st.subheader("2. Generation Engine")
    
    if uploaded_file is not None:
        try:
            # 1. Read Client File
            df_client = pd.read_excel(uploaded_file, sheet_name=0, header=None)
            
            # 2. Determine Column Structure
            num_items = df_client.shape[1] - 1 
            cols = ['Shop Types', 'Delivery Contact', 'Shop Name', 'Address 1', 'Address 2', 
                    'Address 3', 'Address 4', 'Postcode', 'Pick'] + list(range(1, num_items + 1))
            df_out = pd.DataFrame(columns=cols)
            
            # 3. Setup Header Formatting (Rows 0-14)
            header_rows = 15
            for i in range(header_rows):
                df_out.loc[i] = [np.nan] * len(cols)
                
            pick_labels = {
                1: 'Job Number', 2: 'Design', 3: 'Artwork', 4: 'Size', 5: 'Code',
                6: 'Versions', 7: 'Quantity', 8: 'Cost Per Unit', 9: 'Total Cost',
                10: 'Material', 11: 'Printed', 12: 'Finishing', 13: 'Artwork Link', 14: 'Allocation'
            }
            df_out.loc[0, 'Pick'] = 'Pick'
            for row_idx, label in pick_labels.items():
                df_out.loc[row_idx, 'Pick'] = label
                
            # 4. Map Item Specifications
            for col_idx in range(1, num_items + 1):
                if col_idx < df_client.shape[1]:
                    out_col = col_idx + 8 # Offset by the 9 prefix columns
                    
                    df_out.iloc[1, out_col] = df_client.iloc[0, col_idx]   # Job Number
                    df_out.iloc[2, out_col] = df_client.iloc[1, col_idx]   # Design
                    df_out.iloc[4, out_col] = df_client.iloc[2, col_idx]   # Size
                    df_out.iloc[7, out_col] = df_client.iloc[4, col_idx]   # Quantity
                    df_out.iloc[8, out_col] = df_client.iloc[5, col_idx]   # Cost Per Unit
                    df_out.iloc[9, out_col] = df_client.iloc[6, col_idx]   # Total Cost
                    df_out.iloc[5, out_col] = df_client.iloc[9, col_idx]   # Code
                    df_out.iloc[13, out_col] = df_client.iloc[10, col_idx] # Artwork Link
                    
                    # Intelligent Split of Specs into Material and Finishing
                    spec = str(df_client.iloc[11, col_idx])
                    if ',' in spec:
                        mat, fin = spec.split(',', 1)
                        df_out.iloc[10, out_col] = mat.strip()
                        df_out.iloc[12, out_col] = fin.strip()
                    else:
                        df_out.iloc[10, out_col] = spec
                        df_out.iloc[12, out_col] = ""
                        
                    df_out.iloc[11, out_col] = "4/0" # Default Print
                    df_out.iloc[6, out_col] = 1      # Default Versions

            # 5. Map Store Allocations
            store_start_row = 12
            store_rows = df_client.iloc[store_start_row:].copy()
            
            total_stores_processed = 0
            for i in range(len(store_rows)):
                row_data = [np.nan] * 9
                store_name = store_rows.iloc[i, 0]
                
                # Skip truly empty rows to keep the file clean
                if pd.isna(store_name) or str(store_name).strip() == '':
                    continue
                    
                row_data[2] = store_name # Shop Name
                row_data[8] = store_name # Pick / Drive Line
                
                quants = store_rows.iloc[i, 1:num_items+1].tolist()
                row_data.extend(quants)
                df_out.loc[header_rows + total_stores_processed] = row_data
                total_stores_processed += 1
                
            # 6. Create Downloadable Excel Payload
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_out.to_excel(writer, index=False, sheet_name='Collation Output')
            
            # Display success metrics
            m1, m2 = st.columns(2)
            with m1:
                st.markdown(f"<div class='metric-card'><h4>Campaign Items</h4><p class='stat-text'>{num_items}</p></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><h4>Locations Mapped</h4><p class='stat-text'>{total_stores_processed}</p></div>", unsafe_allow_html=True)
            
            st.success("✅ File transposed successfully and ready for the collation team!")
            
            # Use original uploaded filename to create a smart output name
            smart_filename = str(uploaded_file.name).replace('.xlsx', '') + "_DISPATCH.xlsx"
            
            st.download_button(
                label="⬇️ Download Dispatch File",
                data=output.getvalue(),
                file_name=smart_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"An error occurred: {e}")
            
    else:
        st.info("👈 Please upload the Mamas & Papas allocation sheet to begin.")
