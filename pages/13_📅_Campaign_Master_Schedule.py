import streamlit as st
import pandas as pd
import os
import datetime

st.set_page_config(page_title="Campaign Schedule", page_icon="📅", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .capacity-high { background-color: #fffbeb; border: 2px solid #f59e0b; padding: 15px; border-radius: 8px; color: #b45309; font-weight: bold; margin-bottom: 10px; }
    .capacity-normal { background-color: #f8f9fa; border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; color: #333333; margin-bottom: 10px; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #003666; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📅 Master Campaign Schedule")
st.write("Live dispatch tracker, collation capacity monitor, and file vault.")

# --- DATABASE MANAGEMENT ---
DB_FILE = "campaign_database.csv"
UPLOAD_DIR = "campaign_files"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
    else:
        df = pd.DataFrame(columns=[
            "ID", "Client", "Campaign Name", "AM", "Dispatch Date", 
            "Stores (Qty)", "Collation (Hrs)", "Status", "Notes"
        ])
    df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
    return df

def save_db(df):
    df['Dispatch Date'] = df['Dispatch Date'].dt.strftime('%Y-%m-%d')
    df.to_csv(DB_FILE, index=False)

df = load_db()

# --- APP TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Live Tracker", 
    "➕ Add Campaign", 
    "📊 Capacity Dashboard", 
    "📁 File Vault",
    "⚙️ Import Legacy Data"
])

# ==========================================
# TAB 1: LIVE TRACKER (INTERACTIVE)
# ==========================================
with tab1:
    st.subheader("Interactive Dispatch Board")
    st.write("Double-click any cell to edit dates, update hours, or change the status. The board automatically saves and re-sorts.")
    
    if df.empty:
        st.info("No campaigns active. Go to 'Add Campaign' or 'Import Legacy Data' to start.")
    else:
        display_df = df.sort_values(by="Dispatch Date", ascending=True).reset_index(drop=True)
        display_df['Dispatch Date'] = display_df['Dispatch Date'].dt.date
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Dispatch Date": st.column_config.DateColumn("Dispatch Date", format="YYYY-MM-DD", required=True),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"],
                    required=True
                ),
                "Collation (Hrs)": st.column_config.NumberColumn("Collation (Hrs)", min_value=0, format="%d"),
                "Stores (Qty)": st.column_config.NumberColumn("Stores (Qty)", min_value=0, format="%d")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic"
        )
        
        if st.button("💾 Save Board Changes"):
            edited_df['Dispatch Date'] = pd.to_datetime(edited_df['Dispatch Date'])
            save_db(edited_df)
            st.success("✅ Master Schedule Updated!")
            st.rerun()

