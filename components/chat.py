# --- START OF FILE components/chat.py ---
"""
Chat Component with Reasoning Feature
Professional chat interface with streaming AI responses, charts, and thought process visualization.
Wired to the real LangGraph backend workflow.
"""

import streamlit as st
import time
import datetime
import random
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from components.styles import get_chat_css
from components.ui_config import USER_PROFILE, CHAT_SUGGESTIONS
from src.services.news_service import GoogleNewsService

# Chart colors matching the theme
CHART_COLORS = ["#4A3B32", "#6B5F52", "#8C7B6E", "#A89890", "#B5A99F", "#C9BFB8"]

# Initialize news service
news_service = GoogleNewsService(use_live_feed=True, cache_duration_minutes=15)


class _MockData:
    """Minimal data holder — sources from ui_config."""
    USER_PROFILE = USER_PROFILE
    CHAT_SUGGESTIONS = CHAT_SUGGESTIONS


MockData = _MockData


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
    user_name = MockData.USER_PROFILE['name'].split()[0]
    
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
        
        for i, suggestion in enumerate(MockData.CHAT_SUGGESTIONS[:4]): 
            with cols[i % 2]:
                # Markdown Label: Bold Title + Newline + Subtitle
                label = f"**{suggestion['title']}**\n{suggestion['subtitle']}"
                icon = suggestion_icons[i] if i < len(suggestion_icons) else ":material/lightbulb:"
                
                if st.button(label, key=f"suggestion_btn_{i}", icon=icon, width='stretch'):
                    return suggestion['subtitle']
        
        st.markdown('</div>', unsafe_allow_html=True)
                
    # Spacer
    # st.markdown('<div style="height: 2vh;"></div>', unsafe_allow_html=True)
    
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


