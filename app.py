import streamlit as st
import pandas as pd

# Import components
from components import (
    apply_custom_styles,
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
from components.all_chats import render_all_chats
from components.sidebar import render_sidebar_header, render_sidebar_body

# Import existing modules
from src.graph.workflow import Workflow
from src.utils.data_loader import data_loader
from src.config import config

# Try to import mock UI data for development (won't exist in production)
try:
    import test_ui
    USE_MOCK_DATA = True  # Set to False for production
except ImportError:
    # Production fallback - test_ui.py not available
    USE_MOCK_DATA = False


#Page config
st.set_page_config(
    page_title="Prime Analyst",
    page_icon=":chart_with_upwards_trend:",
    layout="wide"
)


#Initialize
@st.cache_resource
def create_workflow():
    """Initialize the workflow (cached)"""
    return Workflow()


# ==========================================
# Page wrapper functions for st.Page
# ==========================================
def _page_home():
    render_home()

def _page_chat():
    workflow = get_workflow()
    render_chat(
        workflow=workflow,
        placeholder="Ask a question about transaction data...",
        use_mock=USE_MOCK_DATA
    )

def _page_dashboard():
    render_dashboard()

def _page_analytics():
    render_analytics()

def _page_report():
    render_reports()

def _page_settings():
    render_settings()

def _page_profile():
    render_profile()

def _page_help():
    render_help()

def _page_all_chats():
    render_all_chats()


# ==========================================
# Main Application
# ==========================================
def main():
    # 1. Apply styles
    apply_custom_styles()

    # 2. Initialize session state
    init_session_state(
        workflow_factory=create_workflow,
        show_init_message=True
    )

    # 3. Define all pages for st.navigation (hidden — we render links manually)
    chat_page = st.Page(_page_chat, title="Chat", icon=":material/chat:")
    st.session_state.chat_page = chat_page

    main_pages = [
        st.Page(_page_home,      title="Home",      icon=":material/home:"),
        st.Page(_page_dashboard, title="Dashboard", icon=":material/dashboard:"),
        st.Page(_page_analytics, title="Analytics", icon=":material/analytics:"),
        st.Page(_page_report,    title="Report",    icon=":material/description:"),
    ]
    footer_pages = [
        st.Page(_page_profile,   title="Profile",   icon=":material/person:"),
        st.Page(_page_settings,  title="Settings",  icon=":material/settings:"),
        st.Page(_page_help,      title="Help",      icon=":material/help:"),
    ]

    all_pages = [chat_page] + main_pages + footer_pages

    # 4. st.navigation with position="hidden" — handles routing but no auto sidebar nav
    current_page = st.navigation(all_pages, position="hidden")

    # 5. Render entire sidebar: profile → new chat → page links → chats → footer
    render_sidebar_header(chat_page=chat_page)
    render_sidebar_body(main_pages=main_pages, footer_pages=footer_pages)

    # 6. Run the selected page
    current_page.run()


if __name__ == "__main__":
    main()
