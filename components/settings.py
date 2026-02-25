# --- START OF FILE src/components/settings.py ---
import streamlit as st
from components.styles import get_settings_css


def render_settings():
    """Renders the Settings page with all configuration options."""
    
    # Apply settings page styles
    st.markdown(get_settings_css(), unsafe_allow_html=True)
    
    st.title("Settings")
    st.caption("Configure your Prime Analyst experience")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tabs for different settings categories
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Appearance",
        "Notifications",
        "API & Integrations",
        "Data & Privacy",
        "Advanced"
    ])
    
    # ===== APPEARANCE TAB =====
    with tab1:
        st.subheader("Appearance Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            theme = st.selectbox(
                "Theme",
                options=["Auto", "Light", "Dark"],
                help="Choose your preferred theme"
            )
            
            compact_view = st.toggle(
                "Compact View",
                value=False,
                help="Reduce spacing for more compact interface"
            )
            
            show_tooltips = st.toggle(
                "Show Tooltips",
                value=True,
                help="Display helpful tooltips on hover"
            )
        
        with col2:
            font_size = st.select_slider(
                "Font Size",
                options=["Small", "Medium", "Large"],
                value="Medium"
            )
            
            chart_style = st.selectbox(
                "Chart Style",
                options=["Modern", "Classic", "Minimal"],
                help="Visual style for charts and graphs"
            )
    
    # ===== NOTIFICATIONS TAB =====
    with tab2:
        st.subheader("Notification Preferences")
        
        st.markdown("#### Email Notifications")
        email_col1, email_col2 = st.columns(2)
        
        with email_col1:
            st.checkbox("Transaction Alerts", value=True)
            st.checkbox("Weekly Summary", value=True)
            st.checkbox("System Updates", value=False)
        
        with email_col2:
            st.checkbox("Anomaly Detection", value=True)
            st.checkbox("Report Generation", value=False)
            st.checkbox("API Usage Alerts", value=True)
        
        st.divider()
        
        st.markdown("#### In-App Notifications")
        in_app_col1, in_app_col2 = st.columns(2)
        
        with in_app_col1:
            st.checkbox("Show Notifications", value=True, key="in_app_show")
            st.checkbox("Play Sound", value=False)
        
        with in_app_col2:
            notification_position = st.selectbox(
                "Position",
                options=["Top Right", "Top Left", "Bottom Right", "Bottom Left"]
            )
    
    # ===== API & INTEGRATIONS TAB =====
    with tab3:
        st.subheader("API Configuration")
        
        st.text_input(
            "API Key",
            value="sk-...abc123",
            type="password",
            help="Your Prime Analyst API key"
        )
        
        st.text_input(
            "Webhook URL",
            placeholder="https://your-domain.com/webhook",
            help="Receive real-time event notifications"
        )
        
        st.divider()
        
        st.markdown("#### Connected Integrations")
        
        integration_col1, integration_col2, integration_col3 = st.columns([2, 1, 1])
        
        with integration_col1:
            st.markdown("**Stripe**")
        with integration_col2:
            st.markdown("Connected")
        with integration_col3:
            st.button("Disconnect", key="stripe_disconnect", type="secondary")
        
        integration_col4, integration_col5, integration_col6 = st.columns([2, 1, 1])
        
        with integration_col4:
            st.markdown("**QuickBooks**")
        with integration_col5:
            st.markdown("Not Connected")
        with integration_col6:
            st.button("Connect", key="quickbooks_connect", type="primary")
    
    # ===== DATA & PRIVACY TAB =====
    with tab4:
        st.subheader("Data & Privacy")
        
        st.markdown("#### Data Retention")
        retention_period = st.select_slider(
            "Keep transaction data for",
            options=["30 days", "90 days", "6 months", "1 year", "Forever"],
            value="1 year"
        )
        
        st.divider()
        
        st.markdown("#### Privacy Controls")
        st.checkbox("Allow analytics tracking", value=True)
        st.checkbox("Share anonymous usage data", value=False)
        st.checkbox("Enable audit logging", value=True)
        
        st.divider()
        
        st.markdown("#### Data Export & Deletion")
        col_data1, col_data2 = st.columns(2)
        
        with col_data1:
            if st.button("Export My Data", use_container_width=True):
                st.info("Data export will be sent to your email")
        
        with col_data2:
            if st.button("Delete All Data", type="secondary", use_container_width=True):
                st.warning("This action cannot be undone")
    
    # ===== ADVANCED TAB =====
    with tab5:
        st.subheader("Advanced Settings")
        
        st.markdown("#### Performance")
        cache_enabled = st.toggle("Enable Caching", value=True)
        max_cache_size = st.slider("Max Cache Size (MB)", 50, 500, 200)
        
        st.divider()
        
        st.markdown("#### Developer Options")
        debug_mode = st.toggle("Debug Mode", value=False)
        show_query_logs = st.toggle("Show Query Logs", value=False)
        
        if debug_mode:
            st.code("""
Debug Information:
- Version: 1.0.0
- Environment: Production
- API Endpoint: https://api.primeanalyst.ai/v1
- Session ID: abc-123-def-456
            """)
        
        st.divider()
        
        st.markdown("#### Experimental Features")
        st.checkbox("AI-Powered Insights (Beta)", value=False)
        st.checkbox("Real-time Collaboration", value=False)
        st.checkbox("Advanced Forecasting", value=False)
    
    st.divider()
    
    # Action Buttons
    st.markdown("<br>", unsafe_allow_html=True)
    col_save, col_reset, col_spacer = st.columns([1, 1, 3])
    
    with col_save:
        if st.button("Save Settings", type="primary", use_container_width=True):
            st.success("Settings saved successfully!")
    
    with col_reset:
        if st.button("Reset to Defaults", type="secondary", use_container_width=True):
            st.info("Settings reset to default values")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
