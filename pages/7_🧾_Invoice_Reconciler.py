import streamlit as st
import pandas as pd

st.set_page_config(page_title="Invoice Reconciler", page_icon="🧾", layout="wide")

# --- KEP BRANDING CSS ---
st.markdown("""
    <style>
    .metric-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center; }
    .price-text { color: #004B87; font-size: 32px; font-weight: bold; margin: 0; }
    .alert-text { color: #d9534f; font-size: 32px; font-weight: bold; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

st.title("🧾 Courier Invoice Reconciler")
st.write("Upload a raw DHL invoice (CSV). The system will map the service codes and flag unexpected surcharges instantly.")
st.divider()

# --- DHL SERVICE CODE MAPPING ---
# Based on the official KEP/DHL Rate Card Matrix
DHL_CODES = {
    # Parcels
    1: "Parcels - Next Day", 220: "Parcels - Next Day (Neighbor)", 210: "Parcels - Next Day (Safe)",
    2: "Parcels - Pre 12:00", 221: "Parcels - Pre 12:00 (Neighbor)", 211: "Parcels - Pre 12:00 (Safe)",
    9: "Parcels - Pre 10:30", 222: "Parcels - Pre 10:30 (Neighbor)", 212: "Parcels - Pre 10:30 (Safe)",
    3: "Parcels - Pre 09:00",
    4: "Parcels - Saturday", 225: "Parcels - Saturday (Neighbor)", 215: "Parcels - Saturday (Safe)",
    7: "Parcels - Saturday Pre 10:30", 226: "Parcels - Saturday Pre 10:30 (Neighbor)", 216: "Parcels - Saturday Pre 10:30 (Safe)",
    5: "Parcels - Saturday Pre 09:00",
    48: "Parcels - 48 Hours", 72: "Parcels - 72 Hours",
    
    # Bagit Small 1kg
    40: "Bagit Small 1kg - Next Day", 240: "Bagit Small 1kg - Next Day (Neighbor)", 230: "Bagit Small 1kg - Next Day (Safe)",
    41: "Bagit Small 1kg - Pre 12:00", 241: "Bagit Small 1kg - Pre 12:00 (Neighbor)", 231: "Bagit Small 1kg - Pre 12:00 (Safe)",
    49: "Bagit Small 1kg - Pre 10:30", 242: "Bagit Small 1kg - Pre 10:30 (Neighbor)", 232: "Bagit Small 1kg - Pre 10:30 (Safe)",
    42: "Bagit Small 1kg - Pre 09:00",
    
    # Bagit Medium 2kg
    30: "Bagit Medium 2kg - Next Day", 250: "Bagit Medium 2kg - Next Day (Neighbor)", 340: "Bagit Medium 2kg - Next Day (Safe)",
    31: "Bagit Medium 2kg - Pre 12:00", 251: "Bagit Medium 2kg - Pre 12:00 (Neighbor)", 341: "Bagit Medium 2kg - Pre 12:00 (Safe)",
    
    # Bagit Large 5kg
    20: "Bagit Large 5kg - Next Day", 260: "Bagit Large 5kg - Next Day (Neighbor)", 360: "Bagit Large 5kg - Next Day (Safe)",
    21: "Bagit Large 5kg - Pre 12:00", 261: "Bagit Large 5kg - Pre 12:00 (Neighbor)", 361: "Bagit Large 5kg - Pre 12:00 (Safe)"
}

uploaded_file = st.file_uploader("Upload DHL Invoice (.csv)", type=["csv"])

if uploaded_file:
    try:
        # Load the CSV
        df = pd.read_csv(uploaded_file)
        
        # Clean column names in case DHL exports with trailing spaces
        df.columns = [str(c).strip() for c in df.columns]

        # Ensure critical columns exist
        required_cols = ['Consignment', 'Invoice', 'Service', 'Service Desc', 'Value', 'Long Length Charge', 'Heavy Weight Surcharge']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            st.error(f"Missing expected columns from DHL Invoice: {', '.join(missing)}")
        else:
            # --- DATA PROCESSING ---
            df['Value'] = pd.to_numeric(df['Value'], errors='coerce').fillna(0.0)
            df['Long Length Charge'] = pd.to_numeric(df['Long Length Charge'], errors='coerce').fillna(0.0)
            df['Heavy Weight Surcharge'] = pd.to_numeric(df['Heavy Weight Surcharge'], errors='coerce').fillna(0.0)
            
            # Identify Surcharge rows
            df['Total Surcharges'] = df['Long Length Charge'] + df['Heavy Weight Surcharge']
            if 'Congestion Charge' in df.columns:
                df['Congestion Charge'] = pd.to_numeric(df['Congestion Charge'], errors='coerce').fillna(0.0)
                df['Total Surcharges'] += df['Congestion Charge']
                
            surcharge_mask = df['Total Surcharges'] > 0
            surcharge_df = df[surcharge_mask]
            
            # Map True Service Codes
            df['Mapped Service'] = df['Service'].apply(lambda x: DHL_CODES.get(x, f"Unknown Code ({x})"))
            
            # --- DASHBOARD METRICS ---
            total_invoice_cost = df['Value'].sum() + df['Total Surcharges'].sum()
            total_surcharge_cost = df['Total Surcharges'].sum()
            total_consignments = df['Consignment'].nunique()
            
            st.subheader("Invoice Overview")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"<div class='metric-card'><h4>Total Consignments</h4><p class='price-text'>{total_consignments}</p></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><h4>Total Invoice Value</h4><p class='price-text'>£{total_invoice_cost:,.2f}</p></div>", unsafe_allow_html=True)
            with m3:
                alert_class = "alert-text" if total_surcharge_cost > 0 else "price-text"
                st.markdown(f"<div class='metric-card'><h4>Hidden Surcharges</h4><p class='{alert_class}'>£{total_surcharge_cost:,.2f}</p></div>", unsafe_allow_html=True)

            st.divider()

            # --- SURCHARGE AUDIT ---
            if not surcharge_df.empty:
                st.error(f"⚠️ Warning: Found {len(surcharge_df)} shipments with unexpected surcharges!")
                
                # Show only the critical columns to the CSR
                display_cols = ['Consignment', 'Address', 'Mapped Service', 'Weight', 'Value', 'Long Length Charge', 'Heavy Weight Surcharge', 'Total Surcharges']
                existing_disp_cols = [c for c in display_cols if c in surcharge_df.columns]
                
                st.dataframe(surcharge_df[existing_disp_cols].sort_values(by="Total Surcharges", ascending=False), use_container_width=True)
            else:
                st.success("✅ Clean Invoice! No Long Length or Heavy Weight Surcharges detected in this batch.")
            
            st.divider()

            # --- SERVICE BREAKDOWN ---
            st.subheader("Cost Breakdown by Mapped Service")
            
            # Group by our mapped service descriptions to see where KEP is spending the most
            breakdown = df.groupby('Mapped Service').agg(
                Shipments=('Consignment', 'count'),
                Total_Base_Cost=('Value', 'sum'),
                Total_Surcharges=('Total Surcharges', 'sum')
            ).reset_index()
            
            breakdown['Final_Cost'] = breakdown['Total_Base_Cost'] + breakdown['Total_Surcharges']
            breakdown = breakdown.sort_values('Final_Cost', ascending=False)
            
            st.dataframe(breakdown, use_container_width=True)

    except Exception as e:
        st.error(f"Could not read the invoice: {e}")
