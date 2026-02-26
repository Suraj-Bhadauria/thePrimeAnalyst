# --- START OF FILE src/components/profile.py ---
import streamlit as st
from components.styles import get_profile_css
from components.ui_config import USER_PROFILE


def render_profile():
    """Renders the Profile page with user information and preferences."""
    
    # Apply profile page styles
    st.markdown(get_profile_css(), unsafe_allow_html=True)
    
    # Get user profile data
    user_data = USER_PROFILE
    
    st.title("Profile")
    st.caption("Manage your account information and preferences")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Profile Picture Section
    col_pic, col_info = st.columns([1, 3], gap="large")
    
    with col_pic:
        st.image(user_data["avatar_url"], width=150)
        if st.button("Upload New Photo", use_container_width=True, type="tertiary"):
            st.toast("Photo upload feature coming soon")
    
    with col_info:
        st.subheader("Account Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Split name if available
            full_name = user_data.get("name", "User")
            name_parts = full_name.split(" ", 1)
            first_name = name_parts[0] if len(name_parts) > 0 else "User"
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            st.text_input("First Name", value=first_name)
            st.text_input("Email", value="user@primeanalyst.ai")
            st.text_input("Phone", value="+1 (555) 123-4567")
        
        with col2:
            st.text_input("Last Name", value=last_name)
            st.text_input("Company", value="Prime Analyst")
            st.selectbox("Role", options=["Admin", "Analyst", "Viewer", "Financial Analyst"], 
                        index=3 if user_data.get("role") == "Financial Analyst" else 1)
    
    st.divider()
    
    # Account Statistics
    st.subheader("Account Statistics")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    
    with stat_col1:
        st.metric("Member Since", "Jan 2024")
    with stat_col2:
        st.metric("Total Queries", "1,234")
    with stat_col3:
        st.metric("Reports Generated", "56")
    with stat_col4:
        st.metric("API Calls", "12.5K")
    
    st.divider()
    
    # Preferences
    st.subheader("Preferences")
    
    pref_col1, pref_col2 = st.columns(2)
    
    with pref_col1:
        st.selectbox(
            "Language",
            options=["English", "Spanish", "French", "German"],
            help="Select your preferred language"
        )
        
        st.selectbox(
            "Date Format",
            options=["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"],
            help="Choose date display format"
        )
    
    with pref_col2:
        st.selectbox(
            "Timezone",
            options=["UTC", "EST", "PST", "GMT", "CET"],
            help="Your local timezone"
        )
        
        st.selectbox(
            "Currency",
            options=["USD", "EUR", "GBP", "CAD"],
            help="Default currency for reports"
        )
    
    st.divider()
    
    # Security
    st.subheader("Security")
    
    sec_col1, sec_col2 = st.columns(2)
    
    with sec_col1:
        st.markdown("#### Change Password")
        st.text_input("Current Password", type="password")
        st.text_input("New Password", type="password", key="new_pass")
        st.text_input("Confirm Password", type="password")
        st.button("Update Password", type="primary")
    
    with sec_col2:
        st.markdown("#### Two-Factor Authentication")
        st.toggle("Enable 2FA", value=False, help="Add extra security to your account")
        st.markdown("---")
        st.markdown("#### API Access")
        st.text_input("API Key", value="sk-...abc123", type="password")
        st.button("Generate New Key", type="secondary")
    
    st.divider()
    
    # Action Buttons
    st.markdown("<br>", unsafe_allow_html=True)
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
    
    with btn_col1:
        if st.button("Save Changes", type="primary", use_container_width=True):
            st.success("Profile updated successfully!")
    
    with btn_col2:
        if st.button("Cancel", type="secondary", use_container_width=True):
            st.info("Changes discarded")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
