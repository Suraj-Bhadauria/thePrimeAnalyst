import streamlit as st
import pandas as pd

# Import components
from components import (
    apply_custom_styles,
    render_sidebar,
    render_home,
    init_session_state,
    get_workflow,
    get_messages
)
from components.chat import render_chat
from components.dashboard import render_dashboard
from components.analytics import render_analytics
from components.reports import render_reports
from components.settings import render_settings
from components.profile import render_profile
from components.help import render_help

# Import existing modules
from src.graph.workflow import Workflow
from src.utils.data_loader import data_loader
from src.config import config

#Page config
st.set_page_config(
    page_title="PayInsight AI",
    page_icon=":chart_with_upwards_trend:",
    layout="wide"
)


#Initialize
@st.cache_resource
def create_workflow():
    """Initialize the workflow (cached)"""
    return Workflow()


# ==========================================
# Main Application
# ==========================================
def main():
    # Initialize current_page in session state if not exists
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'Home Page'
    
    # 1. Apply styles
    apply_custom_styles()
    
    # 2. Render new sidebar (simplified - no arguments needed)
    # The sidebar loads mock data from test_ui.py automatically in development
    current_page = render_sidebar()
    
    # 3. Initialize session state
    init_session_state(
        workflow_factory=create_workflow,
        show_init_message=True
    )
    
    # 4. Render pages based on current_page from sidebar
    workflow = get_workflow()
    messages = get_messages()
    
    # Note: Updated to match new sidebar menu IDs
    if current_page == "home":
        render_home()
    
    elif current_page == "chat" or current_page is None:
        render_chat(
            workflow=workflow,
            placeholder="Ask a question about transaction data..."
        )
    
    elif current_page == "dashboard":
        render_dashboard()
    
    elif current_page == "analytics":
        render_analytics()
    
    elif current_page == "report":
        render_reports()
    
    elif current_page == "settings":
        render_settings()
    
    elif current_page == "profile":
        render_profile()
    
    elif current_page == "help":
        render_help()
    
    else:
        # Default to home for any other selection
        render_home()


if __name__ == "__main__":
    main()
