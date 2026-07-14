import streamlit as st
import pandas as pd
import io
import zipfile
import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Tracking Consolidator", page_icon="🚚", layout="wide")

# --- BRANDING DICTIONARIES ---
# This maps the Account Number to specific CSS styles and titles
BRANDING = {
    "F181494": {
        "name": "PrintFlo",
        "title": "PrintFlo Dispatch Report",
        "primary_color": "#ff6600", # PrintFlo Orange
        "bg_color": "#ffffff",
        "header_text": "#ffffff",
        "link": "https://printflo.co.uk/",
        "logo_text": "PrintFlo Fulfillment"
    },
    "F199630": {
        "name": "Mamas_and_Papas",
        "title": "Mamas & Papas Dispatch Report",
        "primary_color": "#000000", # M&P Black/Minimalist
        "bg_color": "#ffffff",
        "header_text": "#ffffff",
        "link": "https://www.mamasandpapas.com/",
        "logo_text": "M&P Campaign Dispatch"
    },
    "F090402": {
        "name": "KEP_Print_Group",
        "title": "KEP Dispatch Report",
        "primary_color": "#004B87", # KEP Blue
        "bg_color": "#ffffff",
        "header_text": "#ffffff",
        "link": "https://www.kep.co.uk/",
        "logo_text": "KEP Print Group"
    }
}

# --- DEFAULT FALLBACK BRANDING ---
DEFAULT_BRAND = {
    "name": "General_Dispatch",
    "title": "Dispatch Report",
    "primary_color": "#555555",
    "bg_color": "#ffffff",
    "header_text": "#ffffff",
    "link": "#",
    "logo_text": "Dispatch Tracking"
}

