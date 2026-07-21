import streamlit as st
import pandas as pd
import requests
import folium
from sklearn.cluster import KMeans
import numpy as np
import io
import re
import time

st.set_page_config(page_title="Route Planner", page_icon="🗺️", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px;}
    .stat-text { color: #004B87; font-size: 28px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 12px; width: 100%; border: none; font-size: 16px;}
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🗺️ Dispatch Route Planner")
st.write("Enter your delivery postcodes or store names to automatically generate the optimal driving sequence and map.")
st.divider()

# --- HELPER FUNCTIONS ---
def is_postcode(text):
    """Checks if a string strictly matches a UK postcode format."""
    pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}$'
    return bool(re.match(pattern, text.strip().upper()))

def geocode_postcodes_bulk(postcode_list):
    """Fast geocoder for actual postcodes."""
    results = {}
    headers = {"Content-Type": "application/json"}
    for i in range(0, len(postcode_list), 100):
        chunk = postcode_list[i:i+100]
        try:
            resp = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": chunk}, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('result', [])
                for item in data:
                    if item['result']:
                        pc = item['result']['postcode']
                        district = item['result'].get('admin_district', '')
                        results[item['query']] = {
                            'lat': item['result']['latitude'],
                            'lon': item['result']['longitude'],
                            'full_address': f"{pc}, {district}".strip(', '),
                            'postcode': pc
                        }
        except Exception:
            pass
    return results

def geocode_places_osm(place_list, progress_bar, status_text):
    """Smart text-search geocoder for place names (Schools, Pubs, etc)."""
    results = {}
    headers = {"User-Agent": "KEP_Print_Dispatch_Router/1.0"}
    
    total = len(place_list)
    for idx, place in enumerate(place_list):
        status_text.text(f"Searching database for '{place}'...")
        progress_bar.progress((idx + 1) / total)
        
        try:
            # Connect to OpenStreetMap free API (Restricted to GB to ensure accuracy)
            url = f"https://nominatim.openstreetmap.org/search?q={place}&format=json&addressdetails=1&countrycodes=gb"
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 0:
                    best_match = data[0]
                    addr = best_match.get('address', {})
                    pc = addr.get('postcode', 'N/A')
                    # Clean up the display name for the manifest
                    full_addr = best_match.get('display_name', place)
                    
                    results[place] = {
                        'lat': float(best_match['lat']),
                        'lon': float(best_match['lon']),
                        'full_address': full_addr,
                        'postcode': pc
                    }
            # OpenStreetMap requires a 1-second delay between free searches
            time.sleep(1)
        except Exception:
            pass
    return results

# --- INTERFACE ---
col_inputs, col_map = st.columns([1, 2], gap="large")

with col_inputs:
    st.subheader("1. Route Details")
    depot_postcode = st.text_input("Depot Postcode (Start & End)", value="B77 5AE")
    
    raw_locations = st.text_area("Paste Locations (Names or Postcodes)", height=250, 
                                 placeholder="e.g.\nCV1 2HN\nTamworth High School\nM&S Banbury")
    
    num_vans = st.slider("Number of Vans / Runs", min_value=1, max_value=5, value=1)
    
    calculate_btn = st.button("🗺️ Optimize Route")

with col_map:
    st.subheader("2. Itinerary & Map")
    
    if calculate_btn and raw_locations.strip():
        # Clean and split inputs
        raw_list = [p.strip() for p in raw_locations.split('\n') if p.strip()]
        raw_list = list(set(raw_list)) # Remove duplicates
        
        pure_postcodes = [p for p in raw_list if is_postcode(p)]
        place_names = [p for p in raw_list if not is_postcode(p)]
        
        # Geocode the Depot first
        depot_data = geocode_postcodes_bulk([depot_postcode])
        if depot_postcode not in depot_data:
            st.error("Could not find the Depot postcode. Please check the format.")
            st.stop()
        
        depot_lat = depot_data[depot_postcode]['lat']
        depot_lon = depot_data[depot_postcode]['lon']
        
        # Prepare the UI for progress tracking (because OpenStreetMap has a 1-sec delay)
        progress_container = st.empty()
        status_container = st.empty()
        
        drop_data = {}
        
        # 1. Process standard postcodes instantly
        if pure_postcodes:
            status_container.text("Processing exact postcodes...")
            drop_data.update(geocode_postcodes_bulk(pure_postcodes))
            
        # 2. Search for place names via OpenStreetMap
        if place_names:
            pb = progress_container.progress(0)
            drop_data.update(geocode_places_osm(place_names, pb, status_container))
            progress_container.empty()
            
        status_container.text("Calculating optimal driving routes...")
        
        # Filter successful drops
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

        # Assign to vans (Clustering)
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
            
        # Routing via OSRM
        m = folium.Map(location=[depot_lat, depot_lon], zoom_start=6)
        folium.Marker(
            [depot_lat, depot_lon], 
            popup="KEP Depot", 
            icon=folium.Icon(color="black", icon="home")
        ).add_to(m)
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        
        total_miles = 0
        total_hours = 0
        master_itinerary = []
        
        for van_id, drops in van_assignments.items():
            if not drops:
                continue
                
            color = colors[van_id % len(colors)]
            
            # Setup the depot block
            depot_block = {
                'query': 'KEP DEPOT', 
                'full_address': f'KEP Print Group, {depot_postcode}', 
                'postcode': depot_postcode, 
                'lat': depot_lat, 'lon': depot_lon
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
                    
                    geojson_shape = route['geometry']
                    folium.GeoJson(
                        geojson_shape,
                        name=f"Van {van_id+1}",
                        style_function=lambda x, c=color: {'color': c, 'weight': 4, 'opacity': 0.8}
                    ).add_to(m)
                    
                    for i, wp in enumerate(waypoints):
                        input_points[i]['sequence'] = wp['waypoint_index']
                        
                    optimized_drops = sorted(input_points, key=lambda x: x['sequence'])
                    
                    # Add to Excel Export List
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
                                [p['lat'], p['lon']],
                                popup=f"Stop {i+1}: {p['query']}",
                                tooltip=p['full_address'],
                                icon=folium.Icon(color=color, icon="info-sign")
                            ).add_to(m)
                            
                else:
                    st.error(f"Routing engine failed for Van {van_id+1}.")
            except Exception as e:
                st.error(f"Could not calculate exact road route for Van {van_id+1}.")
        
        # Clear the status indicator
        status_container.empty()
        
        # --- RENDER TOP LEVEL METRICS & EXPORT ---
        st.divider()
        
        # Create the Excel payload
        if master_itinerary:
            df_manifest = pd.DataFrame(master_itinerary)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_manifest.to_excel(writer, index=False, sheet_name='Optimized Routes')
            
            st.download_button(
                label="⬇️ Download Full Route Manifest (Excel)",
                data=output.getvalue(),
                file_name="KEP_Intelligent_Route_Manifest.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"<div class='metric-card'><h4>Total Campaign Mileage</h4><p class='stat-text'>{total_miles:.1f} mi</p></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><h4>Total Driving Time</h4><p class='stat-text'>{int(total_hours)}h {int((total_hours % 1) * 60)}m</p></div>", unsafe_allow_html=True)
            
        st.components.v1.html(m._repr_html_(), height=600)

    elif not calculate_btn:
        st.info("👈 Paste your locations and hit Optimize to generate the routes.")
