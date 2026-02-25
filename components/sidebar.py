# --- START OF FILE src/components/sidebar.py ---
"""
PayInsight AI Sidebar Component
Earthy Professional Theme - High-end SaaS Design
"""

import streamlit as st
from components.styles import get_sidebar_styles
from components.ui_config import USER_PROFILE, MAIN_MENU, SETTINGS_MENU, RECENT_ACTIVITY_PLACEHOLDER

def _init_sidebar_state():
    """Initialize session state for sidebar actions"""
    if 'deleted_chats' not in st.session_state:
        st.session_state.deleted_chats = set()
    if 'last_deleted' not in st.session_state:
        st.session_state.last_deleted = None
    if 'rename_chat' not in st.session_state:
        st.session_state.rename_chat = None

def render_sidebar():
    """Renders the Sidebar"""
    
    _init_sidebar_state()
    
    # Apply the refined CSS
    st.markdown(get_sidebar_styles(), unsafe_allow_html=True)
    
    # Load UI configuration
    user_profile = USER_PROFILE
    # Use session state for chat history if available, otherwise use placeholder
    recent_activity = st.session_state.get('chat_history', RECENT_ACTIVITY_PLACEHOLDER)
    main_menu = MAIN_MENU
    
    # Sync mock active state
    if 'active_chat_id' not in st.session_state:
        active_item = next((item for item in recent_activity if item.get('is_active')), None)
        st.session_state.active_chat_id = active_item['id'] if active_item else None
        
    # --- Sidebar UI ---
    with st.sidebar:
        # 1. User Profile
        st.markdown('<div class="user-profile" style="margin-bottom: 1rem;">', unsafe_allow_html=True)

        col1, col2 = st.columns([1, 3])
        with col1:
            st.image(user_profile["avatar_url"], width=40)
        with col2:
            st.markdown(f"<p style='margin:0; font-weight:600; font-size:14px;'>{user_profile['name']}</p>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size:11px; color:#8B7B6F;'>{user_profile['role']}</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 2. New Chat
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="new-chat-button">', unsafe_allow_html=True)
        # Using :material/add: icon
        if st.button("New Chat", icon=":material/add:", key="new_chat_btn", width='stretch'):
            st.session_state.active_chat_id = None
            st.session_state.current_page = "chat"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # 3. Main Menu
        for item in main_menu:
            if st.button(item['label'], icon=item['icon'], key=f"menu_{item['id']}", width='stretch'):
                st.session_state.current_page = item['id']
                st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        # 4. Recent Activity
        st.markdown("<p style='font-size:10px; color:#8B7B6F; font-weight:700; letter-spacing:1px; margin-top:1.5rem; margin-bottom:0.5rem;'>RECENT ACTIVITY</p>", unsafe_allow_html=True)
        
        # Undo Toast Logic (remains same)
        if st.session_state.last_deleted:
            col_undo_1, col_undo_2 = st.columns([3, 1])
            col_undo_1.caption(f"Deleted: {st.session_state.last_deleted['label']}")
            if col_undo_2.button("Undo", key="undo_btn"):
                st.session_state.deleted_chats.discard(st.session_state.last_deleted["id"])
                st.session_state.last_deleted = None
                st.rerun()

        # Render List
        st.markdown("<br>", unsafe_allow_html=True)
        for activity in recent_activity:
            if activity['id'] in st.session_state.deleted_chats:
                continue
                
            is_active = (activity['id'] == st.session_state.active_chat_id)
            
            # Row Container
            row_class = "activity-row active" if is_active else "activity-row"
            st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
            # --- ALIGNMENT FIX ---
            # 1. Use [0.85, 0.15] ratio for space
            # 2. Use vertical_alignment="center" to force items to the middle line
            col_link, col_menu = st.columns([0.99, 0.01], gap="small", vertical_alignment="center")
            
            display_label = st.session_state.get(f"chat_label_{activity['id']}", activity['title'])
            
            with col_link:
                if st.session_state.rename_chat == activity['id']:
                    # Rename Mode
                    new_name = st.text_input("Name", value=display_label, key=f"rename_input_{activity['id']}", label_visibility="collapsed")
                    if st.button("Save", key=f"save_{activity['id']}", icon=":material/check:", width='stretch'):
                        st.session_state[f"chat_label_{activity['id']}"] = new_name
                        st.session_state.rename_chat = None
                        st.rerun()
                else:
                    # Main Link Button (Icon + Text)
                    if st.button(display_label, key=f"open_{activity['id']}", icon=":material/chat_bubble_outline:", width='stretch'):
                        st.session_state.active_chat_id = activity['id']
                        st.session_state.current_page = "chat"
                        st.rerun()

            with col_menu:
                # Popover Menu (The Three Dots)
                # Aligned perfectly to the right via CSS and column settings
                with st.popover("", icon=":material/more_vert:", width='stretch'):
                    if st.button("Rename", key=f"opt_rename_{activity['id']}", icon=":material/edit:", width='stretch'):
                        st.session_state.rename_chat = activity['id']
                        st.rerun()
                        
                    if st.button("Share", key=f"opt_share_{activity['id']}", icon=":material/share:", width='stretch'):
                        st.toast(f"Link copied for {activity['title']}")
                        
                    st.markdown('<div class="delete-action">', unsafe_allow_html=True)
                    if st.button("Delete", key=f"opt_delete_{activity['id']}", icon=":material/delete:", width='stretch'):
                        st.session_state.deleted_chats.add(activity['id'])
                        st.session_state.last_deleted = {"id": activity['id'], "label": display_label}
                        if st.session_state.active_chat_id == activity['id']:
                            st.session_state.active_chat_id = None
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # End Card Container
            st.markdown('</div>', unsafe_allow_html=True)
        # 5. Footer Menu
        st.markdown("<br>"*2, unsafe_allow_html=True)
        for f_item in SETTINGS_MENU:
            if st.button(f_item['label'], icon=f_item['icon'], key=f"footer_{f_item['id']}", width='stretch'):
                st.session_state.current_page = f_item['id']
                st.rerun()

    return st.session_state.get('current_page', 'home')