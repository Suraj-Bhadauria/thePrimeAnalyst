"""
Header component for PayInsight AI
"""
import streamlit as st


# Default configuration
DEFAULT_CONFIG = {
    "title": "PayInsight AI",
    "subtitle": "Leadership Analytics - Ask questions about transaction data in natural language",
    "icon": ":chart_with_upwards_trend:",
    "page_title": "PayInsight AI",
    "layout": "wide"
}


def configure_page(
    page_title: str = None,
    page_icon: str = None,
    layout: str = None
):
    """
    Configure Streamlit page settings.
    Must be called before any other Streamlit commands.
    
    Args:
        page_title: Browser tab title
        page_icon: Favicon/icon for the page
        layout: Page layout ('wide' or 'centered')
    """
    st.set_page_config(
        page_title=page_title or DEFAULT_CONFIG["page_title"],
        page_icon=page_icon or DEFAULT_CONFIG["icon"],
        layout=layout or DEFAULT_CONFIG["layout"]
    )


def render_header(
    title: str = None,
    subtitle: str = None,
    show_subtitle: bool = True
):
    """
    Render the main header section.
    
    Args:
        title: Main header text (supports HTML)
        subtitle: Subheader text
        show_subtitle: Whether to display the subtitle
    """
    header_text = title or DEFAULT_CONFIG["title"]
    st.markdown(
        f'<p class="main-header">{header_text}</p>',
        unsafe_allow_html=True
    )
    
    if show_subtitle:
        subtitle_text = subtitle or DEFAULT_CONFIG["subtitle"]
        st.markdown(
            f'<p class="sub-header">{subtitle_text}</p>',
            unsafe_allow_html=True
        )


def render_logo(logo_path: str = None, width: int = 200):
    """
    Render a logo image if provided.
    
    Args:
        logo_path: Path to logo image file
        width: Logo width in pixels
    """
    if logo_path:
        st.image(logo_path, width=width)
