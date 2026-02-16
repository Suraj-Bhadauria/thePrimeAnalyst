import streamlit as st
import pandas as pd
from src.graph.workflow import Workflow
from src.utils.data_loader import data_loader
from src.config import config
import plotly.express as px

# Page config
st.set_page_config(
    page_title="PayInsight AI",
    page_icon="💡",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .stChatMessage {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize
@st.cache_resource
def init_workflow():
    """Initialize the workflow (cached)"""
    return Workflow()

@st.cache_data
def load_sample_data():
    """Load sample data for display"""
    df = data_loader.load_data()
    return df.head(100)

# Header
st.markdown('<p class="main-header">💡 PayInsight AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Leadership Analytics - Ask questions about transaction data in natural language</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("📊 Dataset Info")
    
    try:
        df = data_loader.load_data()
        st.metric("Total Transactions", f"{len(df):,}")
        st.metric("Date Range", f"{df.shape[0]} records")
        st.metric("Columns", df.shape[1])
        
        with st.expander("View Sample Data"):
            st.dataframe(df.head(10), use_container_width=True)
        
        with st.expander("Column Descriptions"):
            for col, desc in config.TRANSACTION_COLUMNS.items():
                st.write(f"**{col}**: {desc}")
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
    
    st.divider()
    
    st.header("💡 Example Questions")
    example_questions = [
        "What is the average transaction amount?",
        "Which age group uses P2P most?",
        "Compare failure rates between Android and iOS",
        "What are the peak hours for food delivery?",
        "Which transaction type has highest failure rate?",
        "Show me fraud flag rate for high-value transactions",
        "Which states have the most transactions?",
        "Compare 4G vs 5G transaction success rates"
    ]
    
    for i, question in enumerate(example_questions):
        if st.button(question, key=f"example_{i}", use_container_width=True):
            st.session_state.selected_question = question

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'workflow' not in st.session_state:
    with st.spinner("Initializing AI agents..."):
        st.session_state.workflow = init_workflow()
    st.success("✅ AI system ready!")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle selected question from sidebar
if 'selected_question' in st.session_state:
    user_input = st.session_state.selected_question
    del st.session_state.selected_question
else:
    user_input = st.chat_input("Ask a question about transaction data...")

# Process user input
if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data..."):
            try:
                # Prepare conversation history
                conv_history = [
                    {"question": msg["content"], "response": st.session_state.messages[i+1]["content"]}
                    for i, msg in enumerate(st.session_state.messages[:-1])
                    if msg["role"] == "user" and i+1 < len(st.session_state.messages)
                ]
                
                # Run workflow
                response = st.session_state.workflow.run(
                    user_input,
                    conv_history
                )
                
                st.markdown(response)
                
            except Exception as e:
                response = f"⚠️ I encountered an error: {str(e)}\n\nPlease try rephrasing your question."
                st.error(response)
    
    # Add assistant message
    st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.divider()
st.caption("Powered by LangGraph | Team primeFactors")