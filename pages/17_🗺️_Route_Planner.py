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

    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}

    .kep-banner {
        background-color: white; padding: 2rem 2.5rem; border-radius: 12px;
        margin-top: -2rem; margin-bottom: 2rem; border-top: 8px solid #004B87;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }
    .kep-banner h1 { color: #004B87 !important; margin: 0.5rem 0 0.2rem 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.5px; }
    .kep-banner p { margin: 0; color: #555; font-size: 1.1rem; font-weight: 400; }

    .section-header {
        color: #004B87; font-weight: 800; font-size: 1.3rem; margin-top: 1.5rem; margin-bottom: 1.2rem;
        border-bottom: 2px solid #edf2f7; padding-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;
    }

    .metric-card {
        background: white; padding: 24px; border-radius: 10px; border-left: 6px solid #004B87;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04); text-align: left; margin-bottom: 20px; transition: transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); }
    .metric-card h4 { margin: 0 0 8px 0; color: #8898aa; font-size: 0.9rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    .stat-text { color: #004B87; font-size: 32px; font-weight: 800; margin: 0; }

    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stDateInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        border: 1px solid #cbd5e0 !important; border-radius: 6px !important; background-color: #f8fafc !important; transition: all 0.2s ease;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus, .stDateInput>div>div>input:focus, .stNumberInput>div>div>input:focus {
        border-color: #004B87 !important; background-color: white !important; box-shadow: 0 0 0 1px #004B87 !important;
    }

    .stButton>button {
        background: linear-gradient(135deg, #004B87 0%, #002D54 100%); color: white !important; border-radius: 8px;
        font-weight: 600 !important; padding: 0.8rem 1.5rem; width: 100%; border: none; font-size: 1.1rem;
        box-shadow: 0 4px 14px rgba(0, 75, 135, 0.25); transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #00569b 0%, #003666 100%); box-shadow: 0 6px 20px rgba(0, 75, 135, 0.4); transform: translateY(-1px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- CUSTOM BRANDED HEADER ---
logo_path = "keplogo.png" if os.path.exists("keplogo.png") else "keplogo.svg" if os.path.exists("keplogo.svg") else None

st.markdown("<div class='kep-banner'>", unsafe_allow_html=True)
if logo_path:
    st.image(logo_path, width=180)
st.markdown("""
    <h1>Intelligent Fleet Router</h1>
    <p>Automatically scales your fleet to minimize costs while respecting legal shift hours and vehicle capacities.</p>
    </div>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def extract_location_data(text):
    text = text.strip()
    pc_pattern = r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})'
    weight = 0.0
    
    w_pattern = r'(?:([,:\|\-])\s*([0-9]+(?:\.[0-9]+)?)\s*(?:kg|kilos)?|\b([0-9]+(?:\.[0-9]+)?)\s*(?:kg|kilos))\s*$'
    w_match = re.search(w_pattern, text, re.IGNORECASE)
    
    if w_match:
        weight_str = w_match.group(2) if w_match.group(2) else w_match.group(3)
        weight = float(weight_str)
        text = text[:w_match.start()].strip(" ,:-|")
            
    pc_match = re.search(pc_pattern, text, re.IGNORECASE)
    pc = pc_match.group(1).upper() if pc_match else None
    
    return {'clean_query': text, 'postcode': pc, 'weight': weight}

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

def capacitated_clustering(points, k, max_weight, force_assign=False):
    if k == 1:
        total = sum(p['weight'] for p in points)
        return {0: points}, (total <= max_weight or force_assign)

    coords = [[p['lat'], p['lon']] for p in points]
    kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
    kmeans.fit(coords)
    centers = kmeans.cluster_centers_
    
    assignments = {i: [] for i in range(k)}
    weights = {i: 0.0 for i in range(k)}
    
    sorted_points = sorted(points, key=lambda x: x['weight'], reverse=True)
    
    success = True
    for p in sorted_points:
        p_coord = np.array([p['lat'], p['lon']])
        dists = [np.linalg.norm(p_coord - c) for c in centers]
        sorted_centers = np.argsort(dists)
        
        assigned = False
        for c_idx in sorted_centers:
            if weights[c_idx] + p['weight'] <= max_weight:
                assignments[c_idx].append(p)
                weights[c_idx] += p['weight']
                assigned = True
                break
        
        if not assigned:
            success = False
            if force_assign:
                best_c = sorted_centers[0]
                assignments[best_c].append(p)
                weights[best_c] += p['weight']
            else:
                return assignments, False
                
    return assignments, success

def generate_pallet_labels(master_itinerary, labels_per_addr, template_type, job_number, job_desc):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    
    # Configure A4 Grid based on user selection
    if template_type == "1 Up":
        cols, rows = 1, 1
        w, h = 190, 277
        start_x, start_y = 10, 10
        gap_x, gap_y = 0, 0
    elif template_type == "2 Up":
        cols, rows = 1, 2
        w, h = 190, 138
        start_x, start_y = 10, 10
        gap_x, gap_y = 0, 5
    elif template_type == "10 Up":
        cols, rows = 2, 5
        w, h = 95, 55
        start_x, start_y = 10, 10
        gap_x, gap_y = 5, 5
    else: # "21 Up"
        cols, rows = 3, 7
        w, h = 63.5, 38.1
        start_x, start_y = 7, 13
        gap_x, gap_y = 2.5, 0

    # Expand list based on required quantity per drop
    labels = []
    for row in master_itinerary:
        if row['Original Search'] != 'KEP DEPOT':
            for _ in range(labels_per_addr):
                labels.append(row)
    
    labels_per_page = cols * rows
    
    for i, lbl in enumerate(labels):
        if i % labels_per_page == 0:
            pdf.add_page()
        
        idx_on_page = i % labels_per_page
        col = idx_on_page % cols
        row_idx = idx_on_page // cols
        
        x = start_x + col * (w + gap_x)
        y = start_y + row_idx * (h + gap_y)
        
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(x, y, w, h)
        pdf.set_xy(x + 3, y + 3)
        
        if template_type in ["1 Up", "2 Up"]:
            pdf.set_font("helvetica", "B", 16)
            pdf.cell(w-6, 8, f"KEP PRINT GROUP", ln=2)
            pdf.set_font("helvetica", "", 12)
            pdf.cell(w-6, 6, f"Job: {job_number} - {job_desc}", ln=2)
            pdf.ln(4)
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(w-6, 8, "DELIVER TO:", ln=2)
            pdf.set_font("helvetica", "", 12)
            for part in lbl['Full Completed Address'].split(','):
                if part.strip():
                    pdf.cell(w-6, 6, part.strip(), ln=2)
            
            # Corporate Tagline at bottom of large formats
            pdf.set_xy(x + 3, y + h - 10)
            pdf.set_font("helvetica", "I", 10)
            pdf.set_text_color(0, 75, 135)
            pdf.cell(w-6, 6, "Print Just Perfected.", align="C")
            pdf.set_text_color(0, 0, 0)
            
        elif template_type == "10 Up":
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(w-6, 5, f"Job: {job_number}", ln=2)
            pdf.set_font("helvetica", "", 8)
            pdf.cell(w-6, 4, f"{job_desc[:40]}", ln=2)
            pdf.ln(2)
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(w-6, 5, "DELIVER TO:", ln=2)
            pdf.set_font("helvetica", "", 8)
            for part in lbl['Full Completed Address'].split(',')[:4]:
                if part.strip():
                    pdf.cell(w-6, 4, part.strip()[:40], ln=2)
                    
        else: # 21 Up
            pdf.set_font("helvetica", "B", 8)
            pdf.cell(w-6, 4, f"Job: {job_number}", ln=2)
            pdf.set_font("helvetica", "B", 7)
            pdf.cell(w-6, 3, "DELIVER TO:", ln=2)
            pdf.set_font("helvetica", "", 7)
            for part in lbl['Full Completed Address'].split(',')[:3]:
                if part.strip():
                    pdf.cell(w-6, 3, part.strip()[:35], ln=2)

    try: return bytes(pdf.output())
    except Exception: return pdf.output(dest="S").encode("latin-1")

# --- INTERFACE ---
col_inputs, col_map = st.columns([1, 2], gap="large")

with col_inputs:
    st.markdown("<h3 class='section-header'>📍 Fleet Parameters</h3>", unsafe_allow_html=True)
    depot_postcode = st.text_input("Depot Postcode (Start & End)", value="B77 5AE")
    
    raw_locations = st.text_area("Paste Locations & Weights (e.g. M&S Banbury: 400kg)", height=150, 
                                 placeholder="e.g.\nCV1 2HN, 250\nTamworth High School B77 3AA\nM&S Banbury: 400kg")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1: max_vans = st.slider("Max Available Vans", min_value=1, max_value=5, value=3)
    with col_f2: max_weight = st.number_input("Max Weight / Van (kg)", value=1000, step=100)
    
    st.markdown("<h3 class='section-header'>📝 Manifest Data</h3>", unsafe_allow_html=True)
    col_dn1, col_dn2 = st.columns(2)
    with col_dn1:
        job_number = st.text_input("Job Number", placeholder="e.g. 355814")
        delivery_date = st.date_input("Delivery Date", datetime.date.today())
    with col_dn2:
        job_qty = st.text_input("Quantity Delivered", placeholder="e.g. 300")
    job_desc = st.text_input("Job Title / Description", placeholder="e.g. Perm POS - Hand Washing...")
    
    st.markdown("<h3 class='section-header'>🏷️ Label Configuration</h3>", unsafe_allow_html=True)
    col_lbl1, col_lbl2 = st.columns(2)
    with col_lbl1:
        lbl_qty = st.number_input("Labels per Address", min_value=1, value=1)
    with col_lbl2:
        lbl_format = st.selectbox("Label Template", ["1 Up", "2 Up", "10 Up", "21 Up"])
    
    st.markdown("<br>", unsafe_allow_html=True)
    calculate_btn = st.button("🗺️ Optimize Fleet & Generate Docs")

with col_map:
    st.markdown("<h3 class='section-header'>🗺️ Interactive Route Map</h3>", unsafe_allow_html=True)
    
    if calculate_btn and raw_locations.strip():
        raw_list = [p.strip() for p in raw_locations.split('\n') if p.strip()]
        
        parsed_drops = {}
        with_postcodes_map = {} 
        place_names_only = []
        
        for raw_loc in raw_list:
            data = extract_location_data(raw_loc)
            clean_q = data['clean_query']
            parsed_drops[clean_q] = data
            
            if data['postcode']: with_postcodes_map[clean_q] = data['postcode']
            else: place_names_only.append(clean_q)
        
        depot_pc_extracted = extract_location_data(depot_postcode)['postcode'] or depot_postcode
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
        
        valid_drops, failed_drops = [], []
        for raw_loc in raw_list:
            clean_q = extract_location_data(raw_loc)['clean_query']
            if clean_q in drop_data:
                valid_drops.append({
                    'query': clean_q, 'lat': drop_data[clean_q]['lat'], 'lon': drop_data[clean_q]['lon'],
                    'full_address': drop_data[clean_q]['full_address'], 'postcode': drop_data[clean_q]['postcode'],
                    'weight': parsed_drops[clean_q]['weight']
                })
            else: failed_drops.append(raw_loc)
                
        if failed_drops: st.warning(f"Could not find coordinates for: {', '.join(failed_drops)}")
        if not valid_drops:
            st.error("No valid locations found to route.")
            status_container.empty()
            st.stop()

        # --- FLEET OPTIMIZER ENGINE ---
        DROP_TIME_HOURS = 15 / 60.0  
        FLEX_LIMIT_HOURS = 11.5      
        
        best_routes_data = {}
        optimal_vans_used = 1
        
        for k in range(1, max_vans + 1):
            status_container.text(f"Testing physical capacities & shift limits for {k} van(s)...")
            actual_k = min(k, len(valid_drops))
            is_last_attempt = (k == max_vans)
            
            temp_assignments, weight_ok = capacitated_clustering(valid_drops, actual_k, max_weight, force_assign=is_last_attempt)
            
            if not weight_ok and not is_last_attempt: continue 
                
            plan_valid = True
            temp_routes_data = {}
            max_van_time_in_plan = 0
            
            for van_id, drops in temp_assignments.items():
                if not drops: continue
                depot_block = {
                    'query': 'KEP DEPOT', 'full_address': f'KEP Print Group, {depot_postcode}', 
                    'postcode': depot_pc_extracted, 'lat': depot_lat, 'lon': depot_lon, 'weight': 0.0
                }
                
                input_points = [depot_block] + drops
                coords_str = ";".join([f"{p['lon']},{p['lat']}" for p in input_points])
                url = f"http://router.project-osrm.org/trip/v1/driving/{coords_str}?source=first&roundtrip=true&geometries=geojson"
                
                try:
                    resp = requests.get(url)
                    data = resp.json()
                    if data.get('code') == 'Ok':
                        route = data['trips'][0]
                        drive_hours = route['duration'] / 3600 
                        miles = route['distance'] / 1609.34
                        total_shift_time = drive_hours + (len(drops) * DROP_TIME_HOURS)
                        
                        if total_shift_time > max_van_time_in_plan: max_van_time_in_plan = total_shift_time
                            
                        temp_routes_data[van_id] = {
                            'route_geom': route['geometry'], 'waypoints': data['waypoints'],
                            'miles': miles, 'drive_hours': drive_hours, 'total_shift_time': total_shift_time,
                            'input_points': input_points
                        }
                    else: plan_valid = False
                except Exception: plan_valid = False
            
            if plan_valid and max_van_time_in_plan <= FLEX_LIMIT_HOURS:
                best_routes_data = temp_routes_data
                optimal_vans_used = actual_k
                break 
            
            if k == max_vans:
                best_routes_data = temp_routes_data
                optimal_vans_used = actual_k

        status_container.empty()
        
        if optimal_vans_used < max_vans:
            st.success(f"🤖 **Fleet Intelligence:** Successfully compacted the route into {optimal_vans_used} van(s), protecting payload limits and saving deployment costs.")
        else:
            st.info(f"🤖 **Fleet Intelligence:** Maxed out all {optimal_vans_used} available vans to handle the heavy payload and high workload.")

        # --- MAP RENDERING ---
        m = folium.Map(location=[depot_lat, depot_lon], zoom_start=6)
        folium.Marker([depot_lat, depot_lon], popup="KEP Depot", icon=folium.Icon(color="black", icon="home")).add_to(m)
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        total_miles, total_hours = 0, 0
        master_itinerary = []
        
        for van_id, r_data in best_routes_data.items():
            color = colors[van_id % len(colors)]
            miles, drive_hours, shift_hours = r_data['miles'], r_data['drive_hours'], r_data['total_shift_time']
            input_points = r_data['input_points']
            
            total_miles += miles
            total_hours += drive_hours
            
            folium.GeoJson(
                r_data['route_geom'], name=f"Van {van_id+1}",
                style_function=lambda x, c=color: {'color': c, 'weight': 5, 'opacity': 0.8}
            ).add_to(m)
            
            for i, wp in enumerate(r_data['waypoints']): input_points[i]['sequence'] = wp['waypoint_index']
            optimized_drops = sorted(input_points, key=lambda x: x['sequence'])
            
            van_payload = sum(p['weight'] for p in optimized_drops)
            
            for i, p in enumerate(optimized_drops):
                master_itinerary.append({
                    "Van / Run": f"Van {van_id+1}", "Stop Sequence": i + 1,
                    "Original Search": p['query'], "Extracted Postcode": p['postcode'],
                    "Full Completed Address": p['full_address'], "Payload (kg)": p.get('weight', 0.0)
                })
            
            st.markdown(f"**🚐 Van {van_id+1} Route** — Shift: {int(shift_hours)}h {int((shift_hours % 1) * 60)}m | Payload: **{van_payload} kg** | Mileage: {miles:.1f} mi")
            df_display = pd.DataFrame({
                "Stop": range(1, len(optimized_drops) + 1), "Search": [p['query'] for p in optimized_drops],
                "Weight (kg)": [p.get('weight', 0.0) for p in optimized_drops]
            })
            st.dataframe(df_display, hide_index=True, use_container_width=True)
            
            for i, p in enumerate(optimized_drops):
                if p['query'] != 'KEP DEPOT':
                    folium.Marker(
                        [p['lat'], p['lon']], popup=f"Stop {i+1}: {p['query']} ({p.get('weight', 0)}kg)",
                        tooltip=p['full_address'], icon=folium.Icon(color=color, icon="info-sign")
                    ).add_to(m)
        
        st.markdown("<br>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1: st.markdown(f"<div class='metric-card'><h4>Total Campaign Mileage</h4><p class='stat-text'>{total_miles:.1f} mi</p></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='metric-card'><h4>Total Driving Time</h4><p class='stat-text'>{int(total_hours)}h {int((total_hours % 1) * 60)}m</p></div>", unsafe_allow_html=True)
            
        st.components.v1.html(m._repr_html_(), height=550)
        
        st.markdown("<h3 class='section-header'>📥 Export Documentation</h3>", unsafe_allow_html=True)
        
        # Switched to 3 columns to fit the new Labels button
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        
        if master_itinerary:
            # 1. EXCEL EXPORT
            df_manifest = pd.DataFrame(master_itinerary)
            excel_out = io.BytesIO()
            with pd.ExcelWriter(excel_out, engine='openpyxl') as writer:
                df_manifest.to_excel(writer, index=False, sheet_name='Optimized Routes')
            with dl_col1:
                st.download_button("⬇️ Route Manifest (.xlsx)", excel_out.getvalue(), 
                                   "KEP_Intelligent_Route_Manifest.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # 2. PDF EXPORT (DELIVERY NOTES)
            valid_drops_for_pdf = [r for r in master_itinerary if r['Original Search'] != 'KEP DEPOT']
            if valid_drops_for_pdf:
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                delivery_date_str = delivery_date.strftime("%d/%m/%Y")
                
                for row in valid_drops_for_pdf:
                    address = row['Full Completed Address']
                    for copy_type in ["DRIVER COPY", "CUSTOMER COPY"]:
                        pdf.add_page()
                        try: pdf.image("keplogo.png", x=10, y=10, w=45)
                        except Exception:
                            try: pdf.image("keplogo.svg", x=10, y=10, w=45)
                            except Exception:
                                pdf.set_font("helvetica", "B", 24)
                                pdf.set_text_color(0, 75, 135)
                                pdf.cell(0, 10, "KEP PRINT GROUP", ln=0, align="L")
                        
                        pdf.set_font("helvetica", "B", 24)
                        pdf.set_text_color(0, 75, 135)
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
                        
                        pdf.set_y(45)
                        pdf.set_font("helvetica", "B", 11)
                        pdf.set_text_color(0, 75, 135)
                        pdf.cell(100, 6, "DELIVER TO:", ln=0)
                        pdf.cell(90, 6, "DELIVERY DETAILS:", ln=1)
                        
                        start_y = pdf.get_y()
                        pdf.set_font("helvetica", "", 10)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_xy(10, start_y)
                        for part in address.split(','):
                            if part.strip(): pdf.cell(90, 5, part.strip(), ln=2)
                        
                        pdf.set_xy(110, start_y)
                        ref_no = f"{job_number}-{row['Stop Sequence']}" if job_number else f"SEQ-{row['Stop Sequence']}"
                        
                        meta_data = [
                            ("Note No:", ref_no), ("Date:", delivery_date_str), ("Method:", "KEP Van"),
                            ("Job No:", job_number), ("Cust Ref:", ""), ("Consignment:", "")
                        ]
                        for label, val in meta_data:
                            pdf.set_x(110)
                            pdf.set_font("helvetica", "B", 9)
                            pdf.set_text_color(100, 100, 100)
                            pdf.cell(25, 5, label, border=0)
                            pdf.set_font("helvetica", "", 9)
                            pdf.set_text_color(0, 0, 0)
                            pdf.cell(65, 5, str(val), border=0, ln=1)
                            
                        pdf.set_y(max(pdf.get_y(), 95))
                        pdf.set_fill_color(0, 75, 135)
                        pdf.set_text_color(255, 255, 255)
                        pdf.set_draw_color(0, 75, 135)
                        pdf.set_font("helvetica", "B", 9)
                        pdf.cell(100, 8, " Job Title / Description", border=1, fill=True)
                        pdf.cell(30, 8, "Qty Delivered", border=1, align="C", fill=True)
                        pdf.cell(30, 8, "No. of", border=1, align="C", fill=True)
                        pdf.cell(30, 8, "Qty per Unit", border=1, ln=1, align="C", fill=True)
                        
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_draw_color(200, 200, 200)
                        pdf.set_font("helvetica", "", 9)
                        pdf.cell(100, 10, f" {job_desc}", border=1)
                        pdf.cell(30, 10, str(job_qty) if job_qty else "", border=1, align="C")
                        pdf.cell(30, 10, "0", border=1, align="C")
                        pdf.cell(30, 10, "0", border=1, ln=1, align="C")
                        
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
                        
                        pdf.set_y(-25)
                        pdf.set_font("helvetica", "", 9)
                        pdf.set_text_color(100, 100, 100)
                        pdf.cell(0, 5, "KEP Print Group | Two Gates Trading Estate, Tamworth B77 5AE | www.kep.co.uk", align="C", ln=1)
                        pdf.set_font("helvetica", "I", 8)
                        pdf.cell(0, 5, f"In case of queries please call 01827 280880 and quote reference {ref_no}", align="C", ln=1)
                        
                try: pdf_bytes = bytes(pdf.output())
                except Exception: pdf_bytes = pdf.output(dest="S").encode("latin-1")
                    
                with dl_col2:
                    st.download_button("⬇️ Delivery Notes (.pdf)", pdf_bytes, 
                                       f"KEP_Delivery_Notes_{job_number}.pdf" if job_number else "KEP_Delivery_Notes.pdf", "application/pdf")
            
            # 3. PDF EXPORT (PALLET LABELS)
            labels_pdf_bytes = generate_pallet_labels(master_itinerary, lbl_qty, lbl_format, job_number, job_desc)
            with dl_col3:
                st.download_button("⬇️ Pallet Labels (.pdf)", labels_pdf_bytes, 
                                   f"KEP_Labels_{job_number}.pdf" if job_number else "KEP_Labels.pdf", "application/pdf")

    elif not calculate_btn:
        st.info("👈 Set your parameters and locations, then compile to generate the KEP logistics plan.")
