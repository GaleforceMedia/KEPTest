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

# --- CUSTOM STORE ORDER (Includes blank lines for grouping) ---
TARGET_STORES_RAW = """ARNOTTS
BLANCHARDSTOWN
DUNDRUM
BELFAST
BIRMINGHAM GALLAGHER
CROYDON
EDINBURGH
FAREHAM
FARNBOROUGH
GATESHEAD
GLASGOW
HULL
LEEDS
LIVERPOOL SPEKE
NOTTINGHAM
SOUTHAMPTON - NEW Location
STRATFORD
STOCKTON
SWINDON
THURROCK
TRAFFORD 
WHITE CITY
OUTLET

NEXT ARNDALE
NEXT BEDFORD
NEXT BRENT CROSS
NEXT BRISTOL
NEXT Charlton
NEXT Chelsford
NEXT Cheltenham
NEXT Crawley
NEXT Dundee
NEXT Enfield
NEXT EXETER
NEXT HAYES
NEXT HIGH WYCOMBE
NEXT Ipswich
NEXT Leicester 
NEXT Luton
NEXT MAIDSTONE
NEXT MILTON KEYNES
NEXT New Malden
NEXT NORWICH
NEXT Oxford
NEXT Peterborough
NEXT Plymouth
NEXT Poole
NEXT Preston
NEXT SHEFFIELD
NEXT SHOREHAM
NEXT Shrewsbury
NEXT SOLIHULL
NEXT SWANSEA
NEXT Tamworth
NEXT WATFORD

M&S Banbury
M&S Bluewater
M&S Cardiff
M&S Cheshire Oaks
M&S Lisburn
M&S Longbridge
M&S Warrington
M&S Westwood Cross
M&S York"""

