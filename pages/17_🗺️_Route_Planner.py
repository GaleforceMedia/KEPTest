import streamlit as st
import pandas as pd
import requests
import folium
from sklearn.cluster import KMeans
import numpy as np
import io

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
st.write("Enter your delivery postcodes to automatically generate the optimal driving sequence and map.")
st.divider()

# --- GEOCODING HELPER ---
def geocode_postcodes(postcode_list):
    results = {}
    headers = {"Content-Type": "application/json"}
    
    # The API handles max 100 postcodes per request, chunk them
    for i in range(0, len(postcode_list), 100):
        chunk = postcode_list[i:i+100]
        try:
            resp = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": chunk}, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('result', [])
                for item in data:
                    if item['result']:
                        results[item['query']] = {
                            'lat': item['result']['latitude'],
                            'lon': item['result']['longitude']
                        }
        except Exception as e:
            st.error("Error connecting to postcode database.")
    return results

# --- INTERFACE ---
col_inputs, col_map = st.columns([1, 2], gap="large")

with col_inputs:
    st.subheader("1. Route Details")
    depot_postcode = st.text_input("Depot Postcode (Start & End)", value="B77 5AE")
    
    raw_postcodes = st.text_area("Paste Delivery Postcodes (One per line)", height=250, 
                                 placeholder="e.g.\nCV1 2HN\nB1 1AA\nLE1 1AA")
    
    num_vans = st.slider("Number of Vans / Runs", min_value=1, max_value=5, value=1)
    
    calculate_btn = st.button("🗺️ Optimize Route")

with col_map:
    st.subheader("2. Itinerary & Map")
    
    if calculate_btn and raw_postcodes.strip():
        # Clean inputs
        pc_list = [p.strip().upper() for p in raw_postcodes.split('\n') if p.strip()]
        pc_list = list(set(pc_list)) # Remove duplicates
        
        with st.spinner("Geocoding locations and calculating optimal routes..."):
            
            # Geocode the Depot
            depot_data = geocode_postcodes([depot_postcode])
            if depot_postcode not in depot_data:
                st.error("Could not find the Depot postcode. Please check the format.")
                st.stop()
            
            depot_lat = depot_data[depot_postcode]['lat']
            depot_lon = depot_data[depot_postcode]['lon']
            
            # Geocode the drops
            drop_data = geocode_postcodes(pc_list)
            
            valid_drops = []
            failed_drops = []
            for pc in pc_list:
                if pc in drop_data:
                    valid_drops.append({'postcode': pc, 'lat': drop_data[pc]['lat'], 'lon': drop_data[pc]['lon']})
                else:
                    failed_drops.append(pc)
                    
            if failed_drops:
                st.warning(f"Could not find coordinates for: {', '.join(failed_drops)}")
                
            if not valid_drops:
                st.error("No valid postcodes found to route.")
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
            
            # Master list to collect data for the Excel export
            master_itinerary = []
            
            for van_id, drops in van_assignments.items():
                if not drops:
                    continue
                    
                color = colors[van_id % len(colors)]
                
                input_points = [{'postcode': 'KEP DEPOT', 'lat': depot_lat, 'lon': depot_lon}] + drops
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
                                "Location Type": "KEP Depot" if p['postcode'] == 'KEP DEPOT' else "Drop",
                                "Postcode": p['postcode']
                            })
                        
                        st.markdown(f"### 🚐 Van {van_id+1} Itinerary")
                        st.write(f"**Est. Drive Time:** {int(duration)}h {int((duration % 1) * 60)}m | **Est. Mileage:** {miles:.1f} miles")
                        
                        df_display = pd.DataFrame({
                            "Stop Sequence": range(1, len(optimized_drops) + 1),
                            "Postcode": [p['postcode'] for p in optimized_drops]
                        })
                        st.dataframe(df_display, hide_index=True, use_container_width=True)
                        
                        for i, p in enumerate(optimized_drops):
                            if p['postcode'] != 'KEP DEPOT':
                                folium.Marker(
                                    [p['lat'], p['lon']],
                                    popup=f"Stop {i+1}: {p['postcode']}",
                                    icon=folium.Icon(color=color, icon="info-sign")
                                ).add_to(m)
                                
                    else:
                        st.error(f"Routing engine failed for Van {van_id+1}.")
                except Exception as e:
                    st.error(f"Could not calculate exact road route for Van {van_id+1}.")
            
            # --- RENDER TOP LEVEL METRICS & EXPORT ---
            st.divider()
            
            # Create the Excel payload
            if master_itinerary:
                df_manifest = pd.DataFrame(master_itinerary)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_manifest.to_excel(writer, index=False, sheet_name='Optimized Routes')
                
                st.download_button(
                    label="⬇️ Download Dispatch Order (Excel)",
                    data=output.getvalue(),
                    file_name="KEP_Route_Manifest.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            m1, m2 = st.columns(2)
            with m1:
                st.markdown(f"<div class='metric-card'><h4>Total Campaign Mileage</h4><p class='stat-text'>{total_miles:.1f} mi</p></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><h4>Total Driving Time</h4><p class='stat-text'>{int(total_hours)}h {int((total_hours % 1) * 60)}m</p></div>", unsafe_allow_html=True)
                
            st.components.v1.html(m._repr_html_(), height=600)

    elif not calculate_btn:
        st.info("👈 Paste your postcodes and hit Optimize to generate the routes.")
