# --- START OF FILE components/chat.py ---
"""
Chat Component with Reasoning Feature
Professional chat interface with streaming AI responses and thought process visualization
"""

import streamlit as st
import time
import datetime
import random
from components.styles import get_chat_css
from components.ui_config import USER_PROFILE, CHAT_SUGGESTIONS


def get_dynamic_greeting(user_name):
    """
    Generates a random, time-aware greeting.
    """
    current_hour = datetime.datetime.now().hour
    
    if 5 <= current_hour < 12:
        # Morning (5 AM - 11:59 AM)
        greetings = [
            "Back at it",
            "Good to see you again",
            "Good morning",
            "Rise and shine",
            "Early bird today"
        ]
    elif 12 <= current_hour < 17:
        # Afternoon (12 PM - 4:59 PM)
        greetings = [
            "Back at it",
            "Good to see you again",
            "Good afternoon",
            "Hope your day is going well",
            "Afternoon analytics"
        ]
    else:
        # Evening/Night (5 PM - 4:59 AM)
        greetings = [
            "Back at it",
            "Good to see you again",
            "Good evening",
            "Late night session"
        ]
    
    greeting_text = random.choice(greetings)
    
    return f"{greeting_text}, <span class=\"hero-username\">{user_name}</span>"


def render_hero_state():
    """Render the empty chat state with hero section - Compact & No Scroll"""
    user_name = USER_PROFILE['name'].split()[0]
    
    # Check for preset query
    preset_query = st.session_state.get('preset_query', None)
    if preset_query:
        st.session_state.preset_query = None
        return preset_query
    
    # 1. GREETING (Dynamic & Time-Aware)
    greeting_html = get_dynamic_greeting(user_name)
    
    st.markdown(f"""
    <div class="hero-container">
        <div class="hero-header">
            <h1 class="hero-greeting">{greeting_html}</h1>
            <p class="hero-subtitle">What insights do you need today?</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. SUGGESTION CARDS (Using Native Buttons with Custom Styling)
    with st.container():
        st.markdown('<div class="suggestion-grid-container">', unsafe_allow_html=True)
        cols = st.columns(2)
        
        # Map suggestions to Material Icons for native implementation
        suggestion_icons = [
            ":material/cancel:",       # Failed Transactions
            ":material/show_chart:",   # Revenue Forecast
            ":material/group_remove:", # Churn
            ":material/payments:"      # High Value
        ]
        
        for i, suggestion in enumerate(CHAT_SUGGESTIONS[:4]): 
            with cols[i % 2]:
                # Markdown Label: Bold Title + Newline + Subtitle
                label = f"**{suggestion['title']}**\n{suggestion['subtitle']}"
                icon = suggestion_icons[i] if i < len(suggestion_icons) else ":material/lightbulb:"
                
                if st.button(label, key=f"suggestion_btn_{i}", icon=icon, width='stretch'):
                    return suggestion['subtitle']
        
        st.markdown('</div>', unsafe_allow_html=True)
                
    # Spacer
    st.markdown('<div style="height: 2vh;"></div>', unsafe_allow_html=True)
    
    # Chat Input with audio support
    prompt = st.chat_input(
        "Ask a question or record audio...",
        key="hero_chat_input",
        accept_audio=True
    )
    
    if prompt:
        if prompt.text:
            return prompt.text
        elif prompt.audio:
            return f"[Audio message received: {prompt.audio.name}]"
    
    return None


def _build_thought_html(thought_events):
    """Build the full thought process HTML from accumulated events."""
    
    STEP_ICONS = {
        1: "🔍", 2: "📋", 3: "📊", 4: "💡",
    }
    STATUS_INDICATORS = {
        "started":   '<span class="tp-status tp-running">⟳ Running</span>',
        "detail":    "",
        "completed": '<span class="tp-status tp-done">✓ Done</span>',
        "error":     '<span class="tp-status tp-error">✗ Error</span>',
    }
    
    # Group events by step
    steps = {}
    for ev in thought_events:
        s = ev["step"]
        if s not in steps:
            steps[s] = {"title": ev["title"], "events": [], "final_status": "started"}
        steps[s]["events"].append(ev)
        steps[s]["final_status"] = ev["status"]
    
    html_parts = ['<div class="thought-process">']
    
    for step_num in sorted(steps.keys()):
        step = steps[step_num]
        icon = STEP_ICONS.get(step_num, "⚙️")
        status = step["final_status"]
        indicator = STATUS_INDICATORS.get(status, "")
        
        # Step header
        is_active = status in ("started", "detail")
        active_class = " tp-step-active" if is_active else ""
        done_class = " tp-step-done" if status == "completed" else ""
        error_class = " tp-step-error" if status == "error" else ""
        
        html_parts.append(
            f'<div class="tp-step{active_class}{done_class}{error_class}">'
            f'  <div class="tp-step-header">'
            f'    <span class="tp-icon">{icon}</span>'
            f'    <span class="tp-title">Step {step_num}: {step["title"]}</span>'
            f'    {indicator}'
            f'  </div>'
        )
        
        # Step detail lines
        html_parts.append('  <div class="tp-details">')
        for ev in step["events"]:
            detail = ev.get("detail", "")
            meta = ev.get("metadata", {})
            
            if detail:
                html_parts.append(f'    <div class="tp-detail-line">{detail}</div>')
            
            # Show metadata as sub-details for completed steps
            if ev["status"] == "completed" and meta:
                html_parts.append('    <div class="tp-meta">')
                for key, val in meta.items():
                    if val and str(val) not in ("none", "", "0", "auto-detect"):
                        nice_key = key.replace("_", " ").title()
                        html_parts.append(
                            f'      <span class="tp-meta-item">'
                            f'<span class="tp-meta-key">{nice_key}:</span> {val}</span>'
                        )
                html_parts.append('    </div>')
        
        html_parts.append('  </div>')  # tp-details
        html_parts.append('</div>')    # tp-step
    
    html_parts.append('</div>')  # thought-process
    return "\n".join(html_parts)


def stream_ai_response(user_query, workflow=None):
    """Stream AI response using the actual multi-agent workflow with live thought process."""
    reasoning_text = ""
    content_text = ""
    
    # Collected thought events for display
    thought_events = []
    
    reasoning_expander = st.expander("💭 Thought Process", expanded=True, icon=":material/psychology:")
    reasoning_container = reasoning_expander.container()
    reasoning_display = reasoning_container.empty()
    content_display = st.empty()
    
    def thinking_callback(event):
        """Called by the workflow at each step transition."""
        thought_events.append(event)
        # Re-render the entire thought process HTML on every event
        html = _build_thought_html(thought_events)
        with reasoning_display:
            st.markdown(html, unsafe_allow_html=True)
    
    if workflow:
        try:
            # Show initial state
            thinking_callback({
                "step": 0, "title": "Initializing", "status": "completed",
                "detail": f"Received query: *\"{user_query}\"*",
                "metadata": {}, "timestamp": 0
            })
            
            # Get conversation history from session state
            conversation_history = []
            for msg in st.session_state.get('messages', []):
                if msg['role'] == 'user':
                    conversation_history.append({
                        'question': msg['content'],
                        'response': ''
                    })
                elif msg['role'] == 'assistant' and conversation_history:
                    conversation_history[-1]['response'] = msg['content']
            
            # Use the workflow with thinking callback for live updates
            content_text = workflow.run_with_thinking(
                question=user_query,
                conversation_history=conversation_history,
                thinking_callback=thinking_callback
            )
            
            # Build final reasoning text for storage
            reasoning_text = _build_thought_html(thought_events)
            
            with content_display:
                st.markdown(content_text)
                
        except Exception as e:
            content_text = f"⚠️ An error occurred while processing your query: {str(e)}"
            with content_display:
                st.error(content_text)
    else:
        content_text = "⚠️ AI workflow not initialized. Please check your configuration."
        with content_display:
            st.warning(content_text)
    
    return reasoning_text, content_text


def render_chat(workflow=None, placeholder=None, use_mock=False):
    """Main entry point for chat component"""
    st.markdown(get_chat_css(), unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "is_streaming" not in st.session_state:
        st.session_state.is_streaming = False
    
    has_messages = len(st.session_state.messages) > 0
    
    if not has_messages:
        user_query = render_hero_state()
        if user_query:
            st.session_state.messages.append({"role": "user", "content": user_query})
            st.rerun()
    else:
        # Standard Chat Interface Header
        st.markdown('<div class="chat-header-row">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([0.7, 0.15, 0.15], gap="small", vertical_alignment="center")
        
        with col1:
            st.markdown('<h2 class="chat-title">PayInsight AI Chat</h2>', unsafe_allow_html=True)
        with col2:
            if st.button("Export", key="export_chat", icon=":material/ios_share:", width='stretch'):
                st.toast("Exporting conversation...", icon="📄")
        with col3:
            if st.button("Share", key="share_chat", icon=":material/share:", width='stretch'):
                st.toast("Link copied to clipboard!", icon="🔗")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<hr class="chat-divider">', unsafe_allow_html=True)
        
        # Display Messages
        last_message = st.session_state.messages[-1]
        messages_to_show = st.session_state.messages[:-1] if last_message['role'] == 'user' and not st.session_state.is_streaming else st.session_state.messages
        
        for message in messages_to_show:
            role = message['role']
            # Use custom avatars: Lightning for AI, Silhouette for User
            avatar_icon = ":material/psychology:" if role == "assistant" else ":material/person:"
            
            with st.chat_message(role, avatar=avatar_icon):
                if role == 'assistant' and message.get('reasoning'):
                    with st.expander("💭 Thought Process", expanded=False, icon=":material/psychology:"):
                        st.markdown(message["reasoning"], unsafe_allow_html=True)
                st.markdown(message['content'])
        
        # Handle Streaming
        if last_message['role'] == 'user' and not st.session_state.is_streaming:
            with st.chat_message("user", avatar=":material/person:"):
                st.markdown(last_message['content'])
            
            st.session_state.is_streaming = True
            with st.chat_message("assistant", avatar=":material/psychology:"):
                reasoning_text, content_text = stream_ai_response(last_message['content'], workflow)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": content_text,
                "reasoning": reasoning_text
            })
            st.session_state.is_streaming = False
            st.rerun()
        
        # Chat Input (Bottom)
        prompt = st.chat_input(
            "Say or record something",
            accept_audio=True)
        if prompt and prompt.text:
            st.session_state.messages.append({"role": "user", "content": prompt.text})
            st.rerun()
        if prompt and prompt.audio:
             st.session_state.messages.append({"role": "user", "content": f"[Audio: {prompt.audio.name}]"})
             st.rerun()

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Chat - PayInsight AI")
    render_chat()