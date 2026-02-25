# --- START OF FILE src/components/styles.py ---

"""
Custom CSS styles for Prime Analyst
"""
import streamlit as st


# Main application styles
MAIN_STYLES = """
<style>
    /* ===== TIGHTEN HEADER SPACING ===== */
    h1, h2, h3 {
        margin-top: 0.5rem !important;
        margin-bottom: 0.75rem !important;
    }
    
    /* Specific header styling */
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem !important;
    }
    
    .sub-header {
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 1rem !important;
    }
    
    /* Chat message styling */
    .stChatMessage {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    /* ===== COMPACT HERO VIEW ===== */
    .hero-chat-container {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        align-items: center;
        margin-top: 8vh;
        padding: 1rem 2rem;
        min-height: 50vh;
    }
    
    .hero-chat-title {
        font-size: 2.25rem;
        font-weight: 600;
        color: #262730;
        margin-bottom: 1.5rem !important;
        margin-top: 0 !important;
        text-align: center;
    }
    
    .hero-input-container {
        width: 100%;
        max-width: 700px;
        margin-top: 0;
    }
    
    /* Remove extra margins from text inputs in hero view */
    .hero-input-container .stTextInput {
        margin-bottom: 0 !important;
    }
    
    .hero-input-container .stTextInput > div {
        margin-bottom: 0 !important;
    }
    
    /* ===== GENERAL SPACING TIGHTENING ===== */
    /* Reduce default Streamlit element spacing */
    .element-container {
        margin-bottom: 0.5rem !important;
    }
    
    /* Tighten divider spacing */
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
</style>
"""

# Additional styles for components
SIDEBAR_STYLES = """
<style>
    .sidebar-metric {
        background: linear-gradient(135deg, #f0f2f6 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0;
        color: white;
        margin-bottom: 0.5rem;
    }
    .example-btn {
        width: 100%;
        text-align: left;
        padding: 0.5rem;
        margin-bottom: 0.25rem;
    }

    /* ===== SUBMENU ARROW REPLACEMENT ===== */
    /* 1. Hide the default chevron/arrow icon in SAC menu */
    .ant-menu-submenu-arrow {
        display: none !important;
        color: white !important;
    }

    /* 2. Inject an ellipsis (...) in its place */
    .ant-menu-submenu-title::after {
        content: "\\2026" !important;  /* Unicode for horizontal ellipsis */
        position: absolute;
        right: 16px;
        font-size: 1.2rem;
        color: #999;
        font-weight: bold;
        line-height: 1;
        transform: none !important; /* Ensure dots don't rotate when expanded */
    }
    
    /* Optional: darken dots on hover */
    .ant-menu-submenu-title:hover::after {
        color: #333;
    }
</style>
"""

CHAT_STYLES = """
<style>
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
    }
    .user-message {
        background-color: #e3f2fd;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
"""

SIDEBAR_HOVER_STYLES = """
<style>
    /* ===== ACTIVITY CARD ROW STYLING ===== */
    
    .activity-row {
        background-color: transparent; /* Transparent by default to blend */
        border-radius: 6px;
        margin-bottom: 4px !important;
        padding: 0px 15 !important;
        border: 1px solid transparent;
        transition: all 0.2s ease;
    }
    
    /* Hover state for the entire card */
    .activity-row:hover {
        background-color: rgba(0,0,0,0.04);
    }
    
    /* ACTIVE STATE: Beige Background + Dark Border */
    .activity-row.active {
        background-color: #EAE8E4; /* Beige */
        border-left: 3px solid #4A3B32 !important; /* Brown indicator */
        border-top-left-radius: 2px;
        border-bottom-left-radius: 2px;
    }

    /* ===== CRITICAL ALIGNMENT FIX ===== */
    
    /* 1. Target the columns inside the row to ensure flex centering */
    .activity-row [data-testid="column"] {
        display: flex !important;
        align-items: center !important; /* Vertically align items */
        justify-content: center !important;
        height: 100% !important;

        min-height: 42px !important; /* Force a minimum height for the row */
    }

    /* 2. Target Buttons to ensure they fill the height and align text */
    .activity-row button {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0px 20px !important; /* Horizontal padding only */
        margin: 0px !important;
        height: 100% !important; /* Fill the column height */
        min-height: 42px !important; /* Match column height */
        display: flex !important;
        align-items: center !important; /* Text vertical center */
        color: #4A3B32 !important;
        border-radius: 4px !important;
    }
    
    /* 3. Specific alignment for the Chat Link (Left Button) */
    .activity-row [data-testid="column"]:first-child button {
        justify-content: flex-start !important; /* Align text to left */
        width: 100% !important;
        font-weight: 500 !important;
        font-size: 0.95rem !important;
    }
    
    /* 4. Specific alignment for the Popover (Right Button) */
    .activity-row [data-testid="column"]:last-child button {
        justify-content: center !important; /* Center the dots */
        width: 100% !important;
        border-radius: 4px !important;
        font-size: 1.2rem !important; /* Larger dots */
        padding: 0 !important;
    }
    
    /* Hover Effects */
    .activity-row [data-testid="column"]:last-child button:hover {
        background-color: #000000 !important;

    }
    
    /* Icon Color Fix */
    .activity-row button svg {
        color: #6B5F52 !important; /* Muted brown for icons */
        fill: #6B5F52 !important;
    }
    
    /* Active State Text Bold */
    .activity-row.active button p {
        font-weight: 600 !important;
        color: #1A1614 !important;
    }
    
    /* Delete Action Red Hover */
    .delete-action button:hover {
        color: #D32F2F !important;
        background-color: #FFEBEE !important;
    }
    .delete-action button:hover svg {
        color: #D32F2F !important;
        fill: #D32F2F !important;
    }
</style>
"""

# ... (Rest of styles) ...

