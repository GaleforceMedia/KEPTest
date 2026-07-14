import streamlit as st
import pandas as pd
import io
import zipfile
import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Tracking Consolidator", page_icon="🚚", layout="wide")

# --- BRANDING DICTIONARIES ---
BRANDING = {
    "F181494": {
        "name": "PrintFlo",
        "title": "PrintFlo Dispatch Report",
        "primary_color": "#ff6600", 
        "bg_color": "#ffffff",
        "header_text": "#ffffff",
        "link": "https://printflo.co.uk/",
        "logo_text": "PrintFlo Fulfillment"
    },
    "F199630": {
        "name": "Mamas_and_Papas",
        "title": "Mamas & Papas Dispatch Report",
        "primary_color": "#000000", 
        "bg_color": "#ffffff",
        "header_text": "#ffffff",
        "link": "https://www.mamasandpapas.com/",
        "logo_text": "M&P Campaign Dispatch"
    },
    "F090402": {
        "name": "KEP_Print_Group",
        "title": "KEP Dispatch Report",
        "primary_color": "#004B87", 
        "bg_color": "#ffffff",
        "header_text": "#ffffff",
        "link": "https://www.kep.co.uk/",
        "logo_text": "KEP Print Group"
    }
}

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
st.write("Upload your DHL Dashboard Summary export. The system will separate the data by Account Number and generate branded HTML tracking dashboards.")
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
        .container {{ max-width: 1100px; margin: 0 auto; background: {brand['bg_color']}; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
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
        .status-badge {{ font-weight: bold; font-size: 13px; }}
        .eta-text {{ font-size: 12px; color: #777; margin-top: 4px; display: block; }}
        .ref-text {{ color: #777; font-size: 12px; margin-top: 4px; display: block; }}
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
                    <strong>Report Date:</strong> {date_str} <br>
                    <strong>Total Shipments:</strong> {len(df)}
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Store / Recipient</th>
                            <th>Postcode</th>
                            <th>Service</th>
                            <th>Status & ETA</th>
                            <th>Tracking Action</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    # Process the specific column names from the DHL Dashboard Summary
    for _, row in df.iterrows():
        # Safely pull data from the known columns
        ref = str(row.get('Customer reference', ''))
        recipient = str(row.get('Business/Recipient name', 'Unknown'))
        
        # Combine Reference and Recipient for a cleaner look
        store_display = f"<strong>{recipient}</strong>"
        if ref and ref.lower() != 'nan':
            store_display += f"<span class='ref-text'>Ref: {ref}</span>"

        pc = str(row.get('Postal Code', ''))
        
        service_raw = str(row.get('Service', ''))
        parcels = str(row.get('Number of parcels', '1'))
        service_display = f"{service_raw}<span class='ref-text'>({parcels} Parcel{'s' if parcels != '1' else ''})</span>"
        
        status = str(row.get('Status', 'Unknown'))
        eta_date = str(row.get('Delivery due date', ''))
        eta_time = str(row.get('ETA', ''))
        
        # Clean up 'nan' string artifacts
        eta_date = "" if eta_date.lower() == 'nan' else eta_date
        eta_time = "" if eta_time.lower() == 'nan' else eta_time
        
        # Format the Status & ETA column
        status_color = "#27ae60" if status.lower() == "delivered" else "#e67e22" if "out for delivery" in status.lower() else "#333"
        status_display = f"<span class='status-badge' style='color: {status_color};'>{status}</span>"
        
        if eta_date or eta_time:
            eta_string = f"{eta_date} {eta_time}".strip()
            status_display += f"<span class='eta-text'>ETA: {eta_string}</span>"
            
        trk = str(row.get('Shipment number', '')).replace('.0', '')
        if trk.lower() == 'nan': trk = ""
        
        # --- THE UPDATED DHL TRACKING URL ---
        track_link = f"https://www.dhl.com/gb-en/home/tracking.html?tracking-id={trk}&submit=1" if trk else "#"
        track_html = f"<a href='{track_link}' class='track-btn' target='_blank'>Track {trk}</a>" if trk else "<em>No Tracking</em>"

        html += f"""
                        <tr>
                            <td>{store_display}</td>
                            <td>{pc}</td>
                            <td>{service_display}</td>
                            <td>{status_display}</td>
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
    uploaded_file = st.file_uploader("Upload DHL Dashboard Summary (.csv)", type=["csv", "xlsx"])
    
    if uploaded_file:
        st.success("Dashboard Summary loaded successfully.")

with right_col:
    st.subheader("2. Preview & Generate")
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            # Clean column names (strip trailing spaces which often happen in CSVs)
            df.columns = [str(c).strip() for c in df.columns]
            
            # Use the exact column name 'Accounts'
            if 'Accounts' not in df.columns:
                st.error("Error: Could not find the 'Accounts' column in the uploaded file. Please ensure you are uploading the raw Dashboard Summary.")
            else:
                # Group by Account Number
                accounts = df['Accounts'].dropna().unique()
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
                                group_df = df[df['Accounts'] == account_id]
                                
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
                                    components.html(html_output, height=600, scrolling=True)

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
        st.info("Upload the raw DHL Dashboard Summary to auto-generate your client-facing HTML dashboards.")
