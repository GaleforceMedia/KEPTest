import streamlit as st
import pandas as pd
import os
import datetime

st.set_page_config(page_title="Campaign Schedule", page_icon="📅", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    
    /* Changed from red clash to amber highlight */
    .capacity-high { background-color: #fffbeb; border: 2px solid #f59e0b; padding: 15px; border-radius: 8px; color: #b45309; font-weight: bold; margin-bottom: 10px; }
    
    /* Changed from green safe to a clean, neutral daily log */
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

# Ensure upload directory exists
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
    else:
        # Schema matching KEP's requirements
        df = pd.DataFrame(columns=[
            "ID", "Client", "Campaign Name", "AM", "Dispatch Date", 
            "Stores (Qty)", "Collation (Hrs)", "Status", "Notes"
        ])
    
    # Ensure dates are datetime objects for sorting
    df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
    return df

def save_db(df):
    # Convert dates back to string format for clean CSV saving
    df['Dispatch Date'] = df['Dispatch Date'].dt.strftime('%Y-%m-%d')
    df.to_csv(DB_FILE, index=False)

# Load data
df = load_db()

# --- APP TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Live Tracker", 
    "➕ Add Campaign", 
    "📊 Capacity Dashboard", 
    "📁 File Vault (Pick Lists)"
])

# ==========================================
# TAB 1: LIVE TRACKER (INTERACTIVE)
# ==========================================
with tab1:
    st.subheader("Interactive Dispatch Board")
    st.write("Double-click any cell to edit dates, update hours, or change the status. The board automatically saves and re-sorts.")
    
    if df.empty:
        st.info("No campaigns active. Go to 'Add Campaign' to start.")
    else:
        # Sort chronologically by Dispatch Date
        display_df = df.sort_values(by="Dispatch Date", ascending=True).reset_index(drop=True)
        
        # Format the date for the display editor
        display_df['Dispatch Date'] = display_df['Dispatch Date'].dt.date
        
        # Configure the interactive dataframe
        edited_df = st.data_editor(
            display_df,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Dispatch Date": st.column_config.DateColumn("Dispatch Date", format="YYYY-MM-DD", required=True),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    help="Current stage of the campaign",
                    options=[
                        "🔴 Awaiting Artwork",
                        "🟠 In Production",
                        "🟡 Picking/Collation",
                        "🟢 Dispatched"
                    ],
                    required=True
                ),
                "Collation (Hrs)": st.column_config.NumberColumn("Collation (Hrs)", min_value=0, format="%d"),
                "Stores (Qty)": st.column_config.NumberColumn("Stores (Qty)", min_value=0, format="%d")
            },
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic"
        )
        
        # Save changes when the user edits the table
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
        
        submitted = st.form_submit_button("➕ Add to Master Schedule")
        
        if submitted:
            if client and campaign:
                new_id = f"{client[:3].upper()}-{datetime.datetime.now().strftime('%m%d%H%M')}"
                
                new_row = pd.DataFrame([{
                    "ID": new_id,
                    "Client": client,
                    "Campaign Name": campaign,
                    "AM": am,
                    "Dispatch Date": pd.to_datetime(dispatch_date),
                    "Stores (Qty)": stores,
                    "Collation (Hrs)": collation_hrs,
                    "Status": status,
                    "Notes": notes
                }])
                
                df = pd.concat([df, new_row], ignore_index=True)
                save_db(df)
                st.success(f"✅ Campaign '{campaign}' added successfully!")
                st.rerun()
            else:
                st.error("Client and Campaign Name are required.")

# ==========================================
# TAB 3: CAPACITY DASHBOARD (UPDATED)
# ==========================================
with tab3:
    st.subheader("📊 Daily Capacity Monitor")
    st.write("Highlights high-workload days to help the team plan for potential overtime or resource reallocation.")
    
    # Filter out Dispatched jobs for capacity planning
    active_df = df[df["Status"] != "🟢 Dispatched"].copy()
    
    if active_df.empty:
        st.info("No active campaigns to monitor.")
    else:
        # Group by Date to find total hours and stores per day
        active_df['Date_Str'] = active_df['Dispatch Date'].dt.strftime('%Y-%m-%d')
        capacity_df = active_df.groupby('Date_Str').agg(
            Total_Hours=('Collation (Hrs)', 'sum'),
            Total_Stores=('Stores (Qty)', 'sum'),
            Campaign_Count=('ID', 'count')
        ).reset_index()
        
        # Define max daily standard capacity 
        MAX_DAILY_HOURS = 16.0 
        
        st.write(f"*Standard Floor Capacity Threshold Set To: {MAX_DAILY_HOURS} Collation Hours/Day*")
        
        for index, row in capacity_df.iterrows():
            date = row['Date_Str']
            hours = row['Total_Hours']
            stores = row['Total_Stores']
            c_count = row['Campaign_Count']
            
            if hours > MAX_DAILY_HOURS:
                st.markdown(f"""
                    <div class="capacity-high">
                        ⚠️ HIGH CAPACITY ON {date}: {hours} hours required for {stores} stores ({c_count} campaigns). Overtime or additional staffing may be required.
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="capacity-normal">
                        📅 {date}: {hours} hours required for {stores} stores ({c_count} campaigns). Within standard capacity.
                    </div>
                """, unsafe_allow_html=True)

        st.divider()
        st.bar_chart(data=capacity_df, x='Date_Str', y='Total_Hours', color="#004B87")

# ==========================================
# TAB 4: FILE VAULT
# ==========================================
with tab4:
    st.subheader("📁 Campaign File Vault")
    st.write("Upload Pick Lists, Matrix Spreadsheets, or Make-up Guides for the Collation Manager.")
    
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
                safe_filename = f"{camp_id}_{uploaded_file.name}"
                file_path = os.path.join(UPLOAD_DIR, safe_filename)
                
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"✅ File securely saved to {camp_id}")
                
        with col_vault2:
            st.write("**Retrieve Files**")
            available_files = os.listdir(UPLOAD_DIR)
            
            if not available_files:
                st.info("Vault is empty.")
            else:
                for file_name in sorted(available_files):
                    file_path = os.path.join(UPLOAD_DIR, file_name)
                    
                    with open(file_path, "rb") as file:
                        btn = st.download_button(
                            label=f"⬇️ Download {file_name}",
                            data=file,
                            file_name=file_name,
                            mime="application/octet-stream"
                        )