def get_sidebar_styles():
    """
    Returns earthy professional sidebar CSS targeting Prime Analyst design specs.
    
    Theme Colors:
    - Background: #F9F8F6 (Light Beige)
    - Text: #4A3B32 (Dark Brown)
    - Active Background: #463830 (Dark Coffee)
    - Active Text: #FFFFFF (White)
    """
    return """
<style>
    /* =============================================
       1. SIDEBAR CONTAINER & RESET (COMPACT MODE)
       ============================================= */
    
    [data-testid="stSidebar"] {
        background-color: #F9F8F6 !important;
        border-right: 1px solid rgba(0,0,0,0.05);
        padding-top: 1rem !important;
    }
    
    /* Kill default gaps and padding for tight layout */
    [data-testid="stSidebar"] .element-container,
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"],
    [data-testid="stSidebar"] [data-testid="column"],
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
    }
    
    /* Remove default Streamlit styling from buttons */
    [data-testid="stSidebar"] .stButton {
        margin: 0px !important;
        padding: 0px !important;
        border: none !important;
    }

    /* =============================================
       2. BUTTONS: NO BORDERS & CLEAN STYLE
       ============================================= */
    
    /* Target ALL buttons in sidebar */
    [data-testid="stSidebar"] button {
        border: none !important;
        box-shadow: none !important;
        background-color: transparent !important;
        color: #4A3B32 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        text-align: left !important;
        padding: 0.5rem 0.5rem !important; /* Minimal padding */
        transition: all 0.2s ease !important;
        margin: 0 !important;
        font-weight: 400 !important;
        min-height: 0px !important;
        height: auto !important;
        line-height: 1.2 !important;
    }
    
    /* Ensure button text and icons are left-aligned */
    [data-testid="stSidebar"] button p,
    [data-testid="stSidebar"] button span,
    [data-testid="stSidebar"] button div {
        text-align: left !important;
        justify-content: flex-start !important;
    }

    /* Hover state for general buttons */
    [data-testid="stSidebar"] button:hover {
        background-color: rgb(70, 56, 48, 0.6) !important;
        color: #F9F8F6 !important;
    }

    /* Focus/Active state removal */
    [data-testid="stSidebar"] button:focus,
    [data-testid="stSidebar"] button:active {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        color: #F9F8F6 !important;
        background-color: #463830 !important;
    }

    /* Primary (active) buttons — dark brown background (e.g. active chat) */
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background-color: #463830 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p,
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span,
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"] {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
        background-color: #4A3B32 !important;
        color: #FFFFFF !important;
    }
    
    /* Save and Close buttons in rename mode - add borders */
    [data-testid="stSidebar"] [data-testid="stForm"] button {
        border: 1px solid #D0C5BA !important;
        background-color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] [data-testid="stForm"] button:hover {
        border-color: #4A3B32 !important;
        background-color: #F9F8F6 !important;
    }

    /* =============================================
       3. RECENT ACTIVITY ROW (The Chat List)
       ============================================= */
    
    /* The container for each row */
    .activity-row {
        border-radius: 6px;
        margin-bottom: 0px !important;
        margin-top: 0px !important;
        padding: 0px !important;
        transition: background-color 0.1s ease;
        display: flex;
        align-items: center;
        text-align: left;
    }
    
    /* Remove all gaps inside activity rows */
    .activity-row [data-testid="column"],
    .activity-row [data-testid="stHorizontalBlock"],
    .activity-row .element-container,
    .activity-row .stButton {
        margin: 0px !important;
        padding: 0px !important;
        gap: 0px !important;
    }
    
    /* Compact button specifically in activity rows */
    .activity-row button {
        padding: 0.1rem 0.5rem !important;
        margin: 0px 10px !important;
        line-height: 1.1 !important;
        min-height: 24px !important;
        height: auto !important;
        text-align: left !important;
        justify-content: flex-start !important;
    }
    
    /* Zero out text margins inside activity row buttons */
    .activity-row button p,
    .activity-row button span {
        margin: 0px !important;
        padding: 0px !important;
        line-height: 1.1 !important;
    }
    
    /* Hover on the ROW container */
    .activity-row:hover {
        background-color: rgba(235, 232, 227, 0.5);
    }
    
    /* Ensure the main button takes full width of its column */
    .activity-row [data-testid="column"] button {
        width: 100% !important;
    }

    /* =============================================
       4. ACTIVE STATE (Dark Brown Theme)
       ============================================= */
    
    /* 
       CRITICAL: Use !important to override Streamlit's default button styling.
       We apply background to the ROW DIV, and text color to the BUTTON.
       The row div holds the brown — not the button itself — so it persists
       through all Streamlit re-renders and pseudo-state changes on the button.
    */
    
    /* The Active Row Container — persistent, not tied to any pseudo-class */
    div.activity-row.active {
        background-color: #463830 !important; /* Theme Dark Brown */
        border-radius: 6px !important;
    }

    /* The Text/Button inside active row — keep button bg transparent so row shows through */
    div.activity-row.active button,
    div.activity-row.active button p,
    div.activity-row.active button span {
        color: #FFFFFF !important; /* White Text */
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    /* Lock the brown THROUGH all transient button pseudo-states.
       Without this, :hover/:focus/:active on the button can momentarily
       re-apply Streamlit's default button background over the row div's brown. */
    div.activity-row.active button:hover,
    div.activity-row.active button:focus,
    div.activity-row.active button:active,
    div.activity-row.active button:focus-visible,
    div.activity-row.active button:focus-within {
        background-color: transparent !important;
        color: #FFFFFF !important;
        outline: none !important;
        box-shadow: none !important;
        border: none !important;
    }
    
    /* Also hold the row div brown through those same states in case any
       Streamlit rule targets the parent element */
    div.activity-row.active:hover,
    div.activity-row.active:focus-within {
        background-color: #463830 !important;
    }

    /* =============================================
       5. POPOVER (Three Dots)
       ============================================= */
    
    /* 5a. HIDE THE DROPDOWN ARROW SVG COMPLETELY */
    [data-testid="stSidebar"] [data-testid="stPopover"] button svg,
    [data-testid="stSidebar"] [data-testid="stPopover"] button > svg {
        display: none !important;
    }

    /* 5b. ELLIPSIS VISIBILITY - ONLY ON POPOVER HOVER */
    
    /* Base State: Hidden (transparent) */
    [data-testid="stSidebar"] [data-testid="stPopover"] button,
    [data-testid="stSidebar"] div[data-testid="stPopover"] button {
        color: transparent !important; 
        background: transparent !important;
        padding: 0px !important;
        width: 20px !important; 
        min-width: 20px !important;
        justify-content: center !important;
        transition: color 0.15s ease !important;
    }
    
    /* Ensure text inside follows the same color */
    [data-testid="stSidebar"] [data-testid="stPopover"] button p,
    [data-testid="stSidebar"] [data-testid="stPopover"] button span {
        color: inherit !important;
    }

    /* Popover Hover: Visible (Dark Brown) - Show ellipsis only when hovering popover */
    [data-testid="stSidebar"] [data-testid="stPopover"]:hover button,
    [data-testid="stSidebar"] div[data-testid="stPopover"]:hover button {
        color: #6B5F52 !important;
    }

    /* Active Row Popover Hover: Visible (White) */
    div.activity-row.active [data-testid="stPopover"]:hover button,
    [data-testid="stSidebar"] div.activity-row.active [data-testid="stPopover"]:hover button {
        color: #FFFFFF !important;
    }

    /* =============================================
       6. POPOVER TRAY (The Menu that opens)
       ============================================= */
    
    [data-baseweb="popover"] {
        border-radius: 8px !important;
        border: 1px solid #E5E1DB !important;
        background-color: #FFFFFF !important;
        padding: 4px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
        min-width: 110px !important;
    }
    
    /* Remove all spacing from Streamlit containers inside popover */
    [data-baseweb="popover"] .element-container,
    [data-baseweb="popover"] [data-testid="stVerticalBlock"],
    [data-baseweb="popover"] .stMarkdown,
    [data-baseweb="popover"] .stButton {
        margin: 0px !important;
        padding: 0px !important;
        gap: 0px !important;
    }
    
    /* Remove spacing from popover-action wrapper divs */
    .popover-action {
        margin: 0px !important;
        padding: 0px !important;
    }

    /* The buttons inside the tray */
    .popover-action button {
        width: 100% !important;
        text-align: left !important;
        padding: 4px 8px !important;
        margin: 1px 0px !important;
        border-radius: 4px !important;
        font-size: 0.85rem !important;
        background: transparent !important;
        color: #4A3B32 !important;
        height: auto !important;
        min-height: 26px !important;
        line-height: 1.2 !important;
    }
    
    /* Remove margin from button text */
    .popover-action button p,
    .popover-action button span {
        margin: 0px !important;
        padding: 0px !important;
    }

    .popover-action button:hover {
        background-color: #F0F2F6 !important;
    }
    
    .popover-action.delete button {
        color: #D32F2F !important;
    }
    .popover-action.delete button:hover {
        background-color: #FFEBEE !important;
    }

    /* =============================================
       7. NEW CHAT BUTTON
       ============================================= */
    .new-chat-button button {
        background-color: #463830 !important; /* Dark Brown */
        color: #FFFFFF !important;
        box-shadow: 0 2px 4px rgba(70, 56, 48, 0.2) !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 0.6rem !important;
        margin-bottom: 1rem !important;
    }
    .new-chat-button button:hover {
        background-color: #362A24 !important;
        box-shadow: 0 4px 8px rgba(70, 56, 48, 0.3) !important;
    }
    
    /* =============================================
       8. UTILITY
       ============================================= */
    /* Remove separators that cause "brown lines" */
    [data-testid="stSidebar"] hr {
        margin: 0.5rem 0 !important;
        border-color: #E5E1DB !important;
        opacity: 0.5;
    }
</style>
"""

def get_home_css():
    """
    Returns CSS for the Home Page component.
    Warm earthy theme with dot pattern background.
    """
    return """
<style>
    div[data-testid="stVerticalBlock"]:has(.hero-card-container) {
        background: #F9F8F6; /* Light Beige */
        padding: 1rem 1rem;
        min-height: 80vh;
        display: flex;
        flex-direction: column;;
        align-items: left;
        justify-content: center;
        border-radius: 12px;
    }
    /* ===== PILL BADGE ===== */
    .pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: rgba(168, 197, 181, 0.15);
        border: 1px solid rgba(168, 197, 181, 0.3);
        border-radius: 24px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 1px;
        color: #3E3229;
        margin-bottom: 1.5rem;
        text-transform: uppercase;
    }
    
    .pill-badge::before {
        content: '';
        width: 8px;
        height: 8px;
        background: #A8C5B5;
        border-radius: 50%;
        display: inline-block;
    }
    
    /* ===== TYPOGRAPHY ===== */
    .big-title {
        font-size: 5.5rem;
        font-weight: 700;
        color: #3E3229;
        margin: 0 0 1rem 0;
        letter-spacing: -2px;
        line-height: 1.1;
        text-align: left;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .subtitle-text {
        font-size: 1.25rem;
        color: #6B5F52;
        max-width: 700px;
        text-align: left;
        line-height: 1.7;
        margin: 0 0 4rem 0;
        font-weight: 400;
    }

    /* ===== CTA BUTTON STYLING ===== */
    
    /* 1. Hide the locator div itself so it doesn't take up space */
    .cta-locator {
        display: none;
    }

    /* 2. Target the button immediately following the locator */
    /* Logic: Find the div containing the locator -> Select the NEXT sibling div -> Select the button inside it */
    div:has(.cta-locator) + div button {
        background-color: #4A3B32 !important; /* Dark Brown */
        color: white !important;
        border: 2px solid #4A3B32 !important;
        border-radius: 10px !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(62, 50, 41, 0.25) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        min-width: 200px !important;
    }
    
    /* 3. Hover State: Slide Up + Cream Background */
    div:has(.cta-locator) + div button:hover {
        background-color: #FDFBF7 !important; /* Cream */
        color: #4A3B32 !important; /* Brown Text */
        border-color: #4A3B32 !important;
        transform: translateY(-5px) !important;
        box-shadow: 0 12px 24px rgba(74, 59, 50, 0.15) !important;
    }


    /* 4. Ensure Icon and Text change color on hover */
    div:has(.cta-locator) + div button:hover p,
    div:has(.cta-locator) + div button:hover span,
    div:has(.cta-locator) + div button:hover svg {
        color: #4A3B32 !important;
        fill: #4A3B32 !important;
    }

    /* 5. Active/Click State */
    div:has(.cta-locator) + div button:active {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(74, 59, 50, 0.2) !important;
    }
    
    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {
        .big-title { font-size: 2.5rem; letter-spacing: -1px; }
        .subtitle-text { font-size: 1rem; }
    }
</style>
"""

