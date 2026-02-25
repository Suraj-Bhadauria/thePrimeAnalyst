# --- START OF FILE components/home.py ---
"""
Home Page Component for Prime Analyst
"""

import streamlit as st
from components.styles import get_home_css

def render_home():
    """
    Renders the Prime Analyst home page landing view.
    """
    
    # Apply home page CSS
    st.markdown(get_home_css(), unsafe_allow_html=True)
    
    # Load data from test_ui
    try:
        from test_ui import MockData
        home_data = MockData.HOME_DATA
        svg_icons = MockData.SVG_ICONS
    except ImportError:
        home_data = {
            "badge_text": "INTELLIGENT ANALYTICS",
            "title": "Prime Analyst",
            "subtitle": "Your autonomous partner in data analysis.",
            "feature_cards": [],
        }
        svg_icons = {}
    
    # ===== HERO SECTION =====
    with st.container():
        # 2. Add a unique locator so CSS can find this specific container
        st.markdown('<span class="hero-card-container"></span>', unsafe_allow_html=True)
        
        # Badge
        st.markdown(
            f'<div class="pill-badge">{home_data["badge_text"]}</div>',
            unsafe_allow_html=True
        )
        
        # Title
        st.markdown(
            f'<h1 class="big-title">{home_data["title"]}</h1>',
            unsafe_allow_html=True
        )
        
        # Subtitle
        st.markdown(
            f'<p class="subtitle-text">{home_data["subtitle"]}</p>',
            unsafe_allow_html=True
        )
        
        # Button Locator (for button styling)
        st.markdown('<div class="cta-locator"></div>', unsafe_allow_html=True)
        
        # Button
        if st.button(
            "Start New Chat",
            key="home_start_chat",
            icon=":material/add:",
            width='content'
        ):
            st.session_state.active_chat_id = None
            st.session_state.is_new_chat = False
            st.switch_page(st.session_state.chat_page)
# ===== STANDALONE TEST =====
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    render_home()