# --- UI STYLING ---
st.markdown("""
    <style>
    .stButton>button { background-color: #000000; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚚 Post-Ship Tracking Consolidator")
st.write("Upload the End-of-Day DHL tracking export. The system will separate the data by Account Number and generate branded HTML tracking dashboards for each client.")
st.divider()

# --- HELPER: HTML GENERATOR ---
def generate_branded_html(df, brand_code, date_str):
    brand = BRANDING.get(brand_code, DEFAULT_BRAND)
    
    html = f"""<!DOCTYPE html>
    <html>
    <head>
    <title>{brand['title']}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f6; color: #333; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: {brand['bg_color']}; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .header {{ background-color: {brand['primary_color']}; color: {brand['header_text']}; padding: 25px 30px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ margin: 0; font-size: 24px; letter-spacing: 1px; }}
        .header a {{ color: {brand['header_text']}; text-decoration: none; font-size: 14px; opacity: 0.8; }}
        .content {{ padding: 30px; }}
        .meta {{ margin-bottom: 25px; font-size: 14px; color: #666; border-bottom: 2px solid #eee; padding-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background-color: #f8f9fa; font-weight: 600; color: #555; text-transform: uppercase; font-size: 12px; }}
        tr:hover {{ background-color: #fcfcfc; }}
        .track-btn {{ background-color: {brand['primary_color']}; color: {brand['header_text']} !important; padding: 8px 15px; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 12px; display: inline-block; transition: opacity 0.2s; }}
        .track-btn:hover {{ opacity: 0.8; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{brand['logo_text']}</h1>
                <a href="{brand['link']}" target="_blank">Visit Website &rarr;</a>
            </div>
            <div class="content">
                <div class="meta">
                    <strong>Date:</strong> {date_str} <br>
                    <strong>Total Shipments:</strong> {len(df)}
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Reference / Store</th>
                            <th>Postcode</th>
                            <th>Service</th>
                            <th>Items</th>
                            <th>Tracking Action</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    # Identify dynamic columns from the uploaded DHL export
    cols = [str(c).lower() for c in df.columns]
    
    # Find the best matching columns for our table
    ref_col = next((c for c in df.columns if 'ref' in str(c).lower() or 'name' in str(c).lower()), 'Unknown')
    postcode_col = next((c for c in df.columns if 'postcode' in str(c).lower() or 'address 4' in str(c).lower()), 'Unknown')
    service_col = next((c for c in df.columns if 'service desc' in str(c).lower() or 'service' in str(c).lower()), 'Standard')
    items_col = next((c for c in df.columns if 'item' in str(c).lower() or 'pieces' in str(c).lower()), '1')
    track_col = next((c for c in df.columns if 'consignment' in str(c).lower() or 'tracking' in str(c).lower()), None)

    for _, row in df.iterrows():
        ref = str(row[ref_col]) if ref_col in df.columns else "N/A"
        pc = str(row[postcode_col]) if postcode_col in df.columns else "N/A"
        srv = str(row[service_col]) if service_col in df.columns else "DHL Service"
        itm = str(row[items_col]) if items_col in df.columns else "1"
        trk = str(row[track_col]).replace('.0', '') if track_col in df.columns else ""
        
        # Build the DHL Tracking URL
        track_link = f"https://track.dhlparcel.co.uk/?trackingnumber={trk}" if trk else "#"
        track_html = f"<a href='{track_link}' class='track-btn' target='_blank'>Track {trk}</a>" if trk else "<em>No Tracking</em>"

        html += f"""
                        <tr>
                            <td><strong>{ref}</strong></td>
                            <td>{pc}</td>
                            <td>{srv}</td>
                            <td>{itm}</td>
                            <td>{track_html}</td>
                        </tr>
        """
        
    html += """
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html

# --- INTERFACE ---
left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.subheader("1. Upload Export")
    uploaded_file = st.file_uploader("Upload DHL End of Day Export (.csv or .xlsx)", type=["csv", "xlsx"])
    
    if uploaded_file:
        st.success("File loaded successfully.")

with right_col:
    st.subheader("2. Preview & Generate")
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            # Clean column names
            df.columns = [str(c).strip() for c in df.columns]
            
            # Find the Account Number column
            acc_col = next((c for c in df.columns if 'account' in str(c).lower()), None)
            
            if not acc_col:
                st.warning("Could not auto-detect the 'Account Number' column.")
                acc_col = st.selectbox("Select the Account Number column:", df.columns)
                
            if acc_col:
                # Group by Account Number
                accounts = df[acc_col].dropna().unique()
                st.write(f"Detected **{len(accounts)}** distinct accounts in this export: {', '.join([str(a) for a in accounts])}")
                
                if st.button("Generate Branded HTML Reports"):
                    with st.spinner("Splitting data and applying brand templates..."):
                        
                        today_str = datetime.datetime.now().strftime("%d %B %Y")
                        zip_buffer = io.BytesIO()
                        
                        # Set up tabs for live previews
                        tabs = st.tabs([str(acc) for acc in accounts])
                        
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            
                            for idx, account_id in enumerate(accounts):
                                acc_str = str(account_id).strip()
                                group_df = df[df[acc_col] == account_id]
                                
                                # Generate the HTML string
                                html_output = generate_branded_html(group_df, acc_str, today_str)
                                
                                # Determine safe filename
                                brand_info = BRANDING.get(acc_str, DEFAULT_BRAND)
                                file_name = f"Tracking_{brand_info['name']}_{datetime.datetime.now().strftime('%Y%m%d')}.html"
                                
                                # Write to ZIP
                                zip_file.writestr(file_name, html_output)
                                
                                # Render preview in the corresponding tab
                                with tabs[idx]:
                                    st.write(f"**Previewing:** {file_name} ({len(group_df)} Shipments)")
                                    components.html(html_output, height=500, scrolling=True)

                        st.success("✅ Tracking Dashboards Generated!")
                        st.download_button(
                            label="⬇️ Download All Branded HTML Reports (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name=f"KEP_Branded_Tracking_{datetime.datetime.now().strftime('%Y%m%d')}.zip",
                            mime="application/zip"
                        )
                        
        except Exception as e:
            st.error(f"Error processing the file: {e}")
    else:
        st.info("Upload the raw tracking spreadsheet to auto-generate your client-facing HTML dashboards.")
