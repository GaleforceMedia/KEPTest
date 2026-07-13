import streamlit as st
import streamlit.components.v1 as components

# Set the page to full width so the iframe has plenty of room
st.set_page_config(page_title="Collation Machine", page_icon="⚙️", layout="wide")

# Remove the default streamlit menu and padding for a more "app-like" feel
st.markdown("""
    <style>
    .block-container { padding-top: 0rem; padding-bottom: 0rem; }
    </style>
    """, unsafe_allow_html=True)

# Embed your external tool
components.iframe(
    src="https://dmtaylor-apps.github.io/WorkApps/CollationMachineEditor.html",
    height=800,
    scrolling=True
)
