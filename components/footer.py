"""
Footer component for PayInsight AI
"""
import streamlit as st


# Default footer configuration
DEFAULT_FOOTER = {
    "text": "Powered by LangGraph | Team primeFactors",
    "show_divider": True
}


def render_footer(
    text: str = None,
    show_divider: bool = True
):
    """
    Render the footer section.
    
    Args:
        text: Footer text to display
        show_divider: Whether to show a divider above footer
    """
    if show_divider:
        st.divider()
    
    footer_text = text or DEFAULT_FOOTER["text"]
    st.caption(footer_text)


def render_footer_with_links(
    main_text: str = None,
    links: dict = None,
    show_divider: bool = True
):
    """
    Render footer with additional links.
    
    Args:
        main_text: Main footer text
        links: Dictionary of {label: url} pairs
        show_divider: Whether to show divider
    """
    if show_divider:
        st.divider()
    
    cols = st.columns([2, 1, 1, 1])
    
    with cols[0]:
        st.caption(main_text or DEFAULT_FOOTER["text"])
    
    if links:
        for i, (label, url) in enumerate(links.items()):
            if i < 3:  # Max 3 link columns
                with cols[i + 1]:
                    st.markdown(f"[{label}]({url})")


def render_version_info(version: str = "1.0.0"):
    """
    Render version information.
    
    Args:
        version: Version string to display
    """
    st.caption(f"Version {version}")
