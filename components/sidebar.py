# --- START OF FILE src/components/sidebar.py ---
"""
Prime Analyst Sidebar Component
Earthy Professional Theme - High-end SaaS Design

Split into two parts so that user profile appears ABOVE st.navigation
and chat history + footer appear BELOW it.
"""

import streamlit as st
from .styles import get_sidebar_styles


def _init_sidebar_state():
    """Initialize session state for sidebar actions"""
    if 'deleted_chats' not in st.session_state:
        st.session_state.deleted_chats = set()
    if 'last_deleted' not in st.session_state:
        st.session_state.last_deleted = None
    if 'rename_chat' not in st.session_state:
        st.session_state.rename_chat = None


def _load_mock_data():
    """Load mock data for development"""
    try:
        from test_ui import MockData
        return (
            MockData.USER_PROFILE,
            MockData.RECENT_ACTIVITY,
        )
    except ImportError:
        return (
            {
                "name": "Alex",
                "role": "Lead Researcher",
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Alex",
            },
            [
                {"id": "chat_001", "title": "Q4 Revenue Analysis", "timestamp": "2h ago", "is_active": False, "messages": 15},
                {"id": "chat_002", "title": "Competitive Analysis", "timestamp": "5h ago", "is_active": True, "messages": 23},
            ],
        )


# ──────────────────────────────────────────────────────────────
# Part 1 — Rendered BEFORE st.navigation (profile + new chat)
# ──────────────────────────────────────────────────────────────
def render_sidebar_header(chat_page=None):
    """Render user profile and New Chat button at the top of the sidebar."""

    st.markdown(get_sidebar_styles(), unsafe_allow_html=True)
    _init_sidebar_state()

    user_profile, _ = _load_mock_data()

    with st.sidebar:
        # User Profile
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image(user_profile["avatar_url"], width=40)
        with col2:
            st.markdown(f"**{user_profile['name']}**")
            st.caption(user_profile["role"])
        st.divider()
        st.markdown("<br>", unsafe_allow_html=True)
        # New Chat link (looks identical to page links)
        if chat_page is not None:
            st.page_link(chat_page, label="New Chat", icon=":material/add:")

        st.markdown("<br>", unsafe_allow_html=True)
# ──────────────────────────────────────────────────────────────
# Part 2 — Rendered AFTER st.navigation (chat history + footer)
# ──────────────────────────────────────────────────────────────
def render_sidebar_body(main_pages=None, footer_pages=None):
    """Render page links, chat history, and footer items in the sidebar.
    
    Args:
        main_pages:   List of st.Page objects for the main nav (Home, Chat, etc.).
        footer_pages: List of st.Page objects for footer nav (Profile, Settings, Help).
    """

    _, all_recent_activity = _load_mock_data()
    recent_activity = all_recent_activity[:5]

    # Sync mock active state
    if 'active_chat_id' not in st.session_state:
        active_item = next((item for item in recent_activity if item.get('is_active')), None)
        st.session_state.active_chat_id = active_item['id'] if active_item else None

    with st.sidebar:
        # ── Page navigation links ──
        if main_pages:
            for page in main_pages:
                st.page_link(page, label=page.title, icon=page.icon)
        # Undo Toast
        if st.session_state.last_deleted:
            col_undo_1, col_undo_2 = st.columns([3, 1])
            col_undo_1.caption(f"Deleted: {st.session_state.last_deleted['label']}")
            if col_undo_2.button("Undo", key="undo_btn"):
                st.session_state.deleted_chats.discard(st.session_state.last_deleted["id"])
                st.session_state.last_deleted = None
                st.rerun()

        # Chat History List
        st.divider()
        st.markdown("<br>", unsafe_allow_html=True)
        for activity in recent_activity:
            if activity['id'] in st.session_state.deleted_chats:
                continue

            is_active = (activity['id'] == st.session_state.active_chat_id)
            col_link, col_menu = st.columns([0.99, 0.01], gap="small", vertical_alignment="center")
            display_label = st.session_state.get(f"chat_label_{activity['id']}", activity['title'])

            with col_link:
                if st.session_state.rename_chat == activity['id']:
                    new_name = st.text_input("Name", value=display_label, key=f"rename_input_{activity['id']}", label_visibility="collapsed")
                    if st.button("Save", key=f"save_{activity['id']}", icon=":material/check:", use_container_width=True):
                        st.session_state[f"chat_label_{activity['id']}"] = new_name
                        st.session_state.rename_chat = None
                        st.rerun()
                else:
                    if st.button(
                        display_label,
                        key=f"open_{activity['id']}",
                        icon=":material/chat_bubble_outline:",
                        use_container_width=True,
                        type="primary" if is_active else "tertiary",
                    ):
                        st.session_state.active_chat_id = activity['id']
                        st.session_state.is_new_chat = False
                        st.rerun()

            with col_menu:
                with st.popover("", icon=":material/more_vert:", use_container_width=True):
                    if st.button("Rename", key=f"opt_rename_{activity['id']}", icon=":material/edit:", use_container_width=True):
                        st.session_state.rename_chat = activity['id']
                        st.rerun()
                    if st.button("Share", key=f"opt_share_{activity['id']}", icon=":material/share:", use_container_width=True):
                        st.toast(f"Link copied for {activity['title']}")
                    if st.button("Delete", key=f"opt_delete_{activity['id']}", icon=":material/delete:", use_container_width=True, type="tertiary"):
                        st.session_state.deleted_chats.add(activity['id'])
                        st.session_state.last_deleted = {"id": activity['id'], "label": display_label}
                        if st.session_state.active_chat_id == activity['id']:
                            st.session_state.active_chat_id = None
                        st.rerun()

        # See all chats link
        st.markdown(
            """
            <style>
            [data-testid="stSidebar"] button[key="see_more_chats"] {
                color: #8C7B6E !important;
                font-size: 0.75rem !important;
                font-weight: 400 !important;
                padding: 0.25rem 0.5rem !important;
                margin-top: 0.25rem !important;
                text-align: center !important;
                justify-content: center !important;
            }
            [data-testid="stSidebar"] button[key="see_more_chats"]:hover {
                color: #4A3B32 !important;
                background-color: rgba(140, 123, 110, 0.1) !important;
            }
            [data-testid="stSidebar"] button[key="see_more_chats"] p {
                font-size: 0.75rem !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if st.button("See all chats →", key="see_more_chats", use_container_width=True, type="tertiary"):
            st.rerun()

        # ── Footer: Profile / Settings / Help ──
        st.divider()
        st.markdown("<br>", unsafe_allow_html=True)
        if footer_pages:
            for page in footer_pages:
                st.page_link(page, label=page.title, icon=page.icon)
        else:
            # Fallback: static buttons
            static_items = [
                {"label": "Profile",  "icon": ":material/person:"},
                {"label": "Settings", "icon": ":material/settings:"},
                {"label": "Help",     "icon": ":material/help:"},
            ]
            for item in static_items:
                st.button(
                    item["label"],
                    icon=item["icon"],
                    key=f"footer_{item['label']}",
                    use_container_width=True,
                    type="tertiary",
                )


# ──────────────────────────────────────────────────────────────
# Legacy wrappers
# ──────────────────────────────────────────────────────────────
def render_sidebar_content():
    """Legacy single-call wrapper."""
    render_sidebar_header()
    render_sidebar_body()


def render_sidebar():
    """Legacy wrapper — calls render_sidebar_content and returns current page."""
    render_sidebar_content()
    return st.session_state.get('current_page', 'home')