def render_news_panel(news_items: list):
    """
    Render a collapsible news panel in the top right corner.
    Uses components.html() so JavaScript actually works.
    """
    import streamlit.components.v1 as components
    
    # Limit to max 3 items
    news_items = (news_items or [])[:3]
    count = len(news_items) if news_items else 0
    
    if not news_items:
        news_content = '<div class="np-empty">Ask a question to see related news</div>'
    else:
        items_html = []
        for item in news_items:
            items_html.append(
                f'<div class="np-item">'
                f'<p class="np-headline">{item.get("headline", "")}</p>'
                f'<div class="np-meta">'
                f'<span class="np-source">{item.get("source", "")}</span>'
                f'<span class="np-dot">\u2022</span>'
                f'<span class="np-time">{item.get("time", "")}</span>'
                f'<span class="np-tag">{item.get("category", "")}</span>'
                f'</div></div>'
            )
        news_content = "".join(items_html)
    
    badge_html = f'<span class="np-badge">{count} new</span>' if count > 0 else ''
    
    html = f'''<!DOCTYPE html><html><head><style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:transparent;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif}}
    .np{{background:rgba(255,255,255,0.5);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
        border:1px solid rgba(229,224,216,0.6);border-radius:12px;overflow:hidden;
        box-shadow:0 4px 20px rgba(74,59,50,0.08),0 1px 4px rgba(0,0,0,0.04);width:100%;max-width:320px}}
    .np-hdr{{padding:10px 14px;display:flex;align-items:center;gap:10px;cursor:pointer;
        background:linear-gradient(180deg,rgba(253,251,247,0.7),rgba(255,255,255,0.7));
        border-bottom:1px solid rgba(229,224,216,0.6);user-select:none}}
    .np-hdr:hover{{background:linear-gradient(180deg,rgba(248,246,242,0.8),rgba(253,251,247,0.8))}}
    .np.collapsed .np-hdr{{border-bottom-color:transparent}}
    .np-icon{{width:32px;height:32px;background:linear-gradient(135deg,#4A3B32,#6B5F52);
        border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
    .np-icon svg{{width:18px;height:18px;fill:#dcdcdc}}
    .np-titles h2{{font-size:13px;font-weight:700;color:#4A3B32;margin:0}}
    .np-titles p{{font-size:10px;color:#8C7B6E;margin:2px 0 0}}
    .np-badge{{background:linear-gradient(135deg,#4A7C59,#5A9469);color:#fff;
        font-size:10px;font-weight:700;padding:3px 8px;border-radius:10px;margin-left:auto}}
    .np-chev{{width:16px;height:16px;fill:#8C7B6E;transition:transform 0.3s ease;flex-shrink:0}}
    .np.collapsed .np-chev{{transform:rotate(-90deg)}}
    .np-body{{max-height:300px;overflow:hidden;transition:max-height 0.3s ease}}
    .np.collapsed .np-body{{max-height:0}}
    .np-item{{padding:10px 14px;border-bottom:1px solid rgba(240,240,240,0.8);
        border-left:3px solid transparent;transition:background 0.15s ease}}
    .np-item:last-child{{border-bottom:none}}
    .np-item:hover{{background:rgba(253,251,247,0.8);border-left-color:#4A7C59}}
    .np-headline{{font-size:12px;font-weight:600;color:#4A3B32;line-height:1.45;margin:0 0 6px;
        display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
    .np-meta{{display:flex;align-items:center;font-size:10px;color:#8C7B6E;gap:4px;flex-wrap:wrap}}
    .np-source{{font-weight:600;color:#6B5F52}}
    .np-dot{{color:#C9BFB8;font-size:8px}}
    .np-time{{color:#A89890}}
    .np-tag{{background:#F2F1EF;color:#6B5F52;padding:2px 6px;border-radius:4px;
        font-weight:600;font-size:9px;margin-left:auto}}
    .np-empty{{text-align:center;padding:24px 16px;color:#8C7B6E;font-size:12px}}
    </style></head><body>
    <div class="np" id="np">
        <div class="np-hdr" id="npHdr">
            <div class="np-icon"><svg viewBox="0 0 24 24"><path d="M19,5V19H5V5H19M19,3H5C3.9,3 3,3.9 3,5V19C3,20.1 3.9,21 5,21H19C20.1,21 21,20.1 21,19V5C21,3.9 20.1,3 19,3M18,17H6V15H18V17M18,13H6V11H18V13M18,9H6V7H18V9Z"/></svg></div>
            <div class="np-titles"><h2>Market News</h2><p>Related to your query</p></div>
            {badge_html}
            <svg class="np-chev" viewBox="0 0 24 24"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>
        </div>
        <div class="np-body">{news_content}</div>
    </div>
    <script>document.getElementById("npHdr").addEventListener("click",function(){{document.getElementById("np").classList.toggle("collapsed")}});</script>
    </body></html>'''
    
    components.html(html, height=300 if count > 0 else 70, scrolling=False)


def render_chart(chart_config: dict):
    """Render a chart based on the configuration."""
    chart_type = chart_config.get("type")
    title = chart_config.get("title", "")
    data = chart_config.get("data")
    
    if not data:
        return
    
    st.markdown(f"**{title}**")
    
    if chart_type == "pie":
        df = pd.DataFrame(data)
        if 'name' in df.columns and 'value' in df.columns:
            fig = px.pie(df, names='name', values='value', color_discrete_sequence=CHART_COLORS)
        elif 'status' in df.columns and 'count' in df.columns:
            fig = px.pie(df, names='status', values='count', color_discrete_sequence=CHART_COLORS)
        elif 'type' in df.columns and 'count' in df.columns:
            fig = px.pie(df, names='type', values='count', color_discrete_sequence=CHART_COLORS)
        else:
            return
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, key=f"chat_pie_{title}")
    
    elif chart_type == "bar":
        df = pd.DataFrame(data)
        x_field = chart_config.get("x_field", df.columns[0])
        y_field = chart_config.get("y_field", df.columns[1] if len(df.columns) > 1 else df.columns[0])
        fig = px.bar(df, x=x_field, y=y_field, color_discrete_sequence=CHART_COLORS)
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, key=f"chat_bar_{title}")
    
    elif chart_type == "bar_horizontal":
        df = pd.DataFrame(data)
        if 'state' in df.columns and 'volume' in df.columns:
            fig = px.bar(df, x='volume', y='state', orientation='h', color_discrete_sequence=CHART_COLORS)
        else:
            fig = px.bar(df, x=df.columns[1], y=df.columns[0], orientation='h', color_discrete_sequence=CHART_COLORS)
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, key=f"chat_barh_{title}")
    
    elif chart_type == "line":
        if isinstance(data, dict) and 'hours' in data and 'values' in data:
            df = pd.DataFrame({"Hour": data['hours'], "Volume": data['values']})
            fig = px.line(df, x='Hour', y='Volume', markers=True, color_discrete_sequence=CHART_COLORS)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
            fig = px.line(df, x=df.columns[0], y=df.columns[1], markers=True, color_discrete_sequence=CHART_COLORS)
        else:
            return
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, key=f"chat_line_{title}")
    
    elif chart_type == "heatmap":
        df = pd.DataFrame(data)
        if 'day' in df.columns and 'hour' in df.columns and 'fraud_count' in df.columns:
            pivot = df.pivot(index='day', columns='hour', values='fraud_count')
            fig = px.imshow(pivot, color_continuous_scale='RdYlGn_r', aspect='auto')
            fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True, key=f"chat_heat_{title}")
    
    elif chart_type == "kpi":
        # Render KPI cards
        cols = st.columns(4)
        kpi_items = [("Total Volume", data.get("total_volume", {})),
                     ("Total Value", data.get("total_value", {})),
                     ("Success Rate", data.get("success_rate", {})),
                     ("Fraud Flags", data.get("fraud_flags", {}))]
        for i, (name, kpi) in enumerate(kpi_items):
            with cols[i]:
                val = kpi.get("value", "N/A")
                if isinstance(val, (int, float)):
                    if "rate" in name.lower():
                        val = f"{val}%"
                    elif val >= 1000000:
                        val = f"{val/1000000:.1f}M"
                    elif val >= 1000:
                        val = f"{val/1000:.1f}K"
                st.metric(name, val)