def get_dashboard_css():
    """
    Returns CSS for the Dashboard component.
    """
    return """
<style>
    /* ===== DASHBOARD MARKERS ===== */
    .dashboard-header-container, .chart-card-container {
        display: none;
    }
    
    /* ===== HEADER TYPOGRAPHY ===== */
    .dashboard-header {
        margin-bottom: 1rem;
    }
    
    .dashboard-title {
        font-size: 2.25rem;
        font-weight: 700;
        color: #4A3B32;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.5px;
    }
    
    .dashboard-subtitle {
        font-size: 1rem;
        color: #6B5F52;
        margin: 0;
        font-weight: 400;
    }
    
    /* ===== HEADER CONTROLS (BUTTONS) ===== */
    button[kind="secondary"] div[data-testid="stPopover"] button {
        background-color: transparent !important;
        border: 1px solid #D0C5BA !important;
        color: #4A3B32 !important;
        border-radius: 8px !important;
        padding: 0.4rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    
    button[kind="secondary"]:hover div[data-testid="stPopover"] button:hover {
        background-color: #FDFBF7 !important;
        border-color: #4A3B32 !important;
        color: #262730 !important;
        transform: translateY(-1px) !important;
    }
    
    /* ===== KPI CARDS (HTML Based) ===== */
    .dashboard-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        height: 100%;
        transition: all 0.3s ease;
        border: 1px solid rgba(74, 59, 50, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    
    .dashboard-card:hover {
        box-shadow: 0 6px 16px rgba(74, 59, 50, 0.08);
        transform: translateY(-2px);
        border-color: #A8C5B5;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #8B7B6F;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #4A3B32;
        margin: 0 0 0.5rem 0;
        line-height: 1;
    }
    
    .metric-delta {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 6px;
        width: fit-content;
    }
    
    .positive-trend { color: #2E7D32; background: rgba(46, 125, 50, 0.1); }
    .negative-trend { color: #C62828; background: rgba(198, 40, 40, 0.1); }
    
    /* ===== CHART CARDS (Container Based) ===== */
    /* Target the stVerticalBlock that contains the .chart-card-container marker */
    div[data-testid="stVerticalBlock"]:has(.chart-card-container) {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        border: 1px solid rgba(74, 59, 50, 0.08);
        height: 100%;
    }
    
    .chart-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #4A3B32;
        margin: 0 0 1.5rem 0;
        border-bottom: 1px solid #F0F2F6;
        padding-bottom: 0.75rem;
    }
    
    /* ===== PLOTLY FIXES ===== */
    .js-plotly-plot .plotly .modebar { display: none !important; }
</style>
"""

def get_analytics_css():
    """
    Returns custom CSS for the Analytics Dashboard.
    """
    return """
    <style>
        /* =============================================
           1. PAGE BACKGROUND & LAYOUT
        ============================================= */
        .stApp {
            background-color: #F2F1EF;
        }
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background-color: transparent;
        }

        /* =============================================
           2. TYPOGRAPHY
           Note: stMarkdownContainer p is intentionally
           NOT scoped globally — it would style all paragraph
           text app-wide. Filter panel labels are handled
           via .st-key-analytics_filter_panel in section 5.
        ============================================= */
        h1, h2, h3, h4, h5, h6 {
            color: #111827 !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         Helvetica, Arial, sans-serif !important;
        }
        h1 { font-weight: 700; letter-spacing: -0.025em; }
        h3 { font-weight: 600; letter-spacing: -0.01em; }

        div[data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            color: #111827 !important;
        }
        div[data-testid="stMetricLabel"] {
            color: #6B7280 !important;
        }

        /* =============================================
        3. TABS — earthy brown active underline
        ============================================= */
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            background-color : transparent !important;
            border-bottom    : 2px solid #E5E0D8 !important;
            gap              : 0 !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab"] {
            height        : 48px;
            font-weight   : 600;
            font-size     : 0.95rem;
            color         : #6B5F52 !important;
            padding       : 8px 18px !important;
            border-radius : 6px 6px 0 0 !important;
            border        : 1px solid transparent !important;
            border-bottom : none !important;
            transition    : color 0.15s ease, background-color 0.15s ease;
        }
        div[data-testid="stTabs"] [data-baseweb="tab"]:hover {
            color            : #4A3B32 !important;
            background-color : rgba(74, 59, 50, 0.05) !important;
        }
        div[data-testid="stTabs"] [aria-selected="true"] {
            color            : #4A3B32 !important;
            background-color : #F9F8F6 !important;
            border-color     : #E5E0D8 !important;
            border-bottom    : 2px solid #F9F8F6 !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background-color : #4A3B32 !important;
            height           : 2px !important;
        }
        div[data-testid="stTabPanel"] {
            background-color : #F9F8F6 !important;
            border           : 1px solid #E5E0D8 !important;
            border-top       : none !important;
            border-radius    : 0 0 10px 10px !important;
            padding          : 1rem !important;
        }
        /* =============================================
           4. PLOTLY CHARTS — off-white inner background
        ============================================= */
        .js-plotly-plot {
            border-radius: 8px;
            background-color: #FAFAF9;
            margin-bottom: 8px;
        }

        /* =============================================
           5. FILTER PANEL
           Scoped entirely to .st-key-analytics_filter_panel.
           Cannot reach the sidebar or any other page.
        ============================================= */

        /* Panel wrapper */
        .st-key-analytics_filter_panel {
            background-color: #F9F8F6;
            border-radius: 12px;
        }

        /* Form label text — uppercase, earthy */
        .st-key-analytics_filter_panel div[data-testid="stForm"] p {
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6B5F52;
            margin-bottom: 0.25rem;
        }

        /* Tighten spacing between form elements */
        .st-key-analytics_filter_panel div[data-testid="stForm"] .element-container {
            margin-bottom: 0.75rem;
        }

        /* Apply button — dark brown, scoped to this panel only */
        .st-key-analytics_filter_panel button[kind="primaryFormSubmit"],
        .st-key-analytics_filter_panel button[kind="primary"] {
            background-color: #4A3B32 !important;
            border-color: #4A3B32 !important;
            color: #FFFFFF !important;
            font-weight: 600;
        }
        .st-key-analytics_filter_panel button[kind="primaryFormSubmit"] p,
        .st-key-analytics_filter_panel button[kind="primaryFormSubmit"] span,
        .st-key-analytics_filter_panel button[kind="primaryFormSubmit"] svg,
        .st-key-analytics_filter_panel button[kind="primary"] p,
        .st-key-analytics_filter_panel button[kind="primary"] span,
        .st-key-analytics_filter_panel button[kind="primary"] svg {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }
        .st-key-analytics_filter_panel button[kind="primaryFormSubmit"]:hover,
        .st-key-analytics_filter_panel button[kind="primary"]:hover {
            background-color: #2E1F14 !important;
            border-color: #2E1F14 !important;
        }
        /* Reset button — scoped to its own key, subtle link style */
        .st-key-filter_reset_btn button {
            background-color: transparent !important;
            border: none !important;
            color: #9CA3AF !important;
        }
        .st-key-filter_reset_btn button:hover {
            color: #4A3B32 !important;
            background: transparent !important;
            text-decoration: underline;
        }

        /* =============================================
           6. EXPORT CSV BUTTON
           Scoped to its own key only.
        ============================================= */
        .st-key-export_csv_btn button {
            background-color: #FDFBF7 !important;
            border-color: #D9D0CA !important;
            color: #4A3B32 !important;
            font-weight: 500;
        }
        .st-key-export_csv_btn button:hover {
            background-color: #EDE8DF !important;
            border-color: #4A3B32 !important;
        }

        /* =============================================
           7. SECTION CONTAINERS
           White background for all chart section cards.
        ============================================= */
        .st-key-section_txn_overview,
        .st-key-section_comparison,
        .st-key-section_temporal,
        .st-key-section_geo_failure,
        .st-key-section_stats,
        .st-key-section_rankings,
        .st-key-section_bank_matrix,
        .st-key-section_fraud,
        .st-key-section_txn_table,
        .st-key-section_network,
        .st-key-section_forecast,
        .st-key-section_correlation {
            background-color: #FFFFFF;
        }

        /* Inset stat/metric cards — slightly off-white */
        .st-key-stats_desc_card,
        .st-key-network_metrics_card {
            background-color: #F9F8F6;
        }

        /* =============================================
           8. KPI CARDS — all share the kpi_ prefix
        ============================================= */
        [class*="st-key-kpi_"] {
            background-color: #FFFFFF;
        }

        /* =============================================
           9. TABLES & DATAFRAMES
           Scoped to specific section keys only.
        ============================================= */
        .st-key-section_txn_table div[data-testid="stTable"] {
            font-size: 0.9rem;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            overflow: hidden;
        }
        .st-key-section_txn_table thead tr th {
            background-color: #F9FAFB !important;
            color: #4B5563 !important;
        }

        /* Progress bars — scoped to sections that have them */
        .st-key-section_txn_table div[data-testid="stDataFrame"] [role="progressbar"] > div,
        .st-key-section_rankings div[data-testid="stDataFrame"] [role="progressbar"] > div,
        .st-key-section_fraud div[data-testid="stDataFrame"] [role="progressbar"] > div {
            background-color: #4A3B32 !important;
        }

        /* =============================================
           10. MISC COMPONENTS
        ============================================= */
        .streamlit-expanderHeader {
            background-color: #FDFBF7;
            border: 1px solid #E5E1DB;
            border-radius: 8px;
            color: #4A3B32;
        }
        .status-success { color: #4A7C59; font-weight: 600; }
        .status-failed  { color: #B44C3A; font-weight: 600; }
        text.nums {
            font-family: 'Roboto Mono', monospace;
            font-weight: bold;
        }
    </style>
    """