# ==========================================
# TAB 2: ADD NEW CAMPAIGN
# ==========================================
with tab2:
    st.subheader("Log a New Campaign")
    with st.form("new_campaign_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            client = st.text_input("Client", placeholder="e.g. Greggs, Betfred")
            campaign = st.text_input("Campaign Name", placeholder="e.g. Week 40 Campaign")
            am = st.text_input("Account Manager", placeholder="e.g. MS, JS")
        with col2:
            dispatch_date = st.date_input("Target Dispatch Date")
            stores = st.number_input("Amount of Stores/Drops", min_value=1, value=100)
        with col3:
            collation_hrs = st.number_input("Estimated Collation Time (Hours)", min_value=0.0, value=4.0, step=0.5)
            status = st.selectbox("Initial Status", ["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"])
        notes = st.text_area("Notes", placeholder="e.g. Needs specialized box makeup...")
        
        if st.form_submit_button("➕ Add to Master Schedule"):
            if client and campaign:
                new_id = f"{client[:3].upper()}-{datetime.datetime.now().strftime('%m%d%H%M')}"
                new_row = pd.DataFrame([{
                    "ID": new_id, "Client": client, "Campaign Name": campaign, "AM": am,
                    "Dispatch Date": pd.to_datetime(dispatch_date), "Stores (Qty)": stores,
                    "Collation (Hrs)": collation_hrs, "Status": status, "Notes": notes
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_db(df)
                st.success(f"✅ Campaign '{campaign}' added successfully!")
                st.rerun()
            else:
                st.error("Client and Campaign Name are required.")

# ==========================================
# TAB 3: CAPACITY DASHBOARD
# ==========================================
with tab3:
    st.subheader("📊 Daily Capacity Monitor")
    st.write("Highlights high-workload days to help plan for potential overtime.")
    
    active_df = df[df["Status"] != "🟢 Dispatched"].copy()
    if active_df.empty:
        st.info("No active campaigns to monitor.")
    else:
        active_df['Date_Str'] = active_df['Dispatch Date'].dt.strftime('%Y-%m-%d')
        capacity_df = active_df.groupby('Date_Str').agg(
            Total_Hours=('Collation (Hrs)', 'sum'),
            Total_Stores=('Stores (Qty)', 'sum'),
            Campaign_Count=('ID', 'count')
        ).reset_index()
        
        MAX_DAILY_HOURS = 16.0 
        st.write(f"*Standard Floor Capacity Threshold Set To: {MAX_DAILY_HOURS} Collation Hours/Day*")
        
        for _, row in capacity_df.iterrows():
            if row['Total_Hours'] > MAX_DAILY_HOURS:
                st.markdown(f"<div class='capacity-high'>⚠️ HIGH CAPACITY ON {row['Date_Str']}: {row['Total_Hours']} hours required for {row['Total_Stores']} stores. Overtime may be required.</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='capacity-normal'>📅 {row['Date_Str']}: {row['Total_Hours']} hours required for {row['Total_Stores']} stores. Within standard capacity.</div>", unsafe_allow_html=True)

        st.divider()
        st.bar_chart(data=capacity_df, x='Date_Str', y='Total_Hours', color="#004B87")

# ==========================================
# TAB 4: FILE VAULT
# ==========================================
with tab4:
    st.subheader("📁 Campaign File Vault")
    if df.empty:
        st.info("Add a campaign first.")
    else:
        col_vault1, col_vault2 = st.columns(2)
        with col_vault1:
            st.write("**Upload a File**")
            campaign_list = df['ID'] + " | " + df['Client'] + " - " + df['Campaign Name']
            selected_camp = st.selectbox("Attach file to:", campaign_list)
            uploaded_file = st.file_uploader("Upload Matrix/Pick List", type=["pdf", "csv", "xlsx"])
            if st.button("📤 Upload to Vault") and uploaded_file:
                camp_id = selected_camp.split(" | ")[0]
                file_path = os.path.join(UPLOAD_DIR, f"{camp_id}_{uploaded_file.name}")
                with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                st.success(f"✅ File securely saved to {camp_id}")
                
        with col_vault2:
            st.write("**Retrieve Files**")
            available_files = os.listdir(UPLOAD_DIR)
            if not available_files:
                st.info("Vault is empty.")
            else:
                for file_name in sorted(available_files):
                    with open(os.path.join(UPLOAD_DIR, file_name), "rb") as file:
                        st.download_button(label=f"⬇️ {file_name}", data=file, file_name=file_name)

# ==========================================
# TAB 5: IMPORT LEGACY DATA
# ==========================================
with tab5:
    st.subheader("⚙️ Import from Legacy Excel/CSV")
    st.write("Upload your existing KEP Campaign Overview files. Use the dropdowns below to map your messy columns into the clean Master Schedule database.")
    
    import_file = st.file_uploader("Upload 'KEP Campaign Overview' (CSV or Excel)", type=["csv", "xlsx"])
    
    if import_file:
        try:
            # Read the file and skip completely empty rows/columns that often plague Excel files
            if import_file.name.endswith('.csv'):
                raw_df = pd.read_csv(import_file).dropna(how='all', axis=0).dropna(how='all', axis=1)
            else:
                raw_df = pd.read_excel(import_file).dropna(how='all', axis=0).dropna(how='all', axis=1)
            
            # Show a preview so the user knows what the app sees
            st.write("**File Preview:**")
            st.dataframe(raw_df.head(5), height=200)
            
            st.divider()
            st.write("**Map Your Columns**")
            st.write("Tell the app which columns from your uploaded file match the Master Schedule requirements.")
            
            # Generate column options for dropdowns (adding an "Ignore" option)
            col_options = ["--- Ignore / Not Available ---"] + list(raw_df.columns)
            
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                map_client = st.selectbox("Which column contains the 'Client Name'?", col_options)
                map_campaign = st.selectbox("Which column contains the 'Campaign Name' / 'Notes'?", col_options)
                map_am = st.selectbox("Which column contains the 'Account Manager (AM)'?", col_options)
            with m_col2:
                map_date = st.selectbox("Which column contains the 'Dispatch Date' / 'Drop Date'?", col_options)
                map_stores = st.selectbox("Which column contains 'Quantity / Stores'? (Optional)", col_options)
            
            if st.button("🔄 Process and Import Data"):
                new_records = []
                
                # Loop through the uploaded file and translate it
                for index, row in raw_df.iterrows():
                    # Only process if they mapped at least the Client and Campaign
                    if map_client != "--- Ignore / Not Available ---" and map_campaign != "--- Ignore / Not Available ---":
                        client_val = str(row[map_client])
                        camp_val = str(row[map_campaign])
                        
                        # Skip if it's a completely empty or invalid row
                        if client_val.lower() == 'nan' or not client_val.strip():
                            continue
                            
                        # Extract the AM if mapped
                        am_val = str(row[map_am]) if map_am != "--- Ignore / Not Available ---" else ""
                        if am_val.lower() == 'nan': am_val = ""
                        
                        # Extract and format the date if mapped
                        date_val = pd.NaT
                        if map_date != "--- Ignore / Not Available ---":
                            try:
                                date_val = pd.to_datetime(row[map_date])
                            except:
                                date_val = pd.NaT
                                
                        # Extract stores if mapped
                        stores_val = 0
                        if map_stores != "--- Ignore / Not Available ---":
                            try:
                                stores_val = int(''.join(filter(str.isdigit, str(row[map_stores]))))
                            except:
                                stores_val = 0
                                
                        # Generate unique ID
                        new_id = f"{client_val[:3].upper()}-IMP{datetime.datetime.now().strftime('%M%S')}{index}"
                        
                        new_records.append({
                            "ID": new_id,
                            "Client": client_val,
                            "Campaign Name": camp_val,
                            "AM": am_val,
                            "Dispatch Date": date_val,
                            "Stores (Qty)": stores_val,
                            "Collation (Hrs)": 4.0, # Defaulting to 4 hours for imported jobs
                            "Status": "🔴 Awaiting Artwork", # Defaulting status
                            "Notes": "Imported from Legacy System"
                        })
                
                if new_records:
                    import_df = pd.DataFrame(new_records)
                    # Merge with existing database
                    df = pd.concat([df, import_df], ignore_index=True)
                    save_db(df)
                    st.success(f"✅ Successfully imported {len(new_records)} campaigns into the Master Schedule!")
                    st.rerun()
                else:
                    st.warning("No valid rows found to import based on your mapping.")

        except Exception as e:
            st.error(f"Error reading file: {e}")