def stream_ai_response(user_query, workflow=None):
    """Stream AI response using the real LangGraph workflow with thinking callback."""
    reasoning_text = ""
    content_text = ""

    reasoning_expander = st.expander("Thought process", expanded=True)
    reasoning_container = reasoning_expander.container()
    reasoning_display = reasoning_container.empty()
    content_display = st.empty()

    if workflow is not None:
        # --- Real backend ---
        def _thinking_cb(event: dict):
            nonlocal reasoning_text
            title = event.get("title", "")
            detail = event.get("detail", "")
            status = event.get("status", "")
            line = ""
            if title:
                line += f"**{title}**"
            if detail:
                line += f" — {detail}"
            if status:
                line += f" _{status}_"
            if line:
                reasoning_text += line + "\n\n"
                with reasoning_display:
                    st.markdown(
                        f'<div class="reasoning-content">{reasoning_text}</div>',
                        unsafe_allow_html=True,
                    )

        # Build conversation history from session messages
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.get("messages", [])[:-1]  # exclude current user msg
        ]

        final_response = workflow.run_with_thinking(
            question=user_query,
            conversation_history=history,
            thinking_callback=_thinking_cb,
        )
        content_text = final_response or "No response generated."
        with content_display:
            st.markdown(content_text)
    else:
        # --- No workflow available ---
        reasoning_text = "No analytics backend connected."
        with reasoning_display:
            st.markdown(
                f'<div class="reasoning-content">{reasoning_text}</div>',
                unsafe_allow_html=True,
            )
        content_text = "Please ensure the backend workflow is initialized."
        with content_display:
            st.markdown(content_text)

    return reasoning_text, content_text, {"charts": []}