def get_report_css() -> str:
    """
    Returns the full CSS block for the Reports Generator page.
    Inject with: st.markdown(get_report_css(), unsafe_allow_html=True)

    Covers:
      - Page / container chrome
      - Config card, action bar, preview panel, right-filter panel
      - Tabs (Summary / Charts / Tables / Full Report)
      - KPI metric cards
      - AI Insights panel + depth badge
      - Named helpers: .report-section-label, .preview-section-header, .rg-generated-badge
      - Streamlit widget overrides (selectbox, radio, segmented control, toggle,
        multiselect, text-area, date-input, dataframe, expander, popover, divider)
      - Download / action buttons
    """
    return """
<style>
/* ================================================================
   PRIME ANALYST — REPORTS GENERATOR
   Palette  (mirrors analytics.py)
     primary   #4A3B32 | secondary  #6B5F52 | accent    #2563EB
     success   #4A7C59 | warning    #C17F24 | danger    #B44C3A
     upi       #C2673A | rupay      #5C7A3E
     bg        #F2F1EF | card       #FFFFFF  | muted     #6B7280
   ================================================================ */


/* ── 0. EARTHY WIDGET COLOR OVERRIDES ───────────────────────
   Streamlit sets widget accent colors as inline style attributes
   via React (e.g. style="background-color: rgb(255,75,75)").
   We override every component with !important selectors AND
   [style*="255"] attribute fallbacks to catch inline reds.
   A JS MutationObserver in reports.py handles React re-renders.
────────────────────────────────────────────────────────────── */

/* CSS custom property fallback (works when Streamlit reads var()) */
:root {
    --primary-color              : #4A3B32;
    --primary-background-color   : rgba(74, 59, 50, 0.08);
}

/* ── MULTISELECT TAG PILLS ─────────────────────────────────
   Streamlit injects: style="background-color: rgb(255,75,75)"
   on <span data-baseweb="tag">. We override all three colors. */
[data-baseweb="tag"],
span[data-baseweb="tag"] {
    background-color : #EAE5E0 !important;
    color            : #4A3B32 !important;
    border-color     : #C9BFB8 !important;
    border-radius    : 4px !important;
    font-size        : 11px !important;
    font-weight      : 600 !important;
}
/* Catch any remaining inline red on tag children */
[data-baseweb="tag"] * { color: #4A3B32 !important; }
[data-baseweb="tag"] svg,
[data-baseweb="tag"] [role="presentation"] svg {
    color: #6B5F52 !important;
    fill:  #6B5F52 !important;
}

/* ── RADIO BUTTON ───────────────────────────────────────────
   Outer ring always earthy brown, inner dot filled when checked.
   Remove any background highlight on the label row. */
[data-baseweb="radio"] label {
    background-color : transparent !important;
}
[data-baseweb="radio"] label:hover {
    background-color : transparent !important;
}
/* Outer ring div */
[data-baseweb="radio"] label > div > div {
    border-color : #4A3B32 !important;
}
/* Inner filled dot */
[data-baseweb="radio"] label > div > div > div {
    background-color : #4A3B32 !important;
}
/* Catch any div inside radio with inline red bg */
[data-baseweb="radio"] div[style*="rgb(255"],
[data-baseweb="radio"] div[style*="255, 75"] {
    background-color : #4A3B32 !important;
    border-color     : #4A3B32 !important;
}

/* ── SEGMENTED CONTROL (Platform / AI Insight Depth) ────────
   Active button uses outlined style — earthy border + text.
   Scoped to stMain so it cannot bleed into the sidebar. */
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button {
    border-color     : #D9D0CA !important;
    color            : #6B5F52 !important;
    background-color : transparent !important;
}
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button[data-active="true"] {
    color            : #4A3B32 !important;
    border-color     : #4A3B32 !important;
    border-width     : 2px !important;
    background-color : rgba(74, 59, 50, 0.07) !important;
    font-weight      : 700 !important;
}
/* Inline-style fallback for red text/border */
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button[style*="rgb(255"],
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button[style*="255, 75"] {
    color            : #4A3B32 !important;
    border-color     : #4A3B32 !important;
    background-color : rgba(74, 59, 50, 0.07) !important;
}

/* ── TOGGLE LABEL ───────────────────────────────────────────
   Force transparent bg so primaryColor brown doesn't tint it.
   Target the stWidgetLabel parent wrapper specifically. */
section[data-testid="stMain"] div[data-testid="stToggle"],
section[data-testid="stMain"] div[data-testid="stToggle"] *:not([role="switch"]),
section[data-testid="stMain"] div[data-testid="stToggle"] div:has(> [data-testid="stWidgetLabel"]) {
    background-color : transparent !important;
    background       : transparent !important;
}

/* ── TAB HIGHLIGHT BAR ──────────────────────────────────────
   The sliding underline div gets inline background-color red. */
[data-baseweb="tab-highlight"],
div[data-baseweb="tab-highlight"] {
    background-color : #4A3B32 !important;
    height           : 2px !important;
}
[data-baseweb="tab-highlight"][style*="255"],
[data-baseweb="tab-highlight"][style*="rgb(255"] {
    background-color : #4A3B32 !important;
}
/* ── CHECKBOX ───────────────────────────────────────────────
   Checked checkbox fill → earthy brown. */
div[data-testid="stCheckbox"] input:checked + div,
div[data-testid="stCheckbox"] [data-checked="true"] {
    background-color : #4A3B32 !important;
    border-color     : #4A3B32 !important;
}
div[data-testid="stCheckbox"] [style*="rgb(255"],
div[data-testid="stCheckbox"] [style*="255, 75"] {
    background-color : #4A3B32 !important;
    border-color     : #4A3B32 !important;
}

/* ── REMOVE ALL SELECTION HIGHLIGHT BACKGROUNDS ─────────────
   Streamlit uses primaryColor at ~8% opacity as the hover/focus
   background on radio rows, toggle rows, and option lists.
   With red as primary this gives an unwanted brown/red tint. */
[data-baseweb="radio"] label:hover,
[data-baseweb="radio"] label:focus-within,
[data-baseweb="radio"] label[data-checked="true"],
[data-baseweb="radio"] [data-focused="true"] {
    background-color : transparent !important;
    box-shadow       : none !important;
}
div[data-testid="stRadio"] > div > div > div {
    background-color : transparent !important;
}

/* ── FOCUS RINGS ────────────────────────────────────────────
   Soft earthy outline, no red. Scoped to stMain only. */
section[data-testid="stMain"] *:focus-visible {
    outline-color : rgba(74, 59, 50, 0.5) !important;
    box-shadow    : 0 0 0 3px rgba(74, 59, 50, 0.15) !important;
}
section[data-testid="stMain"] [data-baseweb="select"]:focus-within,
section[data-testid="stMain"] [data-baseweb="input"]:focus-within {
    background-color : #FFFFFF !important;
    border-color : #4A3B32 !important;
    box-shadow   : 0 0 0 2px rgba(74, 59, 50, 0.15) !important;
}


/* ── 1. PAGE SHELL ──────────────────────────────────────────── */

div[data-testid="stMainBlockContainer"],
.main .block-container {
    background-color : #F2F1EF !important;
    padding-top      : 1.25rem !important;
    padding-bottom   : 2rem !important;
    font-family      : 'DM Sans', 'Segoe UI', system-ui, sans-serif;
    color            : #111827;
}


/* ── 2. BORDERED CONTAINERS (cards) ────────────────────────── */

div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border           : 1px solid #E5E0D8 !important;
    border-radius    : 10px !important;
    box-shadow       : 0 1px 4px rgba(74, 59, 50, 0.06) !important;
}

/* Header bar — clean, no shadow */
div[data-testid="stVerticalBlock"][data-key="rg_header"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border-bottom    : 2px solid #E5E0D8 !important;
    border-radius    : 0 !important;
    box-shadow       : none !important;
}

/* Config card — accent left border */
div[data-testid="stVerticalBlock"][data-key="rg_config_card"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-left   : 3px solid #4A3B32 !important;
    border-radius : 8px !important;
}

/* Action bar — elevated bottom chrome */
div[data-testid="stVerticalBlock"][data-key="rg_action_bar"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border-top       : 2px solid #E5E0D8 !important;
    border-radius    : 0 0 10px 10px !important;
    box-shadow       : 0 -2px 8px rgba(74, 59, 50, 0.04) !important;
}

/* Preview panel — dashed outline */
div[data-testid="stVerticalBlock"][data-key="rg_preview_panel"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border           : 1.5px dashed #C9BFB8 !important;
    border-radius    : 10px !important;
}

/* Right filter panel — sticky */
div[data-testid="stVerticalBlock"][data-key="rg_right_panel"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FAFAF9 !important;
    border           : 1px solid #E5E0D8 !important;
    border-radius    : 10px !important;
    position         : sticky;
    top              : 1rem;
}

/* KPI cards — hover lift */
div[data-testid^="stVerticalBlock"][data-key^="rg_kpi_"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border           : 1px solid #E5E0D8 !important;
    border-radius    : 8px !important;
    box-shadow       : 0 1px 3px rgba(74, 59, 50, 0.05) !important;
    transition       : box-shadow 0.2s ease, transform 0.2s ease;
}
div[data-testid^="stVerticalBlock"][data-key^="rg_kpi_"]
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow : 0 4px 12px rgba(74, 59, 50, 0.10) !important;
    transform  : translateY(-1px);
}

/* AI insights panel — secondary left stripe */
div[data-testid="stVerticalBlock"][data-key="rg_ai_panel"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border-left      : 3px solid #6B5F52 !important;
    border-radius    : 8px !important;
}

/* Revenue trends section */
div[data-testid="stVerticalBlock"][data-key="rg_trends_section"]
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color : #FFFFFF !important;
    border-radius    : 10px !important;
}


/* ── 2b. TYPOGRAPHY (mirrors analytics.py) ──────────────────── */

h1, h2, h3, h4, h5, h6 {
    color       : #111827 !important;
    font-family : -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                  Helvetica, Arial, sans-serif !important;
}
h1 { font-weight: 700; letter-spacing: -0.025em; }
h3 { font-weight: 600; letter-spacing: -0.01em; }


/* ── 3. TABS ────────────────────────────────────────────────── */

section[data-testid="stMain"] .stTabs [data-baseweb="tab-list"] {
    gap           : 0;
    border-bottom : 2px solid #E5E0D8;
    padding-bottom: 0;
}
section[data-testid="stMain"] .stTabs [data-baseweb="tab"] {
    height           : 48px;
    background-color : transparent;
    border-radius    : 6px 6px 0 0;
    border           : 1px solid transparent;
    border-bottom    : none;
    color            : #6B5F52;
    font-weight      : 600;
    font-size        : 0.95rem;
    padding          : 0 18px;
    transition       : color 0.15s ease, background-color 0.15s ease;
}
section[data-testid="stMain"] .stTabs [data-baseweb="tab"]:hover {
    color            : #4A3B32;
    background-color : rgba(74, 59, 50, 0.05);
}
section[data-testid="stMain"] .stTabs [data-baseweb="tab-highlight"] {
    background-color : #4A3B32 !important;
    height           : 2px;
}
section[data-testid="stMain"] div[data-testid="stTabPanel"] {
    background-color : #FFFFFF;
    border           : 1px solid #E5E0D8;
    border-top       : none;
    border-radius    : 0 0 10px 10px;
    padding          : 1rem;
}

/* ── 4. NAMED HELPER CLASSES ────────────────────────────────── */

/* Sub-label above right-panel controls */
p.report-section-label,
.report-section-label {
    font-size      : 10px !important;
    font-weight    : 700 !important;
    letter-spacing : 0.07em !important;
    text-transform : uppercase !important;
    color          : #8C7B6E !important;
    margin         : 10px 0 4px !important;
}

/* Section headings inside Charts / Tables tabs */
p.preview-section-header,
.preview-section-header {
    font-size      : 12px !important;
    font-weight    : 700 !important;
    color          : #6B5F52 !important;
    text-transform : uppercase !important;
    letter-spacing : 0.05em !important;
    margin         : 12px 0 6px !important;
    padding-bottom : 4px !important;
    border-bottom  : 1px solid #E5E0D8 !important;
}

/* AI depth badge  (SUMMARY / DETAILED / EXECUTIVE) */
span.rg-generated-badge,
.rg-generated-badge {
    display          : inline-block;
    font-size        : 9px !important;
    font-weight      : 700 !important;
    letter-spacing   : 0.08em !important;
    text-transform   : uppercase !important;
    color            : #4A3B32 !important;
    background-color : #EAE5E0 !important;
    border           : 1px solid #C9BFB8 !important;
    border-radius    : 20px !important;
    padding          : 2px 9px !important;
    line-height      : 1.6 !important;
    white-space      : nowrap;
}


/* ── 5. METRIC  (st.metric) ─────────────────────────────────── */

div[data-testid="stMetric"] label {
    font-size      : 10px !important;
    font-weight    : 700 !important;
    letter-spacing : 0.06em !important;
    text-transform : uppercase !important;
    color          : #6B7280 !important;
}

div[data-testid="stMetricValue"] {
    font-size   : 1.6rem !important;
    font-weight : 700 !important;
    color       : #111827 !important;
}

div[data-testid="stMetricDelta"] svg { display: none !important; }

div[data-testid="stMetricDelta"] {
    font-size   : 12px !important;
    font-weight : 600 !important;
}


/* ── 6. BUTTONS ─────────────────────────────────────────────── */

/* Action bar — primary solid buttons */
div[data-key="rg_action_bar"] button {
    background-color : #4A3B32 !important;
    color            : #F9F8F6 !important;
    border           : 1px solid #4A3B32 !important;
    border-radius    : 7px !important;
    font-weight      : 600 !important;
    font-size        : 13px !important;
    transition       : background-color 0.15s ease, transform 0.15s ease;
}
div[data-key="rg_action_bar"] button:hover {
    background-color : #6B5F52 !important;
    transform        : translateY(-1px) !important;
}

/* Preview toggle — ghost */
section[data-testid="stMain"] button[data-testid*="rg_preview_btn"] {
    background-color : transparent !important;
    color            : #4A3B32 !important;
    border           : 1.5px solid #C9BFB8 !important;
    border-radius    : 7px !important;
    font-weight      : 600 !important;
    font-size        : 13px !important;
}
section[data-testid="stMain"] button[data-testid*="rg_preview_btn"]:hover {
    background-color : #F2F1EF !important;
    border-color     : #4A3B32 !important;
}

/* Download / Generate — success green */
div[data-key="rg_action_bar"][data-testid="stDownloadButton"] button {
    background-color : #4A7C59 !important;
    border-color     : #4A7C59 !important;
    color            : #FFFFFF !important;
}
div[data-key="rg_action_bar"] [data-testid="stDownloadButton"] button:hover {
    background-color : #4A7C59 !important;
    filter           : brightness(0.88);
}

/* Reset Filters — danger ghost */
section[data-testid="stMain"] button[data-testid*="rg_reset"] {
    background-color : transparent !important;
    color            : #B44C3A !important;
    border           : 1px solid #B44C3A !important;
    border-radius    : 6px !important;
    font-size        : 12px !important;
    font-weight      : 600 !important;
}
section[data-testid="stMain"] section[data-testid="stMain"] button[data-testid*="rg_reset"]:hover {
    background-color : rgba(180, 76, 58, 0.08) !important;
}

/* Email Send button */
section[data-testid="stMain"] button[data-testid*="rg_email_send"] {
    background-color : #4A3B32 !important;
    color            : #F9F8F6 !important;
    border           : none !important;
    border-radius    : 7px !important;
    font-weight      : 600 !important;
    font-size        : 13px !important;
}
section[data-testid="stMain"] button[data-testid*="rg_email_send"]:hover {
    background-color : #6B5F52 !important;
}


/* ── 7. FORM CONTROLS ───────────────────────────────────────── */

/* Selectbox & multiselect */
section[data-testid="stMain"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
section[data-testid="stMain"] div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background-color : #FFFFFF !important;
    border           : 1px solid #D9D0CA !important;
    border-radius    : 7px !important;
    font-size        : 13px !important;
    color            : #4A3B32 !important;
}
section[data-testid="stMain"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
section[data-testid="stMain"] div[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {
    background-color : #FFFFFF !important;
    border-color : #4A3B32 !important;
    box-shadow   : 0 0 0 2px rgba(74, 59, 50, 0.12) !important;
}

/* Multiselect tags — high-specificity layer on top of section 0 */
section[data-testid="stMain"] div[data-testid="stMultiSelect"] [data-baseweb="tag"],
section[data-testid="stMain"] div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color : #EAE5E0 !important;
    color            : #4A3B32 !important;
    border-color     : #C9BFB8 !important;
}

/* Radio */
section[data-testid="stMain"] div[data-testid="stRadio"] label {
    font-size   : 13px !important;
    color       : #4A3B32 !important;
    font-weight : 500 !important;
}
/* Inner dot and outer ring — add specificity on top of section 0 */
section[data-testid="stMain"] div[data-testid="stRadio"] [data-baseweb="radio"] label > div > div > div {
    background-color : #4A3B32 !important;
}
section[data-testid="stMain"] div[data-testid="stRadio"] [data-baseweb="radio"] label > div > div {
    border-color : #4A3B32 !important;
}
section[data-testid="stMain"] div[data-testid="stRadio"] [data-baseweb="radio"] div[style*="255"],
section[data-testid="stMain"] div[data-testid="stRadio"] [data-baseweb="radio"] div[style*="rgb(255"] {
    background-color : #4A3B32 !important;
    border-color     : #4A3B32 !important;
}

/* Segmented control — add specificity layer, scoped to main content */
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button {
    font-size   : 12px !important;
    font-weight : 600 !important;
    color       : #6B5F52 !important;
    border      : 1px solid #D9D0CA !important;
}
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
section[data-testid="stMain"] div[data-testid="stSegmentedControl"] button[data-active="true"] {
    color            : #4A3B32 !important;
    border-color     : #4A3B32 !important;
    border-width     : 2px !important;
    background-color : rgba(74, 59, 50, 0.08) !important;
    font-weight      : 700 !important;
}

/* Toggle label — transparent bg */
section[data-testid="stMain"] div[data-testid="stToggle"],
section[data-testid="stMain"] div[data-testid="stToggle"] *:not([role="switch"]),
section[data-testid="stMain"] div[data-testid="stToggle"] div:has(> [data-testid="stWidgetLabel"]) {
    background-color : transparent !important;
    background       : transparent !important;
}

/* Date input */
section[data-testid="stMain"] div[data-testid="stDateInput"] input {
    background-color : #FFFFFF !important;
    border           : 1px solid #D9D0CA !important;
    border-radius    : 7px !important;
    color            : #4A3B32 !important;
    font-size        : 13px !important;
}
section[data-testid="stMain"] div[data-testid="stDateInput"] input:focus {
    background-color : #FFFFFF !important;
    border-color : #4A3B32 !important;
    box-shadow   : 0 0 0 2px rgba(74, 59, 50, 0.12) !important;
}

/* Text area (AI custom query) */
section[data-testid="stMain"] div[data-testid="stTextArea"] textarea {
    background-color : #FFFFFF !important;
    border           : 1px solid #D9D0CA !important;
    border-radius    : 7px !important;
    color            : #4A3B32 !important;
    font-size        : 12px !important;
    line-height      : 1.5 !important;
    resize           : vertical;
}
section[data-testid="stMain"] div[data-testid="stTextArea"] textarea:focus {
    background-color : #FFFFFF !important;
    border-color : #4A3B32 !important;
    box-shadow   : 0 0 0 2px rgba(74, 59, 50, 0.12) !important;
}
section[data-testid="stMain"] div[data-testid="stTextArea"] textarea::placeholder {
    color      : #A89890 !important;
    font-style : italic;
}

/* Text input (email field) */
section[data-testid="stMain"] div[data-testid="stTextInput"] input {
    background-color : #FFFFFF !important;
    border           : 1px solid #D9D0CA !important;
    border-radius    : 7px !important;
    color            : #4A3B32 !important;
    font-size        : 13px !important;
}
section[data-testid="stMain"] div[data-testid="stTextInput"] input:focus {
    background-color : #FFFFFF !important;
    border-color : #4A3B32 !important;
    box-shadow   : 0 0 0 2px rgba(74, 59, 50, 0.12) !important;
}


/* ── 8. CHECKBOX (category selector) ────────────────────────── */

section[data-testid="stMain"] div[data-testid="stCheckbox"] label {
    font-size : 12px !important;
    color     : #4A3B32 !important;
}
section[data-testid="stMain"] div[data-testid="stCheckbox"] input:checked + div {
    background-color : #4A3B32 !important;
    border-color     : #4A3B32 !important;
}


/* ── 9. EXPANDER ────────────────────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stExpander"] summary {
    background-color : #F9FAFB !important;
    border           : 1px solid #E5E0D8 !important;
    border-radius    : 6px !important;
    padding          : 8px 12px !important;
    font-size        : 12px !important;
    font-weight      : 600 !important;
    color            : #111827 !important;
    transition       : background-color 0.15s ease;
}
section[data-testid="stMain"] div[data-testid="stExpander"] summary:hover {
    background-color : #E8E4DF !important;
}
section[data-testid="stMain"] div[data-testid="stExpander"][open] summary {
    border-bottom-left-radius  : 0 !important;
    border-bottom-right-radius : 0 !important;
    border-bottom              : none !important;
}
section[data-testid="stMain"] div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background-color : #FFFFFF !important;
    border           : 1px solid #E5E0D8 !important;
    border-top       : none !important;
    border-radius    : 0 0 6px 6px !important;
    padding          : 10px 12px !important;
}


/* ── 10. DATAFRAME / TABLE ──────────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stDataFrame"] > div {
    border        : 1px solid #E5E0D8 !important;
    border-radius : 8px !important;
    overflow      : hidden;
}
section[data-testid="stMain"] div[data-testid="stDataFrame"] th {
    background-color : #F9FAFB !important;
    color            : #4B5563 !important;
    font-size        : 11px !important;
    font-weight      : 700 !important;
    text-transform   : uppercase !important;
    letter-spacing   : 0.05em !important;
    border-bottom    : 1px solid #D9D0CA !important;
}
section[data-testid="stMain"] div[data-testid="stDataFrame"] td {
    font-size : 12px !important;
    color     : #111827 !important;
}
section[data-testid="stMain"] div[data-testid="stDataFrame"] tr:nth-child(even) td {
    background-color : #F9F8F6 !important;
}
section[data-testid="stMain"] div[data-testid="stDataFrame"] tr:hover td {
    background-color : rgba(74, 59, 50, 0.04) !important;
}


/* ── 11. ALERTS / CALLOUTS ──────────────────────────────────── */

/* Info */
section[data-testid="stMain"] div[data-testid="stAlert"][kind="info"],
section[data-testid="stMain"] div[data-baseweb="notification"][kind="info"] {
    background-color : #F9F8F6 !important;
    border-left      : 3px solid #6B5F52 !important;
    border-radius    : 7px !important;
    color            : #4A3B32 !important;
    font-size        : 12px !important;
}

/* Warning */
section[data-testid="stMain"] div[data-testid="stAlert"][kind="warning"],
section[data-testid="stMain"] div[data-baseweb="notification"][kind="warning"] {
    background-color : #F9F8F6 !important;
    border-left      : 3px solid #C17F24 !important;
    border-radius    : 7px !important;
    color            : #4A3B32 !important;
    font-size        : 12px !important;
}

/* Error */
section[data-testid="stMain"] div[data-testid="stAlert"][kind="error"],
section[data-testid="stMain"] div[data-baseweb="notification"][kind="error"] {
    background-color : #F2F1EF !important;
    border-left      : 3px solid #B44C3A !important;
    border-radius    : 7px !important;
    font-size        : 12px !important;
}


/* ── 12. POPOVER (email share) ──────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stPopover"] > div {
    background-color : #FFFFFF !important;
    border           : 1px solid #E5E0D8 !important;
    border-radius    : 10px !important;
    box-shadow       : 0 8px 24px rgba(74, 59, 50, 0.12) !important;
    padding          : 12px !important;
}


/* ── 13. DIVIDERS ───────────────────────────────────────────── */

section[data-testid="stMain"] hr[data-testid="stDivider"],
section[data-testid="stMain"] hr {
    border-color : #E5E0D8 !important;
    margin       : 0.75rem 0 !important;
}


/* ── 14. CAPTION / SMALL TEXT ───────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stCaptionContainer"] p,
section[data-testid="stMain"] .stCaption {
    color     : #8C7B6E !important;
    font-size : 11px !important;
}


/* ── 15. PLOTLY CHART WRAPPER ───────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stPlotlyChart"] {
    border-radius : 8px !important;
    overflow      : hidden;
    background    : transparent !important;
}


/* ── 16. SPINNER ────────────────────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stSpinner"] > div {
    border-top-color : #4A3B32 !important;
}


/* ── 17. TOAST ──────────────────────────────────────────────── */

section[data-testid="stMain"] div[data-testid="stToast"] {
    background-color : #4A3B32 !important;
    color            : #F9F8F6 !important;
    border-radius    : 8px !important;
    font-size        : 13px !important;
    box-shadow       : 0 4px 16px rgba(74, 59, 50, 0.20) !important;
}


/* ── 18. SCROLLBAR ──────────────────────────────────────────── */

section[data-testid="stMain"] ::-webkit-scrollbar               { width: 5px; height: 5px; }
section[data-testid="stMain"] ::-webkit-scrollbar-track         { background: #F2F1EF; }
section[data-testid="stMain"] ::-webkit-scrollbar-thumb         { background: #C9BFB8; border-radius: 10px; }
section[data-testid="stMain"] ::-webkit-scrollbar-thumb:hover   { background: #6B5F52; }


</style>
"""

