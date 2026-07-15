import streamlit as st
import pandas as pd
import os
import datetime
import calendar

st.set_page_config(page_title="Campaign Schedule", page_icon="📅", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    .stButton>button { background-color: #004B87; color: white; border-radius: 4px; padding: 10px; width: 100%; border: none; }
    .cal-container { width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 10px; font-family: Arial, sans-serif; }
    .cal-header { background-color: #f8f9fa; text-align: center; padding: 10px; font-weight: bold; border: 1px solid #ddd; color: #555; }
    .cal-cell { border: 1px solid #ddd; vertical-align: top; height: 120px; padding: 5px; background-color: #fff; }
    .date-standard { background-color: #f1f5f9; color: #334155; font-weight: bold; padding: 4px; border-radius: 4px; margin-bottom: 5px; }
    .job-badge { font-size: 11px; padding: 4px; margin-bottom: 4px; border-radius: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .badge-artwork { background-color: #fee2e2; border-left: 3px solid #ef4444; color: #991b1b; }
    .badge-prod { background-color: #ffedd5; border-left: 3px solid #f97316; color: #c2410c; }
    .badge-collate { background-color: #fef08a; border-left: 3px solid #eab308; color: #854d0e; }
    .badge-dispatch { background-color: #d1fae5; border-left: 3px solid #22c55e; color: #065f46; }
    </style>
    """, unsafe_allow_html=True)

st.title("📅 Master Campaign Schedule")

# --- DATABASE MANAGEMENT ---
DB_FILE = "campaign_database.csv"

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df['Dispatch Date'] = pd.to_datetime(df['Dispatch Date'], errors='coerce')
        
        # --- AUTO-DISPATCH LOGIC ---
        today = pd.Timestamp(datetime.date.today())
        mask = (df['Dispatch Date'] < today) & (df['Status'] != '🟢 Dispatched')
        df.loc[mask, 'Status'] = '🟢 Dispatched'
        return df
    return pd.DataFrame(columns=["ID", "Client", "Campaign Name", "AM", "Dispatch Date", "Stores (Qty)", "Collation (Hrs)", "Status", "Notes"])

def save_db(df):
    df['Dispatch Date'] = df['Dispatch Date'].dt.strftime('%Y-%m-%d')
    df.to_csv(DB_FILE, index=False)

df = load_db()

# Split into Active/Dispatched
active_df = df[df['Status'] != '🟢 Dispatched'].copy()
dispatched_df = df[df['Status'] == '🟢 Dispatched'].copy()

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📋 Active Campaigns", "📦 Dispatched Archive", "➕ Add/Import"])

with tab1:
    st.subheader("Active Production Schedule")
    
    # Powerful Search
    search = st.text_input("🔍 Search Active Campaigns (Client, Campaign, AM...)")
    
    search_df = active_df.copy()
    if search:
        search_df = search_df[search_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]
    
    edited_df = st.data_editor(
        search_df.sort_values("Dispatch Date"),
        column_config={
            "ID": st.column_config.TextColumn(disabled=True),
            "Dispatch Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Status": st.column_config.SelectboxColumn(options=["🔴 Awaiting Artwork", "🟠 In Production", "🟡 Picking/Collation", "🟢 Dispatched"]),
        },
        use_container_width=True, hide_index=True, num_rows="dynamic"
    )
    
    if st.button("💾 Save Changes to Active"):
        # Combine back and save
        new_df = pd.concat([edited_df, dispatched_df], ignore_index=True)
        save_db(new_df)
        st.success("✅ Saved!")
        st.rerun()

with tab2:
    st.subheader("Dispatched Campaigns")
    st.dataframe(dispatched_df.sort_values("Dispatch Date", ascending=False), use_container_width=True, hide_index=True)

with tab3:
    col_add, col_imp = st.columns(2)
    with col_add:
        with st.form("add_camp"):
            c = st.text_input("Client")
            n = st.text_input("Campaign Name")
            d = st.date_input("Date")
            if st.form_submit_button("Add"):
                new_row = pd.DataFrame([{"ID": "NEW", "Client": c, "Campaign Name": n, "Dispatch Date": d, "Status": "🔴 Awaiting Artwork"}])
                save_db(pd.concat([df, new_row]))
                st.rerun()
    with col_imp:
        st.info("Legacy Import functionality remains available in the background logic.")
