import streamlit as st
import pandas as pd
import os
import datetime
import calendar

st.set_page_config(page_title="Campaign Schedule", page_icon="📅", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; font-weight: bold; padding: 10px; width: 100%; border: none; }
    .stButton>button:hover { background-color: #003666; color: white; }
    
    /* Calendar Styling */
    .cal-container { width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 20px; font-family: Arial, sans-serif; }
    .cal-header { background-color: #f8f9fa; text-align: center; padding: 10px; font-weight: bold; border: 1px solid #ddd; color: #555; }
    .cal-cell { border: 1px solid #ddd; vertical-align: top; height: 120px; padding: 5px; background-color: #fff; }
    .cal-cell-empty { background-color: #f9f9f9; border: 1px solid #eee; }
    .cal-date-header { font-weight: bold; font-size: 14px; padding: 4px; border-radius: 4px; display: flex; justify-content: space-between; margin-bottom: 5px; }
    
    /* Capacity Colors */
    .cap-safe { background-color: #d1fae5; color: #065f46; } /* Green */
    .cap-warn { background-color: #fef08a; color: #854d0e; } /* Yellow */
    .cap-clash { background-color: #fee2e2; color: #991b1b; border: 1px solid #ef4444; } /* Red */
    
    /* Job Badges inside Calendar */
    .job-badge { background-color: #e0f2fe; border-left: 3px solid #0284c7; font-size: 11px; padding: 4px; margin-bottom: 4px; border-radius: 3px; color: #0369a1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2; }
    </style>
    """, unsafe_allow_html=True)

st.title("📅 Master Campaign Schedule")
st.write("Live dispatch tracker, interactive capacity calendar, and file vault.")

# --- DATABASE MANAGEMENT ---
DB_FILE = "campaign_database.csv"
UPLOAD_DIR = "campaign_files"
MAX_DAILY_HOURS = 16.0 # KEP's daily collation limit

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
    else:
        df = pd.DataFrame(columns=["ID", "Client", "Campaign Name", "AM", "Dispatch Date", "Stores (Qty)", "Collation (Hrs)", "Status", "Notes"])
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
    "🗓️ Visual Capacity Calendar", 
    "📁 File Vault",
    "⚙️ Import Legacy Data"
])

# ==========================================
# TAB 1: LIVE TRACKER (INTERACTIVE)
# ==========================================
with tab1:
    st.subheader("Interactive Dispatch Board")
    st.write("Double-click any cell to edit. The board automatically saves.")
    
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
                "Status": st.column_config.SelectboxColumn("Status", options=["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"], required=True),
                "Collation (Hrs)": st.column_config.NumberColumn("Collation (Hrs)", min_value=0, format="%d")
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
            client = st.text_input("Client", placeholder="e.g. Greggs")
            campaign = st.text_input("Campaign Name", placeholder="e.g. Week 40")
            am = st.text_input("Account Manager", placeholder="e.g. MS")
        with col2:
            dispatch_date = st.date_input("Target Dispatch Date")
            stores = st.number_input("Amount of Stores", min_value=1, value=100)
        with col3:
            collation_hrs = st.number_input("Est. Collation (Hours)", min_value=0.0, value=4.0, step=0.5)
            status = st.selectbox("Initial Status", ["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"])
        notes = st.text_area("Notes")
        
        if st.form_submit_button("➕ Add to Master Schedule"):
            if client and campaign:
                new_id = f"{client[:3].upper()}-{datetime.datetime.now().strftime('%m%d%H%M')}"
                new_row = pd.DataFrame([{"ID": new_id, "Client": client, "Campaign Name": campaign, "AM": am, "Dispatch Date": pd.to_datetime(dispatch_date), "Stores (Qty)": stores, "Collation (Hrs)": collation_hrs, "Status": status, "Notes": notes}])
                df = pd.concat([df, new_row], ignore_index=True)
                save_db(df)
                st.success(f"✅ Added {campaign}")
                st.rerun()
            else:
                st.error("Client and Campaign required.")

# ==========================================
# TAB 3: VISUAL CAPACITY CALENDAR
# ==========================================
with tab3:
    st.subheader("🗓️ Production Calendar")
    st.write(f"Visually maps daily dispatch load. Days exceeding the **{MAX_DAILY_HOURS}-hour capacity limit** will turn red.")
    
    # Filter active campaigns
    active_df = df[df["Status"] != "🟢 Dispatched"].copy()
    
    if active_df.empty:
        st.info("No active campaigns to display.")
    else:
        # Date selection for the calendar view
        col_m, col_y, _ = st.columns([1, 1, 3])
        with col_m:
            selected_month = st.selectbox("Month", range(1, 13), index=datetime.datetime.now().month - 1, format_func=lambda x: calendar.month_name[x])
        with col_y:
            current_year = datetime.datetime.now().year
            selected_year = st.selectbox("Year", range(current_year - 1, current_year + 3), index=1)
            
        # Group active data by exact date
        active_df['Date_Str'] = active_df['Dispatch Date'].dt.strftime('%Y-%m-%d')
        
        # HTML Calendar Generation
        cal = calendar.monthcalendar(selected_year, selected_month)
        
        html = "<table class='cal-container'>"
        html += "<tr><th class='cal-header'>Mon</th><th class='cal-header'>Tue</th><th class='cal-header'>Wed</th><th class='cal-header'>Thu</th><th class='cal-header'>Fri</th><th class='cal-header'>Sat</th><th class='cal-header'>Sun</th></tr>"
        
        for week in cal:
            html += "<tr>"
            for day in week:
                if day == 0:
                    html += "<td class='cal-cell-empty'></td>"
                else:
                    date_str = f"{selected_year}-{selected_month:02d}-{day:02d}"
                    day_jobs = active_df[active_df['Date_Str'] == date_str]
                    
                    total_hours = day_jobs['Collation (Hrs)'].sum()
                    
                    # Determine Cell Header Color
                    if total_hours == 0:
                        header_class = "cap-safe"
                        hours_text = ""
                    elif total_hours <= MAX_DAILY_HOURS * 0.8:
                        header_class = "cap-safe"
                        hours_text = f"{total_hours}h"
                    elif total_hours <= MAX_DAILY_HOURS:
                        header_class = "cap-warn"
                        hours_text = f"{total_hours}h"
                    else:
                        header_class = "cap-clash"
                        hours_text = f"🚨 {total_hours}h"
                    
                    # Build the cell
                    html += f"<td class='cal-cell'>"
                    html += f"<div class='cal-date-header {header_class}'><span>{day}</span><span>{hours_text}</span></div>"
                    
                    # List the jobs inside the cell
                    for _, job in day_jobs.iterrows():
                        html += f"<div class='job-badge' title='{job['Campaign Name']}'><b>{job['Client']}</b><br>{job['Campaign Name']}</div>"
                        
                    html += "</td>"
            html += "</tr>"
        html += "</table>"
        
        st.markdown(html, unsafe_allow_html=True)

# ==========================================
# TAB 4: FILE VAULT
# ==========================================
with tab4:
    st.subheader("📁 Campaign File Vault")
    if df.empty:
        st.info("Add a campaign first.")
    else:
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            campaign_list = df['ID'] + " | " + df['Client'] + " - " + df['Campaign Name']
            selected_camp = st.selectbox("Attach file to:", campaign_list)
            uploaded_file = st.file_uploader("Upload Matrix/Pick List", type=["pdf", "csv", "xlsx"])
            if st.button("📤 Upload") and uploaded_file:
                camp_id = selected_camp.split(" | ")[0]
                with open(os.path.join(UPLOAD_DIR, f"{camp_id}_{uploaded_file.name}"), "wb") as f: f.write(uploaded_file.getbuffer())
                st.success("✅ File saved.")
        with col_v2:
            st.write("**Retrieve Files**")
            files = os.listdir(UPLOAD_DIR)
            if not files: st.info("Vault is empty.")
            else:
                for f_name in sorted(files):
                    with open(os.path.join(UPLOAD_DIR, f_name), "rb") as file:
                        st.download_button(label=f"⬇️ {f_name}", data=file, file_name=f_name)

# ==========================================
# TAB 5: IMPORT LEGACY DATA
# ==========================================
with tab5:
    st.subheader("⚙️ Import Legacy Excel Data")
    import_file = st.file_uploader("Upload 'KEP Campaign Overview'", type=["csv", "xlsx"])
    if import_file:
        try:
            if import_file.name.endswith('.csv'): raw_df = pd.read_csv(import_file).dropna(how='all', axis=0).dropna(how='all', axis=1)
            else: raw_df = pd.read_excel(import_file).dropna(how='all', axis=0).dropna(how='all', axis=1)
            
            st.dataframe(raw_df.head(3))
            col_opts = ["--- Ignore ---"] + list(raw_df.columns)
            
            m1, m2 = st.columns(2)
            with m1:
                map_client = st.selectbox("Client Name Column", col_opts)
                map_campaign = st.selectbox("Campaign Name Column", col_opts)
            with m2:
                map_date = st.selectbox("Dispatch Date Column", col_opts)
                
            if st.button("🔄 Import Data"):
                new_recs = []
                for _, row in raw_df.iterrows():
                    if map_client != "--- Ignore ---" and map_campaign != "--- Ignore ---":
                        c_val, camp_val = str(row[map_client]), str(row[map_campaign])
                        if c_val.lower() == 'nan' or not c_val.strip(): continue
                        
                        d_val = pd.NaT
                        if map_date != "--- Ignore ---":
                            try: d_val = pd.to_datetime(row[map_date])
                            except: pass
                            
                        new_recs.append({"ID": f"{c_val[:3].upper()}-IMP{datetime.datetime.now().strftime('%M%S%f')}", "Client": c_val, "Campaign Name": camp_val, "AM": "", "Dispatch Date": d_val, "Stores (Qty)": 0, "Collation (Hrs)": 4.0, "Status": "🔴 Awaiting Artwork", "Notes": "Imported"})
                
                if new_recs:
                    df = pd.concat([df, pd.DataFrame(new_recs)], ignore_index=True)
                    save_db(df)
                    st.success(f"✅ Imported {len(new_recs)} campaigns!")
                    st.rerun()
        except Exception as e: st.error(f"Error: {e}")