def get_chat_css():
    """Chat page styles with compact hero and custom SVG inputs"""
    
    return """
<style>
    /* ===== COLORS ===== */
    /* 
       Cream: #FDFBF7
       Brown: #4A3B32
       Sage:  #A8C5B5
    */

    /* ===== PAGE LAYOUT RESET ===== */
    .stMainBlockContainer, .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 1200px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    
    /* ===== CHAT MESSAGES STYLING ===== */
    
    /* 1. The Bubble Container (User & AI) */
    div[data-testid="stChatMessage"] {
        background-color: #FDFBF7 !important; /* Cream Background */
        border: 1px solid rgba(74, 59, 50, 0.1) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
    }
    
    /* 2. The Content Text */
    div[data-testid="stChatMessageContent"] {
        color: #4A3B32 !important; /* Brown Text */
    }
    
    div[data-testid="stChatMessageContent"] p {
        color: #4A3B32 !important;
        line-height: 1.6 !important;
    }
    
    /* 3. The Avatar (Icon) Container */
    div[data-testid="stChatMessageAvatar"] {
        background-color: #4A3B32 !important; /* Brown Background */
        border-radius: 50% !important;
        color: #FDFBF7 !important; /* Cream Icon */
        border: 2px solid #FDFBF7 !important; /* Tiny cream ring */
        width: 36px !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.2rem !important;
    }
    
    /* 4. Remove default Streamlit background colors/icons */
    div[data-testid="stChatMessageAvatar"] svg {
        display: none !important; /* Hide default SVG if any */
    }
    
    /* ===== CHAT INPUT STYLING ===== */
    
    /* Bottom container - let Streamlit handle positioning */
    div[data-testid="stBottom"] {
        background: linear-gradient(to top, #FDFCFB 85%, transparent) !important;
        padding-bottom: 1rem !important;
    }
    
    /* The chat input wrapper */
    div[data-testid="stChatInput"] {
        background: #FFFFFF !important;
        border: 1px solid #D9D0CA !important;
        border-radius: 24px !important;
        box-shadow: 0 2px 12px rgba(74, 59, 50, 0.1) !important;
    }
    
    /* The textarea */
    div[data-testid="stChatInput"] textarea {
        background: transparent !important;
        border: none !important;
        color: #4A3B32 !important;
    }
    
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #8C7B6E !important;
    }
    
    /* All buttons inside chat input */
    div[data-testid="stChatInput"] button {
        color: #6B5F52 !important;
    }
    
    div[data-testid="stChatInput"] button:hover {
        color: #4A3B32 !important;
        background: rgba(74, 59, 50, 0.08) !important;
    }

    /* ===== HERO CONTAINER ===== */
    .hero-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0 1rem;
        padding-top: 10vh;
        margin-bottom: 2rem;
    }
    
    .hero-greeting {
        font-size: 2rem;
        font-weight: 500;
        color: #4A3B32;
        margin: 0;
        text-align: center;
        letter-spacing: -0.5px;
    }
    
    .hero-username {
        font-family: serif;
        font-weight: 600;
        color: #A8C5B5; /* Sage accent */
    }
    
    .hero-subtitle {
        font-size: 1rem;
        color: #8DA399;
        margin-top: 0.25rem;
        text-align: center;
        font-weight: 400;
    }

    /* ===== SUGGESTION BUTTONS (NATIVE) ===== */
    
    .suggestion-grid-container button {
        background-color: #FFFFFF !important;
        border: 1px solid #E0DED9 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        height: auto !important;
        min-height: 72px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: flex-start !important;
        justify-content: flex-start !important;
        gap: 12px !important;
        text-align: left !important;
    }
    
    .suggestion-grid-container button:hover {
        border-color: #A8C5B5 !important;
        box-shadow: 0 4px 12px rgba(168, 197, 181, 0.15) !important;
        transform: translateY(-2px) !important;
        background-color: #FDFBF7 !important;
    }
    
    /* Suggestion Icon Box Styling */
    .suggestion-grid-container button span[data-testid="stIconMaterial"] {
        font-size: 24px !important;
        color: #4A3B32 !important;
        background-color: rgba(168, 197, 181, 0.2) !important;
        padding: 8px !important;
        border-radius: 8px !important;
        margin-right: 4px !important;
        width: 40px !important;
        height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Suggestion Text Styling */
    .suggestion-grid-container button p {
        color: #4A3B32 !important;
        line-height: 1.3 !important;
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        margin: 0 !important;
        white-space: pre-wrap !important;
    }
    
    .suggestion-grid-container button p strong {
        display: block !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        margin-bottom: 2px !important;
        color: #262730 !important;
    }
    
    /* ===== HEADER ACTION BUTTONS ===== */
    
    button[key="export_chat"], button[key="share_chat"],
    div[data-testid="stHorizontalBlock"]:has(.chat-title) button {
        background-color: transparent !important;
        border: 1px solid #D0C5BA !important;
        color: #4A3B32 !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        box-shadow: none !important;
        transition: all 0.2s ease !important;
        height: auto !important;
    }
    
    button[key="export_chat"]:hover, button[key="share_chat"]:hover,
    div[data-testid="stHorizontalBlock"]:has(.chat-title) button:hover {
        background-color: #FDFBF7 !important;
        border-color: #4A3B32 !important;
        color: #262730 !important;
        transform: translateY(-1px) !important;
    }
    
    button[key="export_chat"] span[data-testid="stIconMaterial"], 
    button[key="share_chat"] span[data-testid="stIconMaterial"] {
        color: #4A3B32 !important;
    }

    /* ===== UTILITY ===== */
    .chat-divider {
        border: none;
        border-top: 2px solid #F9F8F6;
        margin: 0.75rem 0;
    }
    
    .chat-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #4A3B32;
        margin: 0;
        line-height: 1.2;
    }
    
    /* Reason Expander */
    div[data-testid="stExpander"] .reasoning-content {
        background: #FDFBF7; /* Cream */
        border-left: 3px solid #4A3B32; /* Brown */
        padding: 1rem;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
        color: #6B5F52;
    }
    
    .suggestion-grid-container [data-testid="stVerticalBlock"] > div {
        align-items: stretch !important;
    }
    
    /* Chat charts styling */
    .chat-chart-container {
        background: #FDFBF7;
        border-radius: 8px;
        padding: 0.5rem;
        margin-top: 0.5rem;
    }
    
    /* ===== NEWS PANEL (rendered via components.html iframe) ===== */
</style>
"""

