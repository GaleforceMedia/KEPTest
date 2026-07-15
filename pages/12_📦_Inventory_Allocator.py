import streamlit as st
import pandas as pd
import os
import datetime

st.set_page_config(page_title="Inventory Control", page_icon="📦", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .stock-high { color: #27ae60; font-size: 28px; font-weight: bold; margin: 0; }
    .stock-low { color: #d9534f; font-size: 28px; font-weight: bold; margin: 0; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 Live Inventory & Goods-In Allocator")
st.write("Manage warehouse locations, receive deliveries, and allocate stock to specific KEP Jobs.")
st.divider()

# --- DATABASE MANAGEMENT ---
DB_FILE = "live_inventory.csv"

# Function to load the inventory
def load_inventory():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
    else:
        # If it doesn't exist yet, create the empty framework
        df = pd.DataFrame(columns=["SKU", "Description", "Location", "Quantity", "Last Updated"])
    return df

# Function to save the inventory
def save_inventory(df):
    df.to_csv(DB_FILE, index=False)

# Load current data
inventory_df = load_inventory()

# --- THE APP INTERFACE ---
tab1, tab2, tab3 = st.tabs(["📥 Goods In (Receive Stock)", "📤 Allocate (Assign to Job)", "📊 Live Stock Board"])

# ==========================================
# TAB 1: GOODS IN (RECEIVE DELIVERY)
# ==========================================
with tab1:
    st.subheader("Log Incoming Delivery")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        in_sku = st.text_input("Item Code / SKU", placeholder="e.g. XLD20565")
        in_desc = st.text_input("Material Description", placeholder="e.g. 5mm Foamex 8x4")
    with col2:
        in_qty = st.number_input("Quantity Received (Sheets/Units)", min_value=1, value=1000)
    with col3:
        # Pre-set some KEP warehouse locations
        locations = ["Bay A1 (Racking)", "Bay A2 (Racking)", "Bay B (Floor)", "Studio Holding", "Mezzanine", "Custom..."]
        in_loc = st.selectbox("Assign Warehouse Location", locations)
        if in_loc == "Custom...":
            in_loc = st.text_input("Type Custom Location")
            
    if st.button("📥 Book Stock into Warehouse"):
        if in_sku and in_desc:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Check if this exact SKU is already in that exact location
            match = (inventory_df['SKU'] == in_sku) & (inventory_df['Location'] == in_loc)
            
            if match.any():
                # Add to existing stock
                inventory_df.loc[match, 'Quantity'] += in_qty
                inventory_df.loc[match, 'Last Updated'] = now
                st.success(f"✅ Added {in_qty} sheets to existing stock in {in_loc}.")
            else:
                # Create a new pallet/location entry
                new_row = pd.DataFrame({
                    "SKU": [in_sku], "Description": [in_desc], 
                    "Location": [in_loc], "Quantity": [in_qty], "Last Updated": [now]
                })
                inventory_df = pd.concat([inventory_df, new_row], ignore_index=True)
                st.success(f"✅ New stock booked into {in_loc}.")
                
            save_inventory(inventory_df)
            # Force a reload to update the tables instantly
            st.rerun()
        else:
            st.error("Please enter a SKU and Description.")

# ==========================================
# TAB 2: ALLOCATE (GOODS OUT TO JOB)
# ==========================================
with tab2:
    st.subheader("Allocate Stock to Job")
    
    if inventory_df.empty:
        st.info("Warehouse is currently empty. Book stock in via the 'Goods In' tab.")
    else:
        # Only show items that actually have stock
        available_stock = inventory_df[inventory_df['Quantity'] > 0]
        
        col_out1, col_out2 = st.columns([2, 1])
        
        with col_out1:
            # Create a dropdown of available stock
            options = available_stock.apply(
                lambda row: f"{row['SKU']} - {row['Description']} | Loc: {row['Location']} (Current: {row['Quantity']})", 
                axis=1
            ).tolist()
            
            selected_item = st.selectbox("Select Material to Allocate:", options)
        
        with col_out2:
            job_no = st.text_input("KEP Job Number", placeholder="e.g. 353319")
            
        if selected_item:
            # Figure out which row they selected
            selected_idx = options.index(selected_item)
            selected_row = available_stock.iloc[selected_idx]
            max_qty = int(selected_row['Quantity'])
            
            out_qty = st.number_input(f"Quantity to Remove (Max: {max_qty})", min_value=1, max_value=max_qty, value=1)
            
            if st.button("📤 Allocate to Job"):
                if job_no:
                    # Subtract the stock
                    real_index = selected_row.name
                    inventory_df.at[real_index, 'Quantity'] -= out_qty
                    inventory_df.at[real_index, 'Last Updated'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    save_inventory(inventory_df)
                    st.success(f"✅ Allocated {out_qty} sheets to Job {job_no}. Remaining stock updated.")
                    st.rerun()
                else:
                    st.error("You must enter a Job Number to track where this material went.")

# ==========================================
# TAB 3: LIVE STOCK BOARD
# ==========================================
with tab3:
    st.subheader("📊 Live Warehouse Status")
    
    if inventory_df.empty:
        st.write("No stock data available.")
    else:
        # Show top level metrics
        total_items = len(inventory_df[inventory_df['Quantity'] > 0])
        total_sheets = inventory_df['Quantity'].sum()
        
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"<div class='metric-card'><h4>Active Pallets/Locations</h4><p class='stock-high'>{total_items}</p></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><h4>Total Sheets in Warehouse</h4><p class='stock-high'>{total_sheets:,}</p></div>", unsafe_allow_html=True)
            
        st.divider()
        
        # Add a quick search filter
        search = st.text_input("🔍 Search Inventory (by SKU, Description, or Bay)")
        
        display_df = inventory_df[inventory_df['Quantity'] > 0].sort_values(by="Location")
        
        if search:
            display_df = display_df[
                display_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
            ]
            
        # Display the live database
        st.dataframe(display_df, use_container_width=True, hide_index=True)