def render_chat(workflow=None, placeholder=None, use_mock=False):
    """Main entry point for chat component"""
    st.markdown(get_chat_css(), unsafe_allow_html=True)

    # Start a fresh chat every time the Chat page is opened from the sidebar
    if st.session_state.get('is_new_chat') is not True:
        import time as _time
        new_chat_id = f"chat_new_{int(_time.time() * 1000)}"
        st.session_state.active_chat_id = new_chat_id
        st.session_state.is_new_chat = True
        st.session_state.messages = []
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "is_streaming" not in st.session_state:
        st.session_state.is_streaming = False
    
    # Initialize chat-specific news storage
    if "chat_news" not in st.session_state:
        st.session_state.chat_news = {}
    
    # Get current active chat ID
    active_chat_id = st.session_state.get('active_chat_id', 'default')
    
    # Initialize news for this chat if it doesn't exist
    if active_chat_id not in st.session_state.chat_news:
        st.session_state.chat_news[active_chat_id] = []
    
    has_messages = len(st.session_state.messages) > 0
    
    # Two-column layout: chat on left, news on right
    chat_col, news_col = st.columns([4.5, 1.5], gap="medium")
    
    # Render news panel in the right column
    with news_col:
        current_news = st.session_state.chat_news.get(active_chat_id, [])
        render_news_panel(current_news)
    
    # Render entire chat interface in the left column
    with chat_col:
        if not has_messages:
            user_query = render_hero_state()
            if user_query:
                # Fetch news for this query
                st.session_state.chat_news[active_chat_id] = news_service.get_relevant_news(user_query)
                st.session_state.messages.append({"role": "user", "content": user_query})
                st.rerun()
        else:
            # Standard Chat Interface Header
            st.markdown('<div class="chat-header-row">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([0.7, 0.15, 0.15], gap="small", vertical_alignment="center")
            
            with col1:
                st.markdown('<h2 class="chat-title">Prime Analyst Chat</h2>', unsafe_allow_html=True)
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
                        with st.expander("Thought process", expanded=False):
                            st.markdown(f'<div class="reasoning-content">{message["reasoning"]}</div>', unsafe_allow_html=True)
                    st.markdown(message['content'])
                    
                    # Display charts for assistant messages
                    if role == 'assistant' and message.get('charts'):
                        charts = message['charts'].get('charts', [])
                        if charts:
                            st.markdown("---")
                            st.markdown("**📊 Relevant Analytics**")
                            if len(charts) == 1:
                                render_chart(charts[0])
                            elif len(charts) == 2:
                                cols = st.columns(2)
                                for i, chart in enumerate(charts):
                                    with cols[i]:
                                        render_chart(chart)
                            else:
                                render_chart(charts[0])
                                cols = st.columns(2)
                                for i, chart in enumerate(charts[1:3]):
                                    with cols[i]:
                                        render_chart(chart)
            
            # Handle Streaming
            if last_message['role'] == 'user' and not st.session_state.is_streaming:
                with st.chat_message("user", avatar=":material/person:"):
                    st.markdown(last_message['content'])
                
                st.session_state.is_streaming = True
                with st.chat_message("assistant", avatar=":material/psychology:"):
                    reasoning_text, content_text, chart_data = stream_ai_response(
                        last_message['content'], workflow=workflow
                    )
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": content_text,
                    "reasoning": reasoning_text,
                    "charts": chart_data
                })
                st.session_state.is_streaming = False

                # --- Save to chat history for sidebar display ---
                active_id = st.session_state.get("active_chat_id", "default")
                chat_history = st.session_state.get("chat_history", [])
                # Check if this chat already exists in history
                existing = next((c for c in chat_history if c["id"] == active_id), None)
                if existing:
                    existing["messages"] = len(st.session_state.messages)
                    existing["timestamp"] = datetime.datetime.now().strftime("%I:%M %p")
                else:
                    # Create new chat entry — use first user message as title
                    first_msg = next(
                        (m["content"][:40] for m in st.session_state.messages if m["role"] == "user"),
                        "New Chat",
                    )
                    chat_history.insert(0, {
                        "id": active_id,
                        "title": first_msg,
                        "timestamp": datetime.datetime.now().strftime("%I:%M %p"),
                        "messages": len(st.session_state.messages),
                        "is_active": True,
                    })
                st.session_state.chat_history = chat_history

                st.rerun()
            
            # Chat Input (Bottom)
            prompt = st.chat_input(
                "Say or record something",
                accept_audio=True)
            if prompt and prompt.text:
                # Fetch news for this query
                st.session_state.chat_news[active_chat_id] = news_service.get_relevant_news(prompt.text)
                st.session_state.messages.append({"role": "user", "content": prompt.text})
                st.rerun()
            if prompt and prompt.audio:
                 st.session_state.chat_news[active_chat_id] = news_service.get_relevant_news("transaction analysis")
                 st.session_state.messages.append({"role": "user", "content": f"[Audio: {prompt.audio.name}]"})
                 st.rerun()

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Chat - Prime Analyst")
    render_chat()