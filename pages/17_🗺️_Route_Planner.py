import streamlit as st
import pandas as pd
import requests
import folium
from sklearn.cluster import KMeans
import numpy as np
import io
import re
import time
from fpdf import FPDF
import datetime

st.set_page_config(page_title="Route Planner", page_icon="🗺️", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px;}
    .stat-text { color: #004B87; font-size: 28px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; font-size: 16px;}
    .stButton>button:hover { background-color: #003666; color: white; }
    .section-header { color: #004B87; margin-top: 10px; margin-bottom: 10px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

st.title("🗺️ Dispatch Route & Delivery Note Planner")
st.write("Calculate the optimal driving sequence and instantly generate driver manifests and customer delivery notes.")
st.divider()

# --- HELPER FUNCTIONS ---
def extract_postcode(text):
    """Scans text and extracts a UK postcode if one exists anywhere in the string."""
    pattern = r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def geocode_postcodes_bulk(postcode_map):
    """Fast geocoder taking a dictionary of {Original_String: Extracted_Postcode}"""
    results = {}
    headers = {"Content-Type": "application/json"}
    unique_pcs = list(set(postcode_map.values()))
    
    for i in range(0, len(unique_pcs), 100):
        chunk = unique_pcs[i:i+100]
        try:
            resp = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": chunk}, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('result', [])
                pc_data_lookup = {}
                for item in data:
                    if item['result']:
                        pc_data_lookup[item['query']] = item['result']
                        
                for original_str, extracted_pc in postcode_map.items():
                    if extracted_pc in pc_data_lookup:
                        res = pc_data_lookup[extracted_pc]
                        name_part = original_str.replace(extracted_pc, "").strip(" ,-")
                        display_addr = f"{name_part}, {extracted_pc}, {res.get('admin_district', '')}".strip(" ,")
                        if not name_part: 
                             display_addr = f"{extracted_pc}, {res.get('admin_district', '')}".strip(" ,")
                        results[original_str] = {
                            'lat': res['latitude'],
                            'lon': res['longitude'],
                            'full_address': display_addr,
                            'postcode': res['postcode']
                        }
        except Exception:
            pass
    return results

def geocode_places_osm(place_list, progress_bar, status_text):
    """Smart text-search geocoder for locations with NO postcode provided."""
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
                        'lat': float(best_match['lat']),
                        'lon': float(best_match['lon']),
                        'full_address': full_addr,
                        'postcode': pc
                    }
            time.sleep(1)
        except Exception:
            pass
    return results

# --- INTERFACE ---
col_inputs, col_map = st.columns([1, 2], gap="large")

with col_inputs:
    st.markdown("<h3 class='section-header'>📍 1. Route Details</h3>", unsafe_allow_html=True)
    depot_postcode = st.text_input("Depot Postcode (Start & End)", value="B77 5AE")
    
    raw_locations = st.text_area("Paste Locations (Names or Postcodes)", height=180, 
                                 placeholder="e.g.\nCV1 2HN\nTamworth High School B77 3AA\nM&S Banbury")
    num_vans = st.slider("Number of Vans / Runs", min_value=1, max_value=5, value=1)
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    
    st.markdown("<h3 class='section-header'>📝 2. Delivery Note Data</h3>", unsafe_allow_html=True)
    
    # Use side-by-side layout for smaller inputs to save vertical space
    col_dn1, col_dn2 = st.columns(2)
    with col_dn1:
        job_number = st.text_input("Job Number", placeholder="e.g. 355814")
        delivery_date = st.date_input("Delivery Date", datetime.date.today())
    with col_dn2:
        job_qty = st.text_input("Quantity Delivered", placeholder="e.g. 300 (Blank for none)")
        
    job_desc = st.text_input("Job Title / Description", placeholder="e.g. Perm POS - Hand Washing...")
    
    st.markdown("<br>", unsafe_allow_html=True)
    calculate_btn = st.button("🗺️ Optimize Route & Generate Docs")

with col_map:
    st.markdown("<h3 class='section-header'>🗺️ 3. Itinerary & Map</h3>", unsafe_allow_html=True)
    
    if calculate_btn and raw_locations.strip():
        raw_list = [p.strip() for p in raw_locations.split('\n') if p.strip()]
        raw_list = list(set(raw_list)) 
        
        with_postcodes_map = {} 
        place_names_only = []
        
        for loc in raw_list:
            found_pc = extract_postcode(loc)
            if found_pc:
                with_postcodes_map[loc] = found_pc
            else:
                place_names_only.append(loc)
        
        depot_pc_extracted = extract_postcode(depot_postcode) or depot_postcode
        depot_data = geocode_postcodes_bulk({depot_postcode: depot_pc_extracted})
        
        if depot_postcode not in depot_data:
            st.error("Could not find the Depot postcode. Please check the format.")
            st.stop()
        
        depot_lat = depot_data[depot_postcode]['lat']
        depot_lon = depot_data[depot_postcode]['lon']
        
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
        
        valid_drops = []
        failed_drops = []
        for loc in raw_list:
            if loc in drop_data:
                valid_drops.append({
                    'query': loc, 
                    'lat': drop_data[loc]['lat'], 
                    'lon': drop_data[loc]['lon'],
                    'full_address': drop_data[loc]['full_address'],
                    'postcode': drop_data[loc]['postcode']
                })
            else:
                failed_drops.append(loc)
                
        if failed_drops:
            st.warning(f"Could not find coordinates for: {', '.join(failed_drops)}")
            
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
        else:
            van_assignments[0] = valid_drops
            
        m = folium.Map(location=[depot_lat, depot_lon], zoom_start=6)
        folium.Marker([depot_lat, depot_lon], popup="KEP Depot", icon=folium.Icon(color="black", icon="home")).add_to(m)
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        total_miles = 0
        total_hours = 0
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
                        style_function=lambda x, c=color: {'color': c, 'weight': 4, 'opacity': 0.8}
                    ).add_to(m)
                    
                    for i, wp in enumerate(waypoints):
                        input_points[i]['sequence'] = wp['waypoint_index']
                        
                    optimized_drops = sorted(input_points, key=lambda x: x['sequence'])
                    
                    for i, p in enumerate(optimized_drops):
                        master_itinerary.append({
                            "Van / Run": f"Van {van_id+1}",
                            "Stop Sequence": i + 1,
                            "Original Search": p['query'],
                            "Extracted Postcode": p['postcode'],
                            "Full Completed Address": p['full_address']
                        })
                    
                    st.markdown(f"### 🚐 Van {van_id+1} Itinerary")
                    st.write(f"**Est. Drive Time:** {int(duration)}h {int((duration % 1) * 60)}m | **Est. Mileage:** {miles:.1f} miles")
                    
                    df_display = pd.DataFrame({
                        "Stop": range(1, len(optimized_drops) + 1),
                        "Search": [p['query'] for p in optimized_drops],
                        "Address Found": [p['full_address'] for p in optimized_drops]
                    })
                    st.dataframe(df_display, hide_index=True, use_container_width=True)
                    
                    for i, p in enumerate(optimized_drops):
                        if p['query'] != 'KEP DEPOT':
                            folium.Marker(
                                [p['lat'], p['lon']], popup=f"Stop {i+1}: {p['query']}",
                                tooltip=p['full_address'], icon=folium.Icon(color=color, icon="info-sign")
                            ).add_to(m)
                else:
                    st.error(f"Routing engine failed for Van {van_id+1}.")
            except Exception as e:
                st.error(f"Could not calculate exact road route for Van {van_id+1}.")
        
        status_container.empty()
        
        # --- RENDER TOP LEVEL METRICS & EXPORT ---
        st.divider()
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"<div class='metric-card'><h4>Total Campaign Mileage</h4><p class='stat-text'>{total_miles:.1f} mi</p></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><h4>Total Driving Time</h4><p class='stat-text'>{int(total_hours)}h {int((total_hours % 1) * 60)}m</p></div>", unsafe_allow_html=True)
            
        st.components.v1.html(m._repr_html_(), height=600)
        st.divider()

        # --- EXPORT GENERATION ---
        st.subheader("4. Document Exports")
        dl_col1, dl_col2 = st.columns(2)
        
        if master_itinerary:
            # 1. EXCEL MANIFEST
            df_manifest = pd.DataFrame(master_itinerary)
            excel_out = io.BytesIO()
            with pd.ExcelWriter(excel_out, engine='openpyxl') as writer:
                df_manifest.to_excel(writer, index=False, sheet_name='Optimized Routes')
            
            with dl_col1:
                st.download_button(
                    label="⬇️ Download Excel Route Manifest",
                    data=excel_out.getvalue(),
                    file_name="KEP_Intelligent_Route_Manifest.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # 2. PDF DELIVERY NOTES
            valid_drops_for_pdf = [r for r in master_itinerary if r['Original Search'] != 'KEP DEPOT']
            
            if valid_drops_for_pdf:
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                
                # Format the chosen date directly from the UI Date Picker
                delivery_date_str = delivery_date.strftime("%d/%m/%Y")
                
                for row in valid_drops_for_pdf:
                    address = row['Full Completed Address']
                    
                    # Create the 2 copies for every location seamlessly
                    for copy_type in ["Driver Copy", "Customer Copy"]:
                        pdf.add_page()
                        
                        # LOGO HEADER
                        try:
                            pdf.image("keplogo.png", x=10, y=10, w=40)
                        except Exception:
                            try:
                                pdf.image("keplogo.svg", x=10, y=10, w=40)
                            except Exception:
                                pdf.set_font("helvetica", "B", 24)
                                pdf.set_text_color(0, 75, 135)
                                pdf.cell(0, 10, "KEP PRINT GROUP", ln=True, align="L")
                                pdf.set_text_color(0, 0, 0)
                                
                        pdf.ln(15)
                        pdf.set_font("helvetica", "B", 14)
                        pdf.set_text_color(0, 0, 0)
                        pdf.cell(0, 10, f"Delivery Note - {copy_type}", ln=True, align="L")
                        pdf.ln(5)
                        
                        # ADDRESS BLOCK
                        pdf.set_font("helvetica", "B", 10)
                        pdf.cell(0, 6, "Deliver to", ln=True)
                        pdf.set_font("helvetica", "", 10)
                        
                        addr_parts = address.split(',')
                        for part in addr_parts:
                            if part.strip():
                                pdf.cell(0, 5, part.strip(), ln=True)
                        pdf.ln(8)
                        
                        # SYSTEM INFO BLOCK
                        col1 = 45
                        col2 = 100
                        
                        def info_row(label, val):
                            pdf.set_font("helvetica", "B", 10)
                            pdf.cell(col1, 8, label, border=1)
                            pdf.set_font("helvetica", "", 10)
                            pdf.cell(col2, 8, str(val), border=1, ln=True)

                        ref_no = f"{job_number}-{row['Stop Sequence']}" if job_number else f"SEQ-{row['Stop Sequence']}"
                        
                        info_row("Delivery Note No.", ref_no)
                        info_row("Delivery Date:", delivery_date_str)
                        info_row("Delivery Method", "KEP Van")
                        info_row("Job Number", job_number)
                        info_row("Customer Reference", "")
                        info_row("Consignment No", "")
                        pdf.ln(8)
                        
                        # PRODUCTION ITEMS BLOCK
                        pdf.set_font("helvetica", "B", 9)
                        pdf.cell(100, 8, "Job Title", border=1)
                        pdf.cell(30, 8, "Quantity Delivered", border=1, align="C")
                        pdf.cell(20, 8, "No. of", border=1, align="C")
                        pdf.cell(30, 8, "Quantity per Unit", border=1, ln=True, align="C")
                        
                        pdf.set_font("helvetica", "", 9)
                        pdf.cell(100, 8, str(job_desc), border=1)
                        pdf.cell(30, 8, str(job_qty) if job_qty else "", border=1, align="C")
                        pdf.cell(20, 8, "0", border=1, align="C")
                        pdf.cell(30, 8, "0", border=1, ln=True, align="C")
                        
                        pdf.ln(20)
                        
                        # SIGN OFF BLOCK
                        pdf.set_font("helvetica", "B", 10)
                        pdf.cell(0, 8, "Goods received in good condition", ln=True)
                        pdf.set_font("helvetica", "", 10)
                        pdf.cell(0, 8, "Print Name: ___________________________", ln=True)
                        pdf.cell(0, 8, "Signature:  ___________________________", ln=True)
                        pdf.cell(0, 8, "Date:       ___________________________", ln=True)
                        
                        # FOOTER / QUERY
                        pdf.set_y(-30)
                        pdf.set_font("helvetica", "I", 9)
                        pdf.cell(0, 10, f"In case of queries please call 01827 280880 and quote the following reference number {ref_no}", ln=True, align="L")
                        
                # SAFE BYTE CONVERSION FOR STREAMLIT
                try:
                    pdf_bytes = bytes(pdf.output())
                except Exception:
                    pdf_bytes = pdf.output(dest="S").encode("latin-1")
                    
                with dl_col2:
                    st.download_button(
                        label="⬇️ Download Delivery Notes (PDF)",
                        data=pdf_bytes,
                        file_name=f"KEP_Delivery_Notes_{job_number}.pdf" if job_number else "KEP_Delivery_Notes.pdf",
                        mime="application/pdf"
                    )

    elif not calculate_btn:
        st.info("👈 Paste your locations and hit Optimize to generate the routes and delivery documentation.")
