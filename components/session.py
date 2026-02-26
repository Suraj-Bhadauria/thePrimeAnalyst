"""
Session state management for Prime Analyst
"""
import streamlit as st
from typing import Any, List, Dict, Optional


def init_session_state(
    workflow_factory=None,
    show_init_message: bool = True
):
    """
    Initialize all session state variables.
    
    Args:
        workflow_factory: Callable that creates a workflow instance
        show_init_message: Whether to show initialization success message
    """
    # Initialize messages
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # Initialize chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Initialize workflow
    if 'workflow' not in st.session_state and workflow_factory:
        with st.spinner("Initializing AI agents..."):
            st.session_state.workflow = workflow_factory()
        # Header removed as requested - system initializes silently
    
    # Initialize other state
    if 'model_settings' not in st.session_state:
        st.session_state.model_settings = {
            "temperature": 0.7,
            "max_tokens": 1000
        }
    
    if 'data_settings' not in st.session_state:
        st.session_state.data_settings = {
            "cache_enabled": True
        }


def get_workflow():
    """
    Get the workflow instance from session state.
    
    Returns:
        Workflow instance or None
    """
    return st.session_state.get('workflow', None)


def get_messages() -> List[Dict[str, str]]:
    """
    Get the message history from session state.
    
    Returns:
        List of message dictionaries
    """
    return st.session_state.get('messages', [])


def add_message(role: str, content: str):
    """
    Add a message to the session state.
    
    Args:
        role: Message role ('user' or 'assistant')
        content: Message content
    """
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    st.session_state.messages.append({
        "role": role,
        "content": content
    })


def clear_messages():
    """Clear all messages from session state"""
    st.session_state.messages = []


def get_session_value(key: str, default: Any = None) -> Any:
    """
    Get a value from session state.
    
    Args:
        key: Session state key
        default: Default value if key doesn't exist
    
    Returns:
        Session state value or default
    """
    return st.session_state.get(key, default)


def set_session_value(key: str, value: Any):
    """
    Set a value in session state.
    
    Args:
        key: Session state key
        value: Value to set
    """
    st.session_state[key] = value


def delete_session_value(key: str):
    """
    Delete a value from session state.
    
    Args:
        key: Session state key to delete
    """
    if key in st.session_state:
        del st.session_state[key]