def get_help_css():
    """Returns CSS styling for the Help page"""
    return """
    <style>
        /* Help Page Styles */
        section[data-testid="stMain"] h1 {
            color: #4A3B32 !important;
            font-weight: 700 !important;
        }
        
        section[data-testid="stMain"] .stCaptionContainer {
            color: #8C7B6E !important;
        }
        
        section[data-testid="stMain"] h2,
        section[data-testid="stMain"] h3 {
            color: #4A3B32 !important;
            font-weight: 600 !important;
        }
        
        section[data-testid="stMain"] h4 {
            color: #6B5F52 !important;
            font-weight: 600 !important;
        }
        
        /* FAQ Expanders */
        section[data-testid="stMain"] .streamlit-expanderHeader {
            background-color: #F9F8F6 !important;
            color: #4A3B32 !important;
            font-weight: 500 !important;
            border-radius: 8px !important;
            padding: 0.75rem 1rem !important;
        }
        
        section[data-testid="stMain"] .streamlit-expanderHeader:hover {
            background-color: #F0EDE8 !important;
        }
        
        section[data-testid="stMain"] .streamlit-expanderContent {
            background-color: #FDFBF7 !important;
            border-left: 3px solid #4A3B32 !important;
            padding: 1rem !important;
            color: #6B5F52 !important;
        }
        
        /* Contact Form Inputs */
        section[data-testid="stMain"] .stSelectbox > label,
        section[data-testid="stMain"] .stTextInput > label,
        section[data-testid="stMain"] .stTextArea > label {
            color: #4A3B32 !important;
            font-weight: 500 !important;
        }
        
        section[data-testid="stMain"] .stSelectbox input,
        section[data-testid="stMain"] .stSelectbox > div > div,
        section[data-testid="stMain"] .stTextInput input,
        section[data-testid="stMain"] .stTextArea textarea {
            background-color: white !important;
            border-color: #E8E5E0 !important;
        }
        
        section[data-testid="stMain"] .stSelectbox input:focus,
        section[data-testid="stMain"] .stSelectbox > div > div:focus,
        section[data-testid="stMain"] .stTextInput input:focus,
        section[data-testid="stMain"] .stTextArea textarea:focus {
            background-color: white !important;
            border-color: #4A3B32 !important;
        }
        
        /* Ensure all input elements stay white on focus */
        section[data-testid="stMain"] [data-baseweb="input"]:focus-within,
        section[data-testid="stMain"] [data-baseweb="select"]:focus-within,
        section[data-testid="stMain"] input:focus,
        section[data-testid="stMain"] textarea:focus {
            background-color: white !important;
        }
        
        /* Submit Button */
        section[data-testid="stMain"] button[kind="primary"] {
            background-color: #4A3B32 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
        }
        
        section[data-testid="stMain"] button[kind="primary"]:hover {
            background-color: #3A2D24 !important;
        }
        
        /* Dividers */
        section[data-testid="stMain"] hr {
            border-color: #F0EDE8 !important;
            margin: 1.5rem 0 !important;
        }
        
        /* Code blocks */
        section[data-testid="stMain"] .stCodeBlock,
        section[data-testid="stMain"] code {
            background-color: #F9F8F6 !important;
            color: #4A3B32 !important;
            border: 1px solid #E8E5E0 !important;
        }
    </style>
    """

