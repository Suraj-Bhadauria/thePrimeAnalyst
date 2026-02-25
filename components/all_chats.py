"""
All Chats Page Component
Displays a comprehensive list of all chat conversations
"""

import streamlit as st

try:
    from test_ui import MockData
    USE_MOCK_DATA = True
except ImportError:
    USE_MOCK_DATA = False


def render_all_chats():
    """Renders the All Chats page with a comprehensive list of conversations"""
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Page Header
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("All Chats")
        st.caption("Browse and manage your conversation history")
    with col2:
        if st.button("Back", icon=":material/arrow_back:", key="back_to_chat"):
            st.session_state.current_page = "chat"
            st.rerun()
    
    st.divider()
    
    # Load all chats from mock data or fallback
    if USE_MOCK_DATA:
        all_chats = MockData.RECENT_ACTIVITY
    else:
        all_chats = [
            {"id": "chat_001", "title": "Q4 Revenue Analysis", "timestamp": "2h ago", "messages": 15},
            {"id": "chat_002", "title": "Competitive Analysis", "timestamp": "5h ago", "messages": 23},
            {"id": "chat_003", "title": "Market Trends Report", "timestamp": "1d ago", "messages": 8},
        ]
    
    # Search and filter
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        search_query = st.text_input("Search chats", placeholder="Type to search...", label_visibility="collapsed")
    with col2:
        sort_by = st.selectbox("Sort by", ["Recent", "Oldest", "Most Messages"], label_visibility="collapsed")
    with col3:
        st.metric("Total Chats", len(all_chats))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Filter chats based on search
    filtered_chats = all_chats
    if search_query:
        filtered_chats = [
            chat for chat in all_chats 
            if search_query.lower() in chat['title'].lower()
        ]
    
    # Sort chats
    if sort_by == "Oldest":
        filtered_chats = list(reversed(filtered_chats))
    elif sort_by == "Most Messages":
        filtered_chats = sorted(filtered_chats, key=lambda x: x.get('messages', 0), reverse=True)
    
    # Display chats in a grid
    if filtered_chats:
        for chat in filtered_chats:
            with st.container(border=True):
                col1, col2, col3 = st.columns([6, 2, 1])
                
                with col1:
                    if st.button(
                        chat['title'],
                        key=f"allchats_btn_{chat['id']}",
                        icon=":material/chat_bubble_outline:",
                        use_container_width=True,
                        type="tertiary"
                    ):
                        st.session_state.active_chat_id = chat['id']
                        st.session_state.is_new_chat = False
                        st.session_state.current_page = "chat"
                        st.rerun()
                
                with col2:
                    st.caption(f"🕒 {chat['timestamp']}")
                    if 'messages' in chat:
                        st.caption(f"💬 {chat['messages']} messages")
                
                with col3:
                    with st.popover("", icon=":material/more_vert:", use_container_width=True):
                        if st.button("Open", key=f"allchats_open_{chat['id']}", icon=":material/open_in_new:", use_container_width=True):
                            st.session_state.active_chat_id = chat['id']
                            st.session_state.is_new_chat = False
                            st.session_state.current_page = "chat"
                            st.rerun()
                        
                        if st.button("Rename", key=f"allchats_rename_{chat['id']}", icon=":material/edit:", use_container_width=True):
                            st.toast(f"Rename feature for {chat['title']}")
                        
                        if st.button("Share", key=f"allchats_share_{chat['id']}", icon=":material/share:", use_container_width=True):
                            st.toast(f"Link copied for {chat['title']}")
                        
                        if st.button("Delete", key=f"allchats_delete_{chat['id']}", icon=":material/delete:", use_container_width=True, type="tertiary"):
                            st.toast(f"Deleted {chat['title']}")
                            st.rerun()
    else:
        st.info("No chats found matching your search.")
    
    st.markdown("<br><br>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_all_chats()
