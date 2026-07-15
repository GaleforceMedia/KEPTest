import streamlit as st
import pandas as pd
import datetime
import io

st.set_page_config(page_title="Print Flo SPK Picks", page_icon="🖨️", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px;}
    .stat-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; font-size: 16px;}
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🖨️ Print Flo (SPK) Pick Lists")
st.write("Upload the Stonegate/Print Flo allocation matrix to automatically generate printable warehouse pick lists.")
st.divider()

# --- HELPER: HTML PICK LIST GENERATOR ---
def generate_pick_list_html(store_data, campaign_name):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>Pick Lists - {campaign_name}</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; padding: 0; margin: 0; color: #000; background-color: #fff; }}
        .no-print {{ text-align: center; padding: 20px; background: #f8f9fa; margin-bottom: 20px; border-bottom: 1px solid #ddd; }}
        .print-btn {{ padding: 12px 24px; background-color: #004B87; color: white; border: none; font-size: 16px; font-weight: bold; border-radius: 4px; cursor: pointer; }}
        .print-btn:hover {{ background-color: #003666; }}
        
        /* PAGE BREAK LOGIC FOR PRINTING */
        .store-page {{ page-break-after: always; padding: 40px; box-sizing: border-box; }}
        .store-page:last-child {{ page-break-after: auto; }}
        
        .header {{ border-bottom: 3px solid #000; padding-bottom: 15px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
        .header h1 {{ margin: 0; font-size: 28px; font-weight: 900; }}
        .header h2 {{ margin: 5px 0 0 0; font-size: 18px; font-weight: normal; color: #555; }}
        .header-meta {{ text-align: right; font-size: 14px; font-weight: bold; }}
        
        .meta-table {{ width: 100%; margin-bottom: 30px; font-size: 16px; }}
        .meta-table td {{ padding: 8px 0; }}
        .meta-table .label {{ font-weight: bold; width: 150px; }}
        
        .pick-table {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; font-size: 16px; }}
        .pick-table th, .pick-table td {{ border: 1px solid #000; padding: 12px; text-align: left; }}
        .pick-table th {{ background-color: #f2f2f2; font-weight: bold; text-transform: uppercase; }}
        .pick-table td.qty-col {{ text-align: center; font-size: 20px; font-weight: bold; width: 100px; }}
        .pick-table td.check-col {{ width: 80px; text-align: center; }}
        .checkbox {{ width: 25px; height: 25px; border: 2px solid #000; display: inline-block; }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ padding: 0; }}
            @page {{ margin: 1cm; }}
        }}
    </style>
    </head>
    <body>
        <div class="no-print">
            <button class="print-btn" onclick="window.print()">🖨️ Print All Pick Lists</button>
            <p style="color: #666; font-size: 14px; margin-top: 10px;">Loads 1 store per page. Ensure 'Print Background Graphics' is ticked.</p>
        </div>
    """
    
    date_str = datetime.datetime.now().strftime("%d/%m/%Y")
    
    for store in store_data:
        html += f"""
        <div class="store-page">
            <div class="header">
                <div>
                    <h1>{store['Site']}</h1>
                    <h2>Postcode: {store['Postcode']}</h2>
                </div>
                <div class="header-meta">
                    Campaign: {campaign_name}<br>
                    Date: {date_str}
                </div>
            </div>
            
            <table class="pick-table">
                <thead>
                    <tr>
                        <th>Item Description</th>
                        <th>Version / Allocation</th>
                        <th>Pick Qty</th>
                        <th>Packed</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for pick in store['Picks']:
            html += f"""
                    <tr>
                        <td><strong>{pick['Item']}</strong></td>
                        <td>{pick['Version']}</td>
                        <td class="qty-col">{pick['Qty']}</td>
                        <td class="check-col"><div class="checkbox"></div></td>
                    </tr>
            """
            
        html += """
                </tbody>
            </table>
            
            <div style="margin-top: 50px; font-size: 14px; display: flex; justify-content: space-between;">
                <div>Picked By: ___________________________</div>
                <div>Packed By: ___________________________</div>
                <div>Box Count: ______</div>
            </div>
        </div>
        """
        
    html += """
    </body>
    </html>
    """
    return html

# --- INTERFACE ---
col_upload, col_summary = st.columns([1, 2], gap="large")

with col_upload:
    st.subheader("1. Upload Matrix")
    uploaded_file = st.file_uploader("Upload Drop Matrix (CSV or Excel)", type=["csv", "xlsx"])
    campaign_name = st.text_input("Campaign Name (For header)", value="Stonegate Phase 1")

with col_summary:
    st.subheader("2. Generation Engine")
    
    if uploaded_file:
        try:
            # 1. Read the raw file to find the actual header row (ignoring marketing's top notes)
            if uploaded_file.name.endswith('.csv'):
                raw_df = pd.read_csv(uploaded_file, header=None)
            else:
                raw_df = pd.read_excel(uploaded_file, header=None)
            
            # Find the row index that contains 'New Site Name' or 'Postcode'
            header_idx = 0
            for idx, row in raw_df.iterrows():
                # FIX: Bulletproof list comprehension that forces EVERY cell to be a string before joining
                row_str = " ".join([str(val) for val in row.values]).lower()
                if 'new site name' in row_str or 'postcode' in row_str:
                    header_idx = idx
                    break
            
            # 2. Reload the dataframe using the correct header row
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=header_idx)
            else:
                df = pd.read_excel(uploaded_file, header=header_idx)
            
            # 3. Find where the picks start (Column I / after Postcode)
            try:
                # Get the index of the 'Postcode' column
                postcode_col_idx = df.columns.get_loc('Postcode')
                start_col_idx = postcode_col_idx + 1
            except:
                # Fallback to column I (index 8) if headers are weird
                start_col_idx = 8
            
            # 4. Parse the data
            processed_stores = []
            total_items_picked = 0
            
            for index, row in df.iterrows():
                site_name = str(row.get('New Site Name', '')).strip()
                postcode = str(row.get('Postcode', '')).strip()
                
                # Skip completely empty rows
                if pd.isna(site_name) or site_name.lower() == 'nan' or site_name == '':
                    continue
                    
                picks = []
                # Loop through the columns in pairs of 2 (Item -> QTY)
                for i in range(start_col_idx, len(df.columns), 2):
                    if i + 1 < len(df.columns):
                        item_name = str(df.columns[i]).strip()
                        version = str(row.iloc[i]).strip()
                        qty = str(row.iloc[i+1]).strip()
                        
                        # Only add if it's a real version and not marked 'X' or 'nan'
                        if version.upper() != 'X' and version.lower() != 'nan' and version != '':
                            if qty.upper() != 'X' and qty.lower() != 'nan' and qty != '':
                                picks.append({
                                    'Item': item_name,
                                    'Version': version,
                                    'Qty': qty
                                })
                                try:
                                    # Added an extra float conversion layer just in case quantities are logged as '100.0'
                                    total_items_picked += int(float(qty))
                                except:
                                    pass
                
                # Only add the store to the print run if they actually have picks
                if picks:
                    processed_stores.append({
                        'Site': site_name,
                        'Postcode': postcode,
                        'Picks': picks
                    })
            
            # 5. Display Summary
            if processed_stores:
                m1, m2 = st.columns(2)
                with m1:
                    st.markdown(f"<div class='metric-card'><h4>Stores to Pack</h4><p class='stat-text'>{len(processed_stores)}</p></div>", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"<div class='metric-card'><h4>Total Items Picked</h4><p class='stat-text'>{total_items_picked:,}</p></div>", unsafe_allow_html=True)
                
                st.success(f"✅ Successfully extracted {len(processed_stores)} store allocations.")
                
                # 6. Generate the Printable Document
                if st.button("Generate Printable Pick Lists"):
                    html_output = generate_pick_list_html(processed_stores, campaign_name)
                    st.components.v1.html(html_output, height=800, scrolling=True)
            else:
                st.warning("Could not find any active picks in this file. Check the format.")
                
        except Exception as e:
            st.error(f"Error processing matrix: {e}")
            
    else:
        st.info("👈 Please upload the Drop Matrix to begin.")