TARGET_ORDER = [str(s).strip().upper() for s in TARGET_STORES_RAW.split('\n')]

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
            
            # 2. SMART DETECTOR: Dynamically find rows based on M&P's changing headers
            # (Force cast to string to prevent float/NaN length errors)
            def get_row_idx(keywords):
                for i in range(len(df_client)):
                    val_str = str(df_client.iloc[i, 0]).lower()
                    if any(kw in val_str for kw in keywords):
                        return i
                return -1 
                
            mappings = {
                'job_num': get_row_idx(['kep job number', 'uploaded & ready']),
                'design': get_row_idx(['job number', 'name', 'design', 'job name']),
                'size': get_row_idx(['comments', 'size']),
                'qty': get_row_idx(['number of units', 'total units', 'quantity']),
                'cost_pu': get_row_idx(['cost per unit']),
                'total_cost': get_row_idx(['total cost', 'costs']),
                'link': get_row_idx(['link']),
                'spec': get_row_idx(['spec'])
            }
            
            # Find the max row used by headers so we know exactly where the stores begin
            max_header_idx = max(filter(lambda x: x != -1, mappings.values()))
            
            # 3. Determine Column Structure
            num_items = df_client.shape[1] - 1 
            cols = ['Shop Types', 'Delivery Contact', 'Shop Name', 'Address 1', 'Address 2', 
                    'Address 3', 'Address 4', 'Postcode', 'Pick'] + list(range(1, num_items + 1))
            
            df_out = pd.DataFrame(columns=cols, dtype=object)
            
            # 4. Setup Dispatch Header Formatting (Rows 0-14)
            header_rows = 15
            for i in range(header_rows):
                df_out.loc[i] = [None] * len(cols)
                
            pick_labels = {
                1: 'Job Number', 2: 'Design', 3: 'Artwork', 4: 'Size', 5: 'Code',
                6: 'Versions', 7: 'Quantity', 8: 'Cost Per Unit', 9: 'Total Cost',
                10: 'Material', 11: 'Printed', 12: 'Finishing', 13: 'Artwork Link', 14: 'Allocation'
            }
            df_out.loc[0, 'Pick'] = 'Pick'
            for row_idx, label in pick_labels.items():
                df_out.loc[row_idx, 'Pick'] = label
                
            # 5. Map Item Specifications dynamically based on what the detector found
            for col_idx in range(1, num_items + 1):
                if col_idx < df_client.shape[1]:
                    out_col = col_idx + 8
                    
                    if mappings['job_num'] != -1: df_out.iloc[1, out_col] = df_client.iloc[mappings['job_num'], col_idx]
                    if mappings['design'] != -1: df_out.iloc[2, out_col] = df_client.iloc[mappings['design'], col_idx]
                    if mappings['size'] != -1: df_out.iloc[4, out_col] = df_client.iloc[mappings['size'], col_idx]
                    if mappings['qty'] != -1: df_out.iloc[7, out_col] = df_client.iloc[mappings['qty'], col_idx]
                    if mappings['cost_pu'] != -1: df_out.iloc[8, out_col] = df_client.iloc[mappings['cost_pu'], col_idx]
                    if mappings['total_cost'] != -1: df_out.iloc[9, out_col] = df_client.iloc[mappings['total_cost'], col_idx]
                    if mappings['link'] != -1: df_out.iloc[13, out_col] = df_client.iloc[mappings['link'], col_idx]
                    
                    # Material & Finishing parsing
                    if mappings['spec'] != -1:
                        spec = str(df_client.iloc[mappings['spec'], col_idx])
                        if ',' in spec:
                            mat, fin = spec.split(',', 1)
                            df_out.iloc[10, out_col] = mat.strip()
                            df_out.iloc[12, out_col] = fin.strip()
                        elif spec.lower() not in ['nan', 'none', '']:
                            df_out.iloc[10, out_col] = spec
                            df_out.iloc[12, out_col] = ""
                            
                    df_out.iloc[11, out_col] = "4/0"
                    df_out.iloc[6, out_col] = 1      

            # 6. Build a Map of all Stores in the Excel File (Stripped of NaNs to block float errors)
            excel_store_map = {}
            for i in range(len(df_client)):
                val_str = str(df_client.iloc[i, 0]).strip().upper()
                # Ensure we are past the headers and the cell isn't empty/NaN
                if i > max_header_idx and val_str not in ['NAN', 'NONE', '']:
                    excel_store_map[val_str] = i

            # Helper function for fuzzy matching (e.g. "Southampton" vs "Southampton - New Location")
            def find_excel_store(target):
                if target in excel_store_map: return target
                for excel_store in excel_store_map:
                    if len(excel_store) > 3 and (target in excel_store or excel_store in target):
                        return excel_store
                return None

            # 7. Write Stores to Output Based on User's Custom Sort Order
            processed_stores = set()
            current_out_row = header_rows
            
            for target_store in TARGET_ORDER:
                row_data = [None] * len(cols)
                
                # Check for blank line request from the user's list
                if target_store == "":
                    df_out.loc[current_out_row] = row_data 
                    current_out_row += 1
                    continue
                
                matched_excel_name = find_excel_store(target_store)
                
                row_data[2] = target_store.title()
                row_data[8] = target_store.title()
                
                if matched_excel_name:
                    # Pull the quantities from the Excel file
                    excel_row_idx = excel_store_map[matched_excel_name]
                    quants = df_client.iloc[excel_row_idx, 1:num_items+1].tolist()
                    row_data[9:] = quants
                    processed_stores.add(matched_excel_name)
                
                df_out.loc[current_out_row] = row_data
                current_out_row += 1
                
            # 8. Data Loss Prevention: Append any remaining stores not caught in the list (e.g. "SPARES")
            leftover_stores = [s for s in excel_store_map if s not in processed_stores]
            if leftover_stores:
                df_out.loc[current_out_row] = [None] * len(cols) # Add a visual blank line before leftovers
                current_out_row += 1
                for left_store in leftover_stores:
                    row_data = [None] * len(cols)
                    row_data[2] = left_store.title()
                    row_data[8] = left_store.title()
                    
                    excel_row_idx = excel_store_map[left_store]
                    quants = df_client.iloc[excel_row_idx, 1:num_items+1].tolist()
                    row_data[9:] = quants
                    
                    df_out.loc[current_out_row] = row_data
                    current_out_row += 1

            # 9. Create Downloadable Excel Payload
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_out.to_excel(writer, index=False, sheet_name='Collation Output')
            
            # Display success metrics
            m1, m2 = st.columns(2)
            with m1:
                st.markdown(f"<div class='metric-card'><h4>Campaign Items</h4><p class='stat-text'>{num_items}</p></div>", unsafe_allow_html=True)
            with m2:
                total_mapped = len([s for s in TARGET_ORDER if s != ""]) + len(leftover_stores)
                st.markdown(f"<div class='metric-card'><h4>Locations Mapped</h4><p class='stat-text'>{total_mapped}</p></div>", unsafe_allow_html=True)
            
            st.success("✅ File transposed, intelligently ordered, and ready for the collation team!")
            
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
