import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Dispatch Calculator", page_icon="🧮", layout="wide")

# --- KEP BRANDING CSS ---
st.markdown("""
    <style>
    .stButton>button {
        background-color: #000000;
        color: white;
        border-radius: 4px;
        font-weight: bold;
        border: none;
        width: 100%;
        padding: 10px;
    }
    .stButton>button:hover { background-color: #333333; color: white; }
    h1, h2, h3 { font-family: 'Arial', sans-serif; }
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .price-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

st.title("🧮 Dispatch Cost Calculator")
st.write("Generate accurate internal costs and client sell prices for Pallets, DHL, and Dedicated Vans.")
st.divider()

# ==========================================
# 1. DATA DICTIONARIES (Easy to update!)
# ==========================================

# DHL Rates (Base up to 20kg, Per Kg over 20kg)
DHL_RATES = {
    "Zone A": {"Next Working Day": (5.3354, 0.3399), "Pre 12": (12.5454, 0.3399), "Pre 10": (12.4321, 0.3399)},
    "Zone B": {"Next Working Day": (5.3354, 0.3399), "Pre 12": (12.5454, 0.3399), "Pre 10": (12.4321, 0.3399)},
    "Zone C": {"Next Working Day": (12.3600, 0.9270), "Pre 12": (19.5700, 0.9270), "Pre 10": (19.4567, 0.9270)}
}

# Pallet Zones (Sample mapped from your CSV)
# Note: You can easily expand this list with all zones
PALLET_POSTCODES = {
    "Zone 2": ["B", "BB", "BD", "BL", "BS", "CB", "CH", "CV", "CW", "DE", "DN", "DY", "HD", "HG", "HP", "HX", "L", "LE", "LS", "LU", "M", "MK", "NG", "NN", "OL", "PR", "S", "SK", "ST", "TF", "WA", "WF", "WN", "WR", "WS", "WV"],
    "Zone 3": ["GL"],
    "Zone 4": ["E", "EC", "N", "NW", "SE", "W", "WC"],
    "Zone 5": ["SW"],
    "Zone 6": ["DA", "HA", "IG", "RM", "TW", "WD"]
}

# Pallet Costs (Priority Base Rates)
PALLET_RATES_PRIORITY = {
    "Zone 2": {"Micro": 45.50, "Quarter": 50.00, "Half": 52.50, "Full": 60.00},
    "Zone 3": {"Micro": 46.50, "Quarter": 50.50, "Half": 53.50, "Full": 60.00},
    "Zone 4": {"Micro": 72.50, "Quarter": 75.50, "Half": 76.50, "Full": 79.50},
    "Zone 5": {"Micro": 72.50, "Quarter": 75.50, "Half": 76.50, "Full": 79.50},
    "Zone 6": {"Micro": 59.50, "Quarter": 62.00, "Half": 65.00, "Full": 70.00}
}

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def get_pallet_zone(postcode_prefix):
    prefix = postcode_prefix.upper().strip()
    for zone, prefixes in PALLET_POSTCODES.items():
        if prefix in prefixes:
            return zone
    return None # Return None if not found so user can manually select

def calculate_pallet_size(weight, length, width, height):
    # Base logic from your CSV limits
    if weight <= 150 and height <= 0.6 and length <= 1.2 and width <= 0.8:
        return "Micro"
    elif weight <= 300 and height <= 0.6:
        return "Quarter"
    elif weight <= 600:
        return "Half"
    else:
        return "Full"

# ==========================================
# 3. INTERFACE & TABS
# ==========================================

tab_pallet, tab_dhl, tab_van = st.tabs(["📦 Pallet Network (UPN)", "✉️ DHL Parcel", "🚐 Same Day Van"])

# --- TAB 1: PALLET NETWORK ---
with tab_pallet:
    st.subheader("UPN Pallet Quote")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**1. Dimensions & Sizing**")
        p_weight = st.number_input("Total Weight (kg)", min_value=1, value=150, key="p_weight")
        p_height = st.number_input("Height (m)", min_value=0.1, value=1.0, step=0.1, key="p_height")
        
        # Auto-size the pallet based on inputs
        suggested_size = calculate_pallet_size(p_weight, 1.2, 1.2, p_height)
        p_size = st.selectbox("Pallet Size", ["Micro", "Quarter", "Half", "Full", "Oversize"], 
                              index=["Micro", "Quarter", "Half", "Full", "Oversize"].index(suggested_size))
        
        p_qty = st.number_input("Quantity of Pallets", min_value=1, value=1)
        
    with col2:
        st.write("**2. Destination & Service**")
        p_postcode = st.text_input("Postcode Prefix (e.g., 'B' or 'CV')").upper()
        
        # Auto-detect zone
        detected_zone = get_pallet_zone(p_postcode)
        zone_list = list(PALLET_RATES_PRIORITY.keys()) + ["Manual Entry"]
        
        if detected_zone:
            p_zone = st.selectbox("Delivery Zone", zone_list, index=zone_list.index(detected_zone))
        else:
            p_zone = st.selectbox("Delivery Zone", zone_list)
            
        p_service = st.selectbox("Service Level", ["Priority (Next Day)", "Standard (Economy)"])
        p_surcharge = st.selectbox("Surcharges", ["None", "Pre 10am (+£25)", "Pre 12 noon (+£19)", "Timed Delivery (+£22)", "Saturday (+£60)"])
        p_markup = st.number_input("KEP Margin / Markup (%)", min_value=0, value=30, key="p_mark")

    st.write(" ")
    if st.button("Calculate Pallet Cost", use_container_width=True):
        if p_zone == "Manual Entry":
            st.warning("Please select a valid zone for automated calculation, or refer to manual rate card.")
        else:
            # 1. Base Rate
            try:
                base_rate = PALLET_RATES_PRIORITY[p_zone][p_size]
            except KeyError:
                base_rate = 0
                st.error("Rate not found for this Size/Zone combination.")
            
            # 2. Economy Discount (Roughly £4 cheaper based on your CSV)
            if "Standard" in p_service:
                base_rate = max(0, base_rate - 4.00) 
            
            # 3. Add Surcharges
            surcharge_amt = 0
            if "10am" in p_surcharge: surcharge_amt = 25
            elif "12 noon" in p_surcharge: surcharge_amt = 19
            elif "Timed" in p_surcharge: surcharge_amt = 22
            elif "Saturday" in p_surcharge: surcharge_amt = 60
            
            # 4. Math
            total_cost = (base_rate * p_qty) + surcharge_amt
            sell_price = total_cost * (1 + (p_markup / 100))
            
            st.markdown(f"""
            <div class='metric-card'>
                <h4>Total KEP Sell Price</h4>
                <p class='price-text'>£{sell_price:,.2f}</p>
                <p style='color:gray; margin-top:10px;'>Internal Cost: £{total_cost:,.2f} &nbsp; | &nbsp; Profit: £{sell_price - total_cost:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)


# --- TAB 2: DHL PARCELS ---
with tab_dhl:
    st.subheader("DHL Parcel Quote")
    
    d_col1, d_col2 = st.columns(2)
    
    with d_col1:
        st.write("**1. Package Details**")
        d_weight = st.number_input("Weight (kg)", min_value=0.1, value=5.0, step=0.5)
        d_length = st.number_input("Longest Length (cm)", min_value=1, value=50)
        d_qty = st.number_input("Number of Parcels", min_value=1, value=1, key="dhl_qty")
        
    with d_col2:
        st.write("**2. Service Options**")
        d_zone = st.selectbox("DHL Zone", ["Zone A", "Zone B", "Zone C"])
        d_service = st.selectbox("Service Level", ["Next Working Day", "Pre 12", "Pre 10"])
        d_markup = st.number_input("KEP Margin / Markup (%)", min_value=0, value=30, key="d_mark")

    st.write(" ")
    if st.button("Calculate DHL Cost", use_container_width=True):
        
        # 1. Base Rate Math
        base, per_kg = DHL_RATES[d_zone][d_service]
        
        cost_per_parcel = base
        if d_weight > 20:
            extra_kg = math.ceil(d_weight - 20)
            cost_per_parcel += (extra_kg * per_kg)
            
        # 2. Long Length Surcharges (From your DHL CSV)
        ll_surcharge = 0
        if d_length >= 140 and d_length < 160: ll_surcharge = 7.50
        elif d_length >= 160 and d_length < 180: ll_surcharge = 15.00
        elif d_length >= 180: ll_surcharge = 15.00
        
        cost_per_parcel += ll_surcharge
        total_cost = cost_per_parcel * d_qty
        
        # 3. KEP Sell Price (Flat markup method as shown in your CSV, or percentage)
        # Your CSV showed internal £5.33 -> Sell £11.33. We will use the percentage markup for scalability.
        sell_price = total_cost * (1 + (d_markup / 100))
        
        st.markdown(f"""
        <div class='metric-card'>
            <h4>Total KEP Sell Price</h4>
            <p class='price-text'>£{sell_price:,.2f}</p>
            <p style='color:gray; margin-top:10px;'>Internal Cost: £{total_cost:,.2f} &nbsp; | &nbsp; Surcharges applied: £{ll_surcharge * d_qty:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)


# --- TAB 3: SAME DAY VAN ---
with tab_van:
    st.subheader("Dedicated Same Day Vehicle")
    
    v_col1, v_col2 = st.columns(2)
    
    with v_col1:
        v_distance = st.number_input("Total Distance (Miles)", min_value=1, value=166)
        v_vehicle = st.selectbox("Vehicle Required", ["Small Van", "Transit Van", "Luton Van", "7.5T Lorry", "18T Lorry"])
        
    with v_col2:
        v_ppm = st.number_input("Cost Per Mile (£)", min_value=0.50, value=2.50, step=0.10)
        v_markup = st.number_input("KEP Margin / Markup (%)", min_value=0, value=20, key="v_mark")
        
    st.write(" ")
    if st.button("Calculate Vehicle Cost", use_container_width=True):
        total_cost = v_distance * v_ppm
        sell_price = total_cost * (1 + (v_markup / 100))
        
        st.markdown(f"""
        <div class='metric-card'>
            <h4>Total KEP Sell Price</h4>
            <p class='price-text'>£{sell_price:,.2f}</p>
            <p style='color:gray; margin-top:10px;'>Internal Cost: £{total_cost:,.2f} &nbsp; | &nbsp; Profit: £{sell_price - total_cost:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)
