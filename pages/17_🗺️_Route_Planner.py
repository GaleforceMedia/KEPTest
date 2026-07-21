import streamlit as st
import pandas as pd
import requests
import folium
from sklearn.cluster import KMeans
import numpy as np
import io
import re
import time
import os
from fpdf import FPDF
import datetime

st.set_page_config(page_title="KEP Route Planner", page_icon="🗺️", layout="wide")

# --- PREMIUM KEP UI STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .kep-banner {
        background-color: white;
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-top: -2rem;
        margin-bottom: 2rem;
        border-top: 8px solid #004B87;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }
    .kep-banner h1 {
        color: #004B87 !important;
        margin: 0.5rem 0 0.2rem 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .kep-banner p {
        margin: 0;
        color: #555;
        font-size: 1.1rem;
        font-weight: 400;
    }

    .section-header {
        color: #004B87;
        font-weight: 800;
        font-size: 1.3rem;
        margin-top: 1.5rem;
        margin-bottom: 1.2rem;
        border-bottom: 2px solid #edf2f7;
        padding-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .metric-card {
        background: white;
        padding: 24px;
        border-radius: 10px;
        border-left: 6px solid #004B87;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
        text-align: left;
        margin-bottom: 20px;
        transition: transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); }
    .metric-card h4 {
        margin: 0 0 8px 0; color: #8898aa; font-size: 0.9rem;
        font-weight: 600; text-transform: uppercase; letter-spacing: 1px;
    }
    .stat-text { color: #004B87; font-size: 32px; font-weight: 800; margin: 0; }

    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stDateInput>div>div>input {
        border: 1px solid #cbd5e0 !important; border-radius: 6px !important;
        background-color: #f8fafc !important; transition: all 0.2s ease;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus, .stDateInput>div>div>input:focus {
        border-color: #004B87 !important; background-color: white !important;
        box-shadow: 0 0 0 1px #004B87 !important;
    }

    .stButton>button {
        background: linear-gradient(135deg, #004B87 0%, #002D54 100%);
        color: white !important; border-radius: 8px; font-weight: 600 !important;
        padding: 0.8rem 1.5rem; width: 100%; border: none; font-size: 1.1rem;
        box-shadow: 0 4px 14px rgba(0, 75, 135, 0.25); transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #00569b 0%, #003666 100%);
        box-shadow: 0 6px 20px rgba(0, 75, 135, 0.4); transform: translateY(-1px);
    }

    [data-testid="stDownloadButton"]>button {
        background: white !important; color: #004B87 !important;
        border: 2px solid #004B87 !important; box-shadow: none !important;
    }
    [data-testid="stDownloadButton"]>button:hover {
        background: #f0f7fd !important; transform: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CUSTOM BRANDED HEADER ---
logo_path = "keplogo.png" if os.path.exists("keplogo.png") else "keplogo.svg" if os.path.exists("keplogo.svg") else None

st.markdown("<div class='kep-banner'>", unsafe_allow_html=True)
if logo_path:
    st.image(logo_path, width=180)
st.markdown("""
    <h1>Dispatch Route & Logistics Planner</h1>
    <p>Calculate optimal driver sequences and instantly generate automated delivery notes.</p>
    </div>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def extract_postcode(text):
    pattern = r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})'
    match = re.search(pattern, text, re.IGNORECASE)
    if match: return match.group(1).upper()
    return None

def geocode_postcodes_bulk(postcode_map):
    results = {}
    headers = {"Content-Type": "application/json"}
    unique_pcs = list(set(postcode_map.values()))
    for i in range(0, len(unique_pcs), 100):
        chunk = unique_pcs[i:i+100]
        try:
            resp = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": chunk}, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('result', [])
                pc_data_lookup = {item['query']: item['result'] for item in data if item['result']}
                for original_str, extracted_pc in postcode_map.items():
                    if extracted_pc in pc_data_lookup:
                        res = pc_data_lookup[extracted_pc]
                        name_part = original_str.replace(extracted_pc, "").strip(" ,-")
                        display_addr = f"{name_part}, {extracted_pc}, {res.get('admin_district', '')}".strip(" ,")
                        if not name_part: display_addr = f"{extracted_pc}, {res.get('admin_district', '')}".strip(" ,")
                        results[original_str] = {
                            'lat': res['latitude'], 'lon': res['longitude'],
                            'full_address': display_addr, 'postcode': res['postcode']
                        }
        except Exception: pass
    return results

def geocode_places_osm(place_list, progress_bar, status_text):
    results = {}
    headers = {"User-Agent": "KEP_Print_Dispatch_Router/1.0"}
    total = len(place_list)
    for idx, place in enumerate(place_list):
        status_text.text(f"Searching database for '{place}'...")
        progress_bar.progress((idx + 1) / total)
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={place}&format=json&addressdetails=1&countrycodes=gb"
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 0:
                    best_match = data[0]
                    addr = best_match.get('address', {})
                    pc = addr.get('postcode', 'N/A')
                    full_addr = best_match.get('display_name', place)
                    results[place] = {
                        'lat': float(best_match['lat']), 'lon': float(best_match['lon']),
                        'full_address': full_addr, 'postcode': pc
                    }
            time.sleep(1)
        except Exception: pass
    return results

# --- INTERFACE ---
col_inputs, col_map = st.columns([1, 2], gap="large")

with col_inputs:
    st.markdown("<h3 class='section-header'>📍 Route Parameters</h3>", unsafe_allow_html=True)
    depot_postcode = st.text_input("Depot Postcode (Start & End)", value="B77 5AE")
    raw_locations = st.text_area("Paste Locations (Names or Postcodes)", height=150, 
                                 placeholder="e.g.\nCV1 2HN\nTamworth High School B77 3AA\nM&S Banbury")
    num_vans = st.slider("Number of Vans / Runs", min_value=1, max_value=5, value=1)
    
    st.markdown("<h3 class='section-header'>📝 Manifest Data</h3>", unsafe_allow_html=True)
    col_dn1, col_dn2 = st.columns(2)
    with col_dn1:
        job_number = st.text_input("Job Number", placeholder="e.g. 355814")
        delivery_date = st.date_input("Delivery Date", datetime.date.today())
    with col_dn2:
        job_qty = st.text_input("Quantity Delivered", placeholder="e.g. 300 (Blank for none)")
    job_desc = st.text_input("Job Title / Description", placeholder="e.g. Perm POS - Hand Washing...")
    
    st.markdown("<br>", unsafe_allow_html=True)
    calculate_btn = st.button("🗺️ Compile Logistics Plan")

with col_map:
    st.markdown("<h3 class='section-header'>🗺️ Interactive Route Map</h3>", unsafe_allow_html=True)
    
    if calculate_btn and raw_locations.strip():
        raw_list = [p.strip() for p in raw_locations.split('\n') if p.strip()]
        raw_list = list(set(raw_list)) 
        
        with_postcodes_map = {} 
        place_names_only = []
        for loc in raw_list:
            found_pc = extract_postcode(loc)
            if found_pc: with_postcodes_map[loc] = found_pc
            else: place_names_only.append(loc)
        
        depot_pc_extracted = extract_postcode(depot_postcode) or depot_postcode
        depot_data = geocode_postcodes_bulk({depot_postcode: depot_pc_extracted})
        
        if depot_postcode not in depot_data:
            st.error("Could not find the Depot postcode. Please check the format.")
            st.stop()
        
        depot_lat, depot_lon = depot_data[depot_postcode]['lat'], depot_data[depot_postcode]['lon']
        
        progress_container = st.empty()
        status_container = st.empty()
        drop_data = {}
        
        if with_postcodes_map:
            status_container.text("Processing exact coordinates...")
            drop_data.update(geocode_postcodes_bulk(with_postcodes_map))
            
        if place_names_only:
            pb = progress_container.progress(0)
            drop_data.update(geocode_places_osm(place_names_only, pb, status_container))
            progress_container.empty()
            
        status_container.text("Calculating optimal driving routes...")
        
        valid_drops, failed_drops = [], []
        for loc in raw_list:
            if loc in drop_data:
                valid_drops.append({
                    'query': loc, 'lat': drop_data[loc]['lat'], 'lon': drop_data[loc]['lon'],
                    'full_address': drop_data[loc]['full_address'], 'postcode': drop_data[loc]['postcode']
                })
            else: failed_drops.append(loc)
                
        if failed_drops: st.warning(f"Could not find coordinates for: {', '.join(failed_drops)}")
        if not valid_drops:
            st.error("No valid locations found to route.")
            status_container.empty()
            st.stop()

        van_assignments = {i: [] for i in range(num_vans)}
        actual_vans = min(num_vans, len(valid_drops))
        
        if actual_vans > 1:
            coords = [[d['lat'], d['lon']] for d in valid_drops]
            kmeans = KMeans(n_clusters=actual_vans, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(coords)
            for drop, label in zip(valid_drops, labels):
                van_assignments[label].append(drop)
        else: van_assignments[0] = valid_drops
            
        m = folium.Map(location=[depot_lat, depot_lon], zoom_start=6)
        folium.Marker([depot_lat, depot_lon], popup="KEP Depot", icon=folium.Icon(color="black", icon="home")).add_to(m)
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        total_miles, total_hours = 0, 0
        master_itinerary = []
        
        for van_id, drops in van_assignments.items():
            if not drops: continue
            color = colors[van_id % len(colors)]
            depot_block = {
                'query': 'KEP DEPOT', 'full_address': f'KEP Print Group, {depot_postcode}', 
                'postcode': depot_pc_extracted, 'lat': depot_lat, 'lon': depot_lon
            }
            
            input_points = [depot_block] + drops
            coords_str = ";".join([f"{p['lon']},{p['lat']}" for p in input_points])
            url = f"http://router.project-osrm.org/trip/v1/driving/{coords_str}?source=first&roundtrip=true&geometries=geojson"
            
            try:
                resp = requests.get(url)
                data = resp.json()
                if data.get('code') == 'Ok':
                    route = data['trips'][0]
                    waypoints = data['waypoints']
                    miles = route['distance'] / 1609.34
                    duration = route['duration'] / 3600 
                    total_miles += miles
                    total_hours += duration
                    
                    folium.GeoJson(
                        route['geometry'],
                        name=f"Van {van_id+1}",
                        style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.8}
                    ).add_to(m)
                    
                    for i, wp in enumerate(waypoints): input_points[i]['sequence'] = wp['waypoint_index']
                    optimized_drops = sorted(input_points, key=lambda x: x['sequence'])
                    
                    for i, p in enumerate(optimized_drops):
                        master_itinerary.append({
                            "Van / Run": f"Van {van_id+1}", "Stop Sequence": i + 1,
                            "Original Search": p['query'], "Extracted Postcode": p['postcode'],
                            "Full Completed Address": p['full_address']
                        })
                    
                    st.markdown(f"**🚐 Van {van_id+1} Route** — Est. Time: {int(duration)}h {int((duration % 1) * 60)}m | Mileage: {miles:.1f} mi")
                    df_display = pd.DataFrame({
                        "Stop": range(1, len(optimized_drops) + 1), "Search": [p['query'] for p in optimized_drops],
                        "Address Found": [p['full_address'] for p in optimized_drops]
                    })
                    st.dataframe(df_display, hide_index=True, use_container_width=True)
                    
                    for i, p in enumerate(optimized_drops):
                        if p['query'] != 'KEP DEPOT':
                            folium.Marker(
                                [p['lat'], p['lon']], popup=f"Stop {i+1}: {p['query']}",
                                tooltip=p['full_address'], icon=folium.Icon(color=color, icon="info-sign")
                            ).add_to(m)
                else: st.error(f"Routing engine failed for Van {van_id+1}.")
            except Exception: st.error(f"Could not calculate exact road route for Van {van_id+1}.")
        
        status_container.empty()
        
        st.markdown("<br>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"<div class='metric-card'><h4>Total Campaign Mileage</h4><p class='stat-text'>{total_miles:.1f} mi</p></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><h4>Total Driving Time</h4><p class='stat-text'>{int(total_hours)}h {int((total_hours % 1) * 60)}m</p></div>", unsafe_allow_html=True)
            
        st.components.v1.html(m._repr_html_(), height=550)
        
        st.markdown("<h3 class='section-header'>📥 Export Documentation</h3>", unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        
        if master_itinerary:
            # EXCEL EXPORT
            df_manifest = pd.DataFrame(master_itinerary)
            excel_out = io.BytesIO()
            with pd.ExcelWriter(excel_out, engine='openpyxl') as writer:
                df_manifest.to_excel(writer, index=False, sheet_name='Optimized Routes')
            with dl_col1:
                st.download_button("⬇️ Download Route Manifest (.xlsx)", excel_out.getvalue(), 
                                   "KEP_Intelligent_Route_Manifest.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # PDF EXPORT (FULLY BRANDED)
            valid_drops_for_pdf = [r for r in master_itinerary if r['Original Search'] != 'KEP DEPOT']
            if valid_drops_for_pdf:
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                delivery_date_str = delivery_date.strftime("%d/%m/%Y")
                
                for row in valid_drops_for_pdf:
                    address = row['Full Completed Address']
                    for copy_type in ["DRIVER COPY", "CUSTOMER COPY"]:
                        pdf.add_page()
                        
                        # --- HEADER BLOCK ---
                        try:
                            pdf.image("keplogo.png", x=10, y=10, w=45)
                        except Exception:
                            try:
                                pdf.image("keplogo.svg", x=10, y=10, w=45)
                            except Exception:
                                pdf.set_font("helvetica", "B", 24)
                                pdf.set_text_color(0, 75, 135)
                                pdf.cell(0, 10, "KEP PRINT GROUP", ln=0, align="L")
                        
                        pdf.set_font("helvetica", "B", 24)
                        pdf.set_text_color(0, 75, 135) # KEP Blue
                        pdf.set_xy(100, 15)
                        pdf.cell(100, 10, "DELIVERY NOTE", ln=0, align="R")
                        
                        pdf.set_font("helvetica", "B", 12)
                        pdf.set_text_color(120, 120, 120)
                        pdf.set_xy(100, 25)
                        pdf.cell(100, 6, copy_type, ln=1, align="R")
                        
                        pdf.ln(10)
                        pdf.set_draw_color(0, 75, 135)
                        pdf.set_line_width(0.6)
                        pdf.line(10, 38, 200, 38)
                        pdf.set_line_width(0.2)
                        
                        # --- ADDRESS & METADATA GRID ---
                        pdf.set_y(45)
                        pdf.set_font("helvetica", "B", 11)
                        pdf.set_text_color(0, 75, 135)
                        pdf.cell(100, 6, "DELIVER TO:", ln=0)
                        pdf.cell(90, 6, "DELIVERY DETAILS:", ln=1)
                        
                        start_y = pdf.get_y()
                        
                        # Left Col: Address
                        pdf.set_font("helvetica", "", 10)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_xy(10, start_y)
                        for part in address.split(','):
                            if part.strip(): 
                                pdf.cell(90, 5, part.strip(), ln=2)
                        
                        # Right Col: Meta Data
                        pdf.set_xy(110, start_y)
                        ref_no = f"{job_number}-{row['Stop Sequence']}" if job_number else f"SEQ-{row['Stop Sequence']}"
                        
                        meta_data = [
                            ("Note No:", ref_no),
                            ("Date:", delivery_date_str),
                            ("Method:", "KEP Van"),
                            ("Job No:", job_number),
                            ("Cust Ref:", ""),
                            ("Consignment:", "")
                        ]
                        
                        for label, val in meta_data:
                            pdf.set_x(110)
                            pdf.set_font("helvetica", "B", 9)
                            pdf.set_text_color(100, 100, 100)
                            pdf.cell(25, 5, label, border=0)
                            pdf.set_font("helvetica", "", 9)
                            pdf.set_text_color(0, 0, 0)
                            pdf.cell(65, 5, str(val), border=0, ln=1)
                            
                        # --- ITEMS TABLE ---
                        # Table Header (Blue Fill)
                        pdf.set_y(max(pdf.get_y(), 95))
                        pdf.set_fill_color(0, 75, 135)
                        pdf.set_text_color(255, 255, 255)
                        pdf.set_draw_color(0, 75, 135)
                        pdf.set_font("helvetica", "B", 9)
                        pdf.cell(100, 8, " Job Title / Description", border=1, fill=True)
                        pdf.cell(30, 8, "Qty Delivered", border=1, align="C", fill=True)
                        pdf.cell(30, 8, "No. of", border=1, align="C", fill=True)
                        pdf.cell(30, 8, "Qty per Unit", border=1, ln=1, align="C", fill=True)
                        
                        # Table Row
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_draw_color(200, 200, 200)
                        pdf.set_font("helvetica", "", 9)
                        pdf.cell(100, 10, f" {job_desc}", border=1)
                        pdf.cell(30, 10, str(job_qty) if job_qty else "", border=1, align="C")
                        pdf.cell(30, 10, "0", border=1, align="C")
                        pdf.cell(30, 10, "0", border=1, ln=1, align="C")
                        
                        # --- SIGNATURE BOX ---
                        pdf.ln(25)
                        pdf.set_fill_color(248, 249, 250)
                        pdf.set_draw_color(220, 220, 220)
                        box_y = pdf.get_y()
                        pdf.rect(10, box_y, 190, 40, style="DF")
                        
                        pdf.set_xy(15, box_y + 5)
                        pdf.set_font("helvetica", "B", 10)
                        pdf.set_text_color(0, 75, 135)
                        pdf.cell(0, 6, "GOODS RECEIVED IN GOOD CONDITION", ln=1)
                        
                        pdf.ln(2)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font("helvetica", "B", 9)
                        
                        pdf.set_x(15)
                        pdf.cell(20, 8, "Print Name:")
                        pdf.line(35, pdf.get_y()+6, 100, pdf.get_y()+6)
                        pdf.ln(10)
                        
                        pdf.set_x(15)
                        pdf.cell(20, 8, "Signature:")
                        pdf.line(35, pdf.get_y()+6, 100, pdf.get_y()+6)
                        
                        pdf.set_xy(120, pdf.get_y())
                        pdf.cell(10, 8, "Date:")
                        pdf.line(130, pdf.get_y()+6, 190, pdf.get_y()+6)
                        
                        # --- FOOTER ---
                        pdf.set_y(-25)
                        pdf.set_font("helvetica", "", 9)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(0, 5, "KEP Print Group | Two Gates Trading Estate, Tamworth B77 5AE | www.kep.co.uk", align="C", ln=1)
                        pdf.set_font("helvetica", "I", 8)
                        pdf.cell(0, 5, f"In case of queries please call 01827 280880 and quote reference {ref_no}", align="C", ln=1)
                        
                try: pdf_bytes = bytes(pdf.output())
                except Exception: pdf_bytes = pdf.output(dest="S").encode("latin-1")
                    
                with dl_col2:
                    st.download_button("⬇️ Download Delivery Notes (.pdf)", pdf_bytes, 
                                       f"KEP_Delivery_Notes_{job_number}.pdf" if job_number else "KEP_Delivery_Notes.pdf", "application/pdf")

    elif not calculate_btn:
        st.info("👈 Set your parameters and locations, then compile to generate the KEP logistics plan.")