def get_profile_css():
    """Returns CSS styling for the Profile page"""
    return """
    <style>
        /* Profile Page Styles */
        section[data-testid="stMain"] h1 {
            color: #4A3B32 !important;
            font-weight: 700 !important;
        }
        
        section[data-testid="stMain"] .stCaptionContainer {
            color: #8C7B6E !important;
        }
        
        section[data-testid="stMain"] h2,
        section[data-testid="stMain"] h3 {
            color: #4A3B32 !important;
            font-weight: 600 !important;
        }
        
        /* Profile Card */
        section[data-testid="stMain"] [data-testid="stVerticalBlock"] {
            background-color: #FDFBF7 !important;
            border-radius: 12px !important;
        }
        
        /* Input Fields */
        section[data-testid="stMain"] .stTextInput > label,
        section[data-testid="stMain"] .stSelectbox > label {
            color: #4A3B32 !important;
            font-weight: 500 !important;
        }
        
        section[data-testid="stMain"] .stTextInput input,
        section[data-testid="stMain"] .stSelectbox > div > div {
            border-color: #E8E5E0 !important;
            background-color: white !important;
        }
        
        section[data-testid="stMain"] .stTextInput input:focus,
        section[data-testid="stMain"] .stSelectbox > div > div:focus {
            border-color: #4A3B32 !important;
            box-shadow: 0 0 0 1px #4A3B32 !important;
            background-color: white !important;
        }
        
        /* Ensure all input elements stay white on focus */
        section[data-testid="stMain"] [data-baseweb="input"]:focus-within,
        section[data-testid="stMain"] [data-baseweb="select"]:focus-within,
        section[data-testid="stMain"] input:focus,
        section[data-testid="stMain"] textarea:focus {
            background-color: white !important;
        }
        
        /* Buttons */
        section[data-testid="stMain"] button[kind="primary"] {
            background-color: #4A3B32 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
        }
        
        section[data-testid="stMain"] button[kind="primary"]:hover {
            background-color: #3A2D24 !important;
        }
        
        section[data-testid="stMain"] button[kind="secondary"] {
            background-color: #F9F8F6 !important;
            color: #4A3B32 !important;
            border: 1px solid #E8E5E0 !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
        }
        
        section[data-testid="stMain"] button[kind="secondary"]:hover {
            background-color: #F0EDE8 !important;
            border-color: #4A3B32 !important;
        }
        
        /* Dividers */
        section[data-testid="stMain"] hr {
            border-color: #F0EDE8 !important;
            margin: 1.5rem 0 !important;
        }
        
        /* File Uploader */
        section[data-testid="stMain"] [data-testid="stFileUploader"] {
            border: 2px dashed #E8E5E0 !important;
            background-color: #F9F8F6 !important;
            border-radius: 8px !important;
        }
        
        section[data-testid="stMain"] [data-testid="stFileUploader"]:hover {
            border-color: #4A3B32 !important;
        }
    </style>
    """

