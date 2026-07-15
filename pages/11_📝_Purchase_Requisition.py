import streamlit as st
import pandas as pd
import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Purchase Requisition", page_icon="📝", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .price-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📝 Purchase Order Requisition Generator")
st.write("Search the master price list and instantly generate a formatted KEP POR Form for the production team.")
st.divider()

# --- HELPER: HTML POR FORM GENERATOR ---
def generate_por_html(date_str, requester, job_no, qty, product_desc, supplier, unit_cost):
    total_cost = float(qty) * float(unit_cost)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>KEP POR Form - {job_no}</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; padding: 40px; color: #000; background-color: #fff; }}
        .no-print {{ text-align: center; margin-bottom: 30px; }}
        .print-btn {{ padding: 12px 24px; background-color: #004B87; color: white; border: none; font-size: 16px; font-weight: bold; border-radius: 4px; cursor: pointer; }}
        .print-btn:hover {{ background-color: #003666; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 32px; font-weight: 900; letter-spacing: 2px; }}
        .header h2 {{ margin: 10px 0 30px 0; font-size: 20px; font-weight: normal; }}
        .meta-table {{ width: 50%; margin-bottom: 30px; font-size: 16px; }}
        .meta-table td {{ padding: 8px 0; }}
        .meta-table .label {{ font-weight: bold; width: 200px; }}
        .meta-table .value {{ border-bottom: 1px solid #000; width: 300px; }}
        .main-table {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; font-size: 14px; }}
        .main-table th, .main-table td {{ border: 1px solid #000; padding: 12px; text-align: center; }}
        .main-table th {{ background-color: #f2f2f2; font-weight: bold; text-transform: uppercase; }}
        .main-table td.left-align {{ text-align: left; }}
        .footer {{ font-size: 11px; color: #555; margin-top: 60px; text-align: left; }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ padding: 0; }}
            @page {{ margin: 1cm; }}
        }}
    </style>
    </head>
    <body>
        <div class="no-print">
            <button class="print-btn" onclick="window.print()">🖨️ Print Requisition Form</button>
            <p style="color: #666; font-size: 14px; margin-top: 10px;">Click the button above or press Ctrl+P / Cmd+P to print or save as PDF.</p>
        </div>

        <div class="header">
            <h1>KEP</h1>
            <h1 style="font-size: 24px;">PRINT GROUP</h1>
            <h2>Purchase Order Requisition Form</h2>
        </div>

        <table class="meta-table">
            <tr><td class="label">Date:</td><td class="value">{date_str}</td></tr>
            <tr><td class="label">Delivery Date Required:</td><td class="value"></td></tr>
            <tr><td class="label">Requested By:</td><td class="value">{requester}</td></tr>
        </table>

        <table class="main-table">
            <thead>
                <tr>
                    <th style="width: 10%;">Job No.</th>
                    <th style="width: 10%;">Qty.</th>
                    <th style="width: 40%;">Product</th>
                    <th style="width: 15%;">Supplier</th>
                    <th style="width: 10%;">Cost</th>
                    <th style="width: 5%;">Per</th>
                    <th style="width: 10%;">PO Number</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>{job_no}</strong></td>
                    <td>{qty}</td>
                    <td class="left-align">{product_desc}</td>
                    <td>{supplier}</td>
                    <td>£{unit_cost:.2f}</td>
                    <td>Sheet</td>
                    <td></td>
                </tr>
                <tr><td><br></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
                <tr><td><br></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
            </tbody>
        </table>
        
        <div style="text-align: right; font-size: 18px; font-weight: bold; margin-top: -20px; padding-right: 20px;">
            Total Estimated Cost: £{total_cost:.2f}
        </div>

        <div class="footer">
            KEP POR Form - June 2023 - V1 - Approved by SW
        </div>
    </body>
    </html>
    """
    return html


# --- INTERFACE ---
col_left, col_right = st.columns([1, 2], gap="large")

with col_left:
    st.subheader("1. Upload Price Database")
    uploaded_file = st.file_uploader("Upload your Master Costings (CSV)", type=["csv", "xlsx"])
    
    if uploaded_file:
        st.success("Database loaded. Ready to search.")

with col_right:
    st.subheader("2. Requisition Builder")
    
    if uploaded_file:
        try:
            # Load the CSV
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            df.columns = [str(c).strip() for c in df.columns]
            
            # 1. Search Bar
            search_query = st.text_input("🔍 Search Material (e.g., '5mm foamex', 'XLD20565')")
            
            if search_query:
                # Combine description columns for a better search
                desc1 = df.get('Description', pd.Series(dtype='str')).fillna('')
                desc2 = df.get('Description 2', pd.Series(dtype='str')).fillna('')
                item_no = df.get('Item No.', pd.Series(dtype='str')).fillna('')
                
                df['Search_Field'] = item_no + " " + desc1 + " " + desc2
                
                # Filter the dataframe based on the user's query
                filtered_df = df[df['Search_Field'].str.lower().str.contains(search_query.lower())]
                
                if not filtered_df.empty:
                    # Create a clean dropdown list for the user to select the exact sheet
                    options = filtered_df.apply(
                        lambda row: f"{row.get('Item No.', '')} | {row.get('Description', '')} {row.get('Description 2', '')} | £{row.get('Unit Price', 0)}", 
                        axis=1
                    ).tolist()
                    
                    selected_option = st.selectbox("Select the exact sheet size and spec:", options)
                    
                    # Get the data for the selected row
                    selected_idx = options.index(selected_option)
                    selected_row = filtered_df.iloc[selected_idx]
                    
                    st.divider()
                    
                    # 2. Requisition Details Form
                    st.write("**Job Details**")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        job_no = st.text_input("KEP Job Number", placeholder="e.g. 353319")
                    with col_b:
                        qty = st.number_input("Quantity of Sheets", min_value=1, value=1)
                    with col_c:
                        supplier = st.text_input("Supplier", value="Pyramid Display")
                    
                    # Calculations
                    unit_price = float(selected_row.get('Unit Price', 0))
                    total_cost = qty * unit_price
                    
                    st.markdown(f"<div class='metric-card'><h4>Total Material Cost</h4><p class='price-text'>£{total_cost:,.2f}</p></div>", unsafe_allow_html=True)
                    
                    # 3. Generate the POR Form
                    if st.button("Generate POR Form (Printable)"):
                        if not job_no:
                            st.error("Please enter a Job Number before generating.")
                        else:
                            today_str = datetime.datetime.now().strftime("%d/%m/%Y")
                            product_string = f"{selected_row.get('Item No.', '')} - {selected_row.get('Description', '')} {selected_row.get('Description 2', '')}"
                            
                            html_output = generate_por_html(
                                date_str=today_str,
                                requester="Matt Gale",
                                job_no=job_no,
                                qty=qty,
                                product_desc=product_string,
                                supplier=supplier,
                                unit_cost=unit_price
                            )
                            
                            st.success("✅ Form Generated! Scroll down to preview and print.")
                            st.components.v1.html(html_output, height=800, scrolling=True)

                else:
                    st.warning("No materials found matching that search. Check spelling or try a broader term.")
                    
        except Exception as e:
            st.error(f"Error reading the database: {e}")
    else:
        st.info("👈 Please upload your KEP Sales Prices CSV on the left to begin.")