def get_settings_css():
    """Returns CSS styling for the Settings page"""
    return """
    <style>
        /* Settings Page Styles */
        section[data-testid="stMain"] .stTextInput input,
        section[data-testid="stMain"] .stSelectbox > div > div {
            border-color: #E8E5E0 !important;
            background-color: white !important;
        }
        
        /* Ensure all input elements stay white on focus */
        section[data-testid="stMain"] [data-baseweb="input"]:focus-within,
        section[data-testid="stMain"] [data-baseweb="select"]:focus-within,
        section[data-testid="stMain"] input:focus,
        section[data-testid="stMain"] textarea:focus {
            background-color: white !important;
        }
        
        /* Buttons */
        section[data-testid="stMain"] button[kind="primary"] {
            background-color: #4A3B32 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
        }
        
        section[data-testid="stMain"] button[kind="primary"]:hover {
            background-color: #3A2D24 !important;
        }
        
        /* Dividers */
        section[data-testid="stMain"] hr {
            border-color: #F0EDE8 !important;
            margin: 1.5rem 0 !important;
        }
    </style>
    """

# ── st.page_link active / hover styles ──
NAV_STYLES = """
<style>
    /* === Manual page links in sidebar (st.page_link) === */

    /* Compact page-link containers */
    [data-testid="stSidebar"] .stPageLink {
        margin-top: 0px !important;
        margin-bottom: 0px !important;
    }

    /* All page link items — dark text */
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
        border-radius: 8px !important;
        padding: 0.2rem 0.75rem !important;
        min-height: 0px !important;
        margin-bottom: 2px !important;
        transition: background-color 0.15s ease, color 0.15s ease !important;
        color: #3B2F28 !important;
    }
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] span,
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {
        color: #3B2F28 !important;
        font-weight: 500 !important;
    }
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {
        color: #3B2F28 !important;
    }

    /* Hover state — transparent dark brown */
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
        background-color: rgba(70, 56, 48, 0.15) !important;
    }

    /* Active / selected page — solid dark brown with white text */
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
        background-color: #463830 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] span,
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] p {
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }
    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] [data-testid="stIconMaterial"] {
        color: #FFFFFF !important;
    }
</style>
"""

def apply_custom_styles():
    """Apply all custom CSS styles to the app"""
    st.markdown(MAIN_STYLES, unsafe_allow_html=True)
    st.markdown(NAV_STYLES, unsafe_allow_html=True)


def apply_sidebar_styles():
    """Apply sidebar-specific styles"""
    st.markdown(SIDEBAR_STYLES, unsafe_allow_html=True)


def apply_sidebar_hover_styles():
    """Apply sidebar hover effects for chat rows"""
    st.markdown(SIDEBAR_HOVER_STYLES, unsafe_allow_html=True)


def apply_chat_styles():
    """Apply chat-specific styles"""
    st.markdown(CHAT_STYLES, unsafe_allow_html=True)