# --- START OF FILE src/components/styles.py ---

"""
Custom CSS styles for PayInsight AI
"""
import streamlit as st


# Main application styles
MAIN_STYLES = """
<style>
    /* ===== REDUCE MAIN CONTAINER PADDING ===== */
    .stMainBlockContainer,
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }
    
    /* ===== FIX MAIN CONTENT ADJUSTMENT ON SIDEBAR COLLAPSE ===== */
    /* When sidebar is open, main content should have margin */
    section.main {
        transition: margin-left 0.3s ease !important;
    }
    
    /* Ensure main content expands when sidebar is collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] ~ * section.main,
    body:has([data-testid="stSidebar"][aria-expanded="false"]) section.main {
        margin-left: 0 !important;
    }
    
    /* Ensure main content has proper width */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
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
    /* Fixed sidebar width when open - no resize */
    [data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 350px !important;
        max-width: 350px !important;
        width: 350px !important;
    }
    
    /* When sidebar is collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] {
        min-width: 0px !important;
        max-width: 0px !important;
        width: 0px !important;
    }
    
    /* Hide the resize handle/drag bar */
    [data-testid="stSidebarResizeHandle"] {
        display: none !important;
        pointer-events: none !important;
        width: 0 !important;
    }
    
    /* Main content should transition smoothly */
    .stMainBlockContainer {
        transition: margin-left 0.3s ease;
    }
    
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
    Returns earthy professional sidebar CSS targeting PayInsight AI design specs.
    
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
        width: 280px !important;
        min-width: 280px !important;
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
        align-items: left !important;
        display: flex !important;
        padding: 0.5rem 0.5rem !important; /* Minimal padding */
        transition: all 0.2s ease !important;
        margin: 0 !important;
        font-weight: 400 !important;
        min-height: 0px !important;
        height: auto !important;
        line-height: 1.2 !important;
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
        align-items: left;
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
    */
    
    /* The Active Row Container */
    div.activity-row.active {
        background-color: #463830 !important; /* Theme Dark Brown */
        border-radius: 6px !important;
    }

    /* The Text/Button inside active row */
    div.activity-row.active button p,
    div.activity-row.active button span,
    div.activity-row.active button {
        color: #FFFFFF !important; /* White Text */
        background-color: transparent !important;
    }
    
    /* Remove hover effect on active button so it stays solid */
    div.activity-row.active button:hover {
        background-color: transparent !important;
        color: #FFFFFF !important;
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
        text-align: center !important;
        justify-content: center !important;
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
# --- START OF FILE src/components/styles.py ---
# --- START OF FILE src/components/styles.py ---

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

def get_analysis_css():
    """Returns CSS for the analytics page"""
    return """
<style>
    /* Global */
    .stApp {
        background: #F2F1EF !important;
    }
    
    /* Filter Bar */
    .filter-bar {
        display: flex;
        align-items: flex-end;
        gap: 12px;
        padding: 12px 0;
        border-bottom: 1px solid #E8E6E1;
        margin-bottom: 20px;
    }
    
    .filter-label {
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        color: #6B6560;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    
    /* Platform Buttons */
    .platform-btn {
        border: 1px solid #E8E6E1 !important;
        background: white !important;
        border-radius: 6px !important;
        padding: 6px 14px !important;
        cursor: pointer !important;
        font-size: 13px !important;
        color: #6B6560 !important;
        transition: all 0.2s ease !important;
    }
    
    .platform-active {
        background: #1A1614 !important;
        color: white !important;
        border-color: #1A1614 !important;
    }
    
    /* Dashboard Cards */
    .dash-card {
        background: #FFFFFF;
        border: 1px solid #E8E6E1;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    
    .dash-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    
    .dash-card-title {
        font-size: 15px;
        font-weight: 600;
        color: #1A1614;
        margin: 0;
    }
    
    .dash-card-subtitle {
        font-size: 11px;
        color: #6B6560;
        margin: 4px 0 0 0;
    }
    
     .chart-type-toggle {
        display: flex;
        gap: 8px;
    }
    
    .chart-type-btn {
        background: transparent;
        border: none;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        transition: background 0.2s;
    }
    
    .chart-type-btn:hover {
        background: #F2F1EF;
    }
    
    .chart-type-btn.active {
        background: #1A1614;
    }
    
    .chart-type-btn.active svg {
        stroke: white !important;
    }
    
    .ai-confidence-badge {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
        color: white;
        font-size: 10px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 12px;
        letter-spacing: 0.5px;
        display: inline-block;
        margin-bottom: 12px;
    }
    
    /* AI Panel */
    .ai-panel {
        background: #FAFAF9;
        border-left: 1px solid #E8E6E1;
        padding: 16px;
        border-radius: 0 12px 12px 0;
        height: 100%;
    }
    
    .ai-panel-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
    }
    
    .ai-panel-title {
        font-size: 16px;
        font-weight: 700;
        color: #1A1614;
        margin: 0;
    }
    
    .ai-panel-subtitle {
        font-size: 11px;
        color: #6B6560;
        margin: 0 0 20px 0;
    }
    
    /* Metric Tiles */
    .metric-tile {
        border: 1px solid #E8E6E1;
        border-radius: 8px;
        padding: 12px 14px;
        text-align: center;
        background: white;
        margin-bottom: 12px;
    }
    
    .metric-tile-label {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #6B6560;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    
    .metric-tile-value {
        font-size: 22px;
        font-weight: 700;
        color: #1A1614;
        margin: 4px 0;
    }
    
    .delta-up {
        color: #EF4444;
        font-size: 11px;
        font-weight: 600;
    }
    
    .delta-down {
        color: #10B981;
        font-size: 11px;
        font-weight: 600;
    }
    
    /* Insight Cards */
    .insight-card {
        border: 1px solid #E8E6E1;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        background: white;
        position: relative;
    }
    
    .insight-card.alert {
        border-left: 3px solid #EF4444;
    }
    
    .insight-card.warning {
        border-left: 3px solid #F59E0B;
    }
    
    .insight-card.opportunity {
        border-left: 3px solid #10B981;
    }
    
    .insight-icon-circle {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 10px;
    }
    
    .insight-title {
        font-size: 13px;
        font-weight: 600;
        color: #1A1614;
        margin: 0 0 6px 0;
    }
    
    .insight-description {
        font-size: 12px;
        color: #6B6560;
        line-height: 1.5;
        margin: 0 0 12px 0;
    }
    
    .insight-actions {
        display: flex;
        gap: 8px;
        align-items: center;
    }
    
    .insight-cta {
        background: #1A1614;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        flex: 1;
    }
    
    .insight-cta:hover {
        background: #2d241e;
        transform: translateY(-1px);
    }
    
    .insight-flag {
        background: transparent;
        border: 1px solid #E8E6E1;
        border-radius: 6px;
        padding: 6px 8px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .insight-flag:hover {
        background: #F2F1EF;
    }
    
    /* Generate Report Button */
    .generate-report-btn {
        border: 2px dashed #C8C4BE !important;
        border-radius: 8px !important;
        background: transparent !important;
        width: 100% !important;
        padding: 12px !important;
        color: #6B6560 !important;
        cursor: pointer !important;
        text-align: center !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    
    .generate-report-btn:hover {
        background: #F2F1EF !important;
        border-color: #1A1614 !important;
        color: #1A1614 !important;
    }
    
    /* Cohort Table */
    .cohort-table {
        margin-top: 16px;
    }
    
    .cohort-header {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #6B6560;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    
    /* Hide Streamlit button styling */
    .dash-card button[kind="primary"],
    .dash-card button[kind="secondary"],
    .ai-panel button[kind="primary"],
    .ai-panel button[kind="secondary"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        color: inherit !important;
    }
    
    div[data-testid="stHorizontalBlock"] > div:has(> button[kind]) {
        width: min-content !important;
    }
    
    /* Selectbox styling */
    div[data-testid="stSelectbox"] > div > div {
        background: white !important;
        border: 1px solid #E8E6E1 !important;
        border-radius: 6px !important;
    }
    
    /* Dynamic heading styles */
    .chart-main-title {
        font-size: 15px;
        font-weight: 650;
        color: #1A1614;
        margin-bottom: 2px;
    }
    
    .chart-main-subtitle {
        font-size: 11px;
        color: #6B6560;
        margin-bottom: 12px;
        letter-spacing: 0.3px;
    }
    
    .page-subtitle-bar {
        font-size: 12px;
        color: #6B6560;
        padding: 6px 0 14px;
        border-bottom: 1px solid #E8E6E1;
        margin-bottom: 16px;
    }
    
    .filter-active-summary {
        display: inline-flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    
    .filter-tag {
        background: #EEF2FF;
        color: #3730A3;
        font-size: 10px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 10px;
        letter-spacing: 0.3px;
    }
    
    /* Chart type toggle */
    .chart-toggle {
        display: inline-block;
    }
    
    .chart-toggle button {
        background: transparent !important;
        border: 1px solid #E8E6E1 !important;
        color: #6B6560 !important;
        font-size: 11px !important;
        padding: 4px 10px !important;
        border-radius: 5px !important;
        min-height: 28px !important;
        height: 28px !important;
    }
    
    .chart-toggle-active button {
        background: #1A1614 !important;
        border: 1px solid #1A1614 !important;
        color: white !important;
        font-size: 11px !important;
        padding: 4px 10px !important;
        border-radius: 5px !important;
        min-height: 28px !important;
        height: 28px !important;
    }
    
    /* Detailed metrics section */
    .section-divider {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #6B6560;
        padding: 24px 0 12px;
        border-bottom: 1px solid #E8E6E1;
        margin-bottom: 16px;
    }
    
    /* KPI card styles for metric widgets */
    .kpi-card {
        background: #F9F8F6;
        border: 1px solid #E8E6E1;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    
    .kpi-label {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #6B6560;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #1A1614;
        margin: 8px 0;
    }
    
    .kpi-delta {
        font-size: 12px;
        font-weight: 600;
    }
    
    .kpi-delta.positive {
        color: #10B981;
    }
    
    .kpi-delta.negative {
        color: #EF4444;
    }
    
    /* Platform toggle active state */
    [data-testid="stSidebar"] ~ * .platform-active > button,
    .platform-active > button {
        background: #1A1614 !important;
        color: white !important;
        border-color: #1A1614 !important;
    }
</style>
"""

def get_report_css():
    """Complete CSS for the redesigned report page"""
    
    COLORS = {
        "bg_page":        "#F2F1EF",
        "bg_card":        "#FFFFFF",
        "bg_panel":       "#FAFAF9",
        "border":         "#E8E6E1",
        "border_light":   "#F0EEE9",
        "text_primary":   "#1A1614",
        "text_secondary": "#6B6560",
        "text_muted":     "#9CA3AF",
        "accent_blue":    "#2563EB",
        "accent_blue_bg": "#EEF2FF",
        "accent_blue_text":"#3730A3",
        "green":          "#10B981",
        "green_bg":       "#D1FAE5",
        "orange":         "#F59E0B",
        "red":            "#EF4444",
        "red_bg":         "#FEE2E2",
        "btn_dark":       "#1A1614",
        "btn_dark_text":  "#FFFFFF",
    }
    
    return f"""
    <style>
    /* Page background */
    .stApp, .main .block-container {{
        background-color: {COLORS["bg_page"]} !important;
    }}
    
    /* Config panel card */
    .report-config-card {{
        background: {COLORS["bg_card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 14px;
        padding: 20px 18px;
        height: 100%;
    }}
    
    /* Preview panel card */
    .report-preview-card {{
        background: {COLORS["bg_card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 14px;
        padding: 24px 22px;
        min-height: 600px;
        /* Dot grid background */
        background-image: radial-gradient(circle, #D1CDC7 1px, transparent 1px);
        background-size: 20px 20px;
        background-color: {COLORS["bg_card"]};
    }}
    
    /* Panel section label (same as analysis filter-label) */
    .report-section-label {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: {COLORS["text_secondary"]};
        margin: 16px 0 8px;
        display: block;
    }}
    
    /* Segmented control wrapper */
    .segment-control {{
        display: flex;
        gap: 4px;
        background: {COLORS["bg_page"]};
        border-radius: 8px;
        padding: 3px;
        margin-bottom: 4px;
    }}
    
    /* Metric count badge on expander */
    .metric-count-badge {{
        background: {COLORS["accent_blue_bg"]};
        color: {COLORS["accent_blue_text"]};
        font-size: 10px;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 8px;
        float: right;
    }}
    
    /* Preview header */
    .preview-report-title {{
        font-size: 20px;
        font-weight: 650;
        color: {COLORS["text_primary"]};
        margin: 0 0 2px;
    }}
    .preview-report-dates {{
        font-size: 12px;
        color: {COLORS["text_secondary"]};
        margin: 0;
    }}
    
    /* Live badge with pulse */
    .live-badge {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: {COLORS["green_bg"]};
        color: #065F46;
        font-size: 10px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        letter-spacing: 0.5px;
    }}
    .live-dot {{
        width: 6px;
        height: 6px;
        background: {COLORS["green"]};
        border-radius: 50%;
        animation: pulse-dot 2s infinite;
    }}
    @keyframes pulse-dot {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.4; transform: scale(0.7); }}
    }}
    
    /* Section divider in preview */
    .preview-section-header {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: {COLORS["text_secondary"]};
        padding: 16px 0 8px;
        border-bottom: 1px solid {COLORS["border"]};
        margin-bottom: 12px;
    }}
    
    /* Export bar */
    .export-action-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 0 0;
        border-top: 1px solid {COLORS["border"]};
        margin-top: 20px;
    }}
    .export-bar-info {{
        font-size: 12px;
        color: {COLORS["text_secondary"]};
    }}
    
    /* KPI card (same as analysis page) */
    .kpi-card {{
        background: {COLORS["bg_card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }}
    .kpi-label {{
        font-size: 11px;
        color: {COLORS["text_secondary"]};
        margin-bottom: 4px;
        font-weight: 500;
    }}
    .kpi-value {{
        font-size: 26px;
        font-weight: 700;
        color: {COLORS["text_primary"]};
        line-height: 1.1;
    }}
    .kpi-delta {{
        display: inline-block;
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        margin-top: 4px;
    }}
    .kpi-delta.positive {{ background: {COLORS["green_bg"]}; color: #065F46; }}
    .kpi-delta.negative {{ background: {COLORS["red_bg"]}; color: #991B1B; }}
    
    /* Empty state */
    .preview-empty-state {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 80px 20px;
        color: {COLORS["text_muted"]};
        text-align: center;
    }}
    .preview-empty-icon {{
        font-size: 40px;
        margin-bottom: 12px;
        opacity: 0.4;
    }}
    .preview-empty-text {{
        font-size: 13px;
        max-width: 220px;
        line-height: 1.6;
    }}
    
    /* Clear all button */
    .report-clear-btn > div > button {{
        background: transparent !important;
        border: 1px solid {COLORS["border"]} !important;
        color: {COLORS["text_secondary"]} !important;
        border-radius: 8px !important;
        font-size: 12px !important;
        width: 100% !important;
        margin-top: 12px !important;
    }}
    .report-clear-btn > div > button:hover {{
        border-color: {COLORS["red"]} !important;
        color: {COLORS["red"]} !important;
    }}
    
    /* Dark export button */
    .export-btn-dark > div > button {{
        background: {COLORS["btn_dark"]} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
    }}
    .export-btn-dark > div > button:hover {{
        background: #2D2420 !important;
    }}
    
    /* Outlined export button */
    .export-btn-outline > div > button {{
        background: transparent !important;
        color: {COLORS["text_primary"]} !important;
        border: 1px solid {COLORS["border"]} !important;
        border-radius: 8px !important;
        font-size: 12px !important;
    }}
    
    /* Remove default Streamlit metric styling */
    [data-testid="stMetric"] {{
        background: {COLORS["bg_card"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 10px;
        padding: 10px 14px;
        text-align: center;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 9px !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
        color: {COLORS["text_secondary"]} !important;
        font-weight: 700 !important;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 28px !important;
        font-weight: 700 !important;
        color: {COLORS["accent_blue"]} !important;
    }}
    
    /* Segmented radio override */
    div[data-testid="stRadio"] > div {{
        display: flex !important;
        flex-direction: row !important;
        gap: 4px !important;
        background: {COLORS["bg_page"]} !important;
        border-radius: 8px !important;
        padding: 3px !important;
    }}
    div[data-testid="stRadio"] > div > label {{
        flex: 1 !important;
        text-align: center !important;
        padding: 6px 8px !important;
        border-radius: 6px !important;
        font-size: 12px !important;
        cursor: pointer !important;
        background: transparent !important;
        color: {COLORS["text_secondary"]} !important;
        border: none !important;
        font-weight: 500 !important;
        transition: all 0.15s !important;
    }}
    div[data-testid="stRadio"] > div > label[data-checked="true"],
    div[data-testid="stRadio"] > div > label:has(input:checked) {{
        background: {COLORS["btn_dark"]} !important;
        color: white !important;
        font-weight: 600 !important;
    }}
    div[data-testid="stRadio"] > div > label > div:first-child {{
        display: none !important;
    }}
    </style>
    """

# --- START OF FILE src/components/styles.py ---

# ... (Previous standard styles remain) ...

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
        padding-bottom: 0rem !important;
        max-width: 900px !important;
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
    
    /* ===== CHAT INPUT FIELD ===== */
    
    /* The main container at the bottom */
    div[data-testid="stChatInput"] {
        background-color: transparent !important;
        padding-bottom: 2rem !important;
    }
    
    /* The Input Box itself */
    div[data-testid="stChatInput"] textarea,
    div[data-testid="stChatInput"] input {
        background-color: #FDFBF7 !important; /* Cream Input */
        color: #4A3B32 !important; /* Brown Text */
        border: 2px solid rgba(74, 59, 50, 0.2) !important; /* Subtle Brown Border */
        border-radius: 16px !important;
        padding: 12px 16px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    }
    
    /* Focus State */
    div[data-testid="stChatInput"] textarea:focus,
    div[data-testid="stChatInput"] input:focus {
        border-color: #4A3B32 !important;
        box-shadow: 0 4px 16px rgba(74, 59, 50, 0.1) !important;
    }
    
    /* The Send Button inside input */
    div[data-testid="stChatInput"] button {
        color: #4A3B32 !important;
    }
    div[data-testid="stChatInput"] button:hover {
        background-color: rgba(74, 59, 50, 0.1) !important;
        color: #4A3B32 !important;
    }

    /* ===== HERO CONTAINER ===== */
    .hero-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0 1rem;
        margin-top: 1vh;
        margin-bottom: 1.5rem;
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
    
    /* Thought Process Styles */
    div[data-testid="stExpander"] .reasoning-content {
        background: #FDFBF7;
        border-left: 3px solid #4A3B32;
        padding: 1rem;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
        color: #6B5F52;
    }

    /* ===== THOUGHT PROCESS COMPONENT ===== */
    .thought-process {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 0.85rem;
        color: #4A3B32;
    }

    .tp-step {
        position: relative;
        padding: 0.6rem 0 0.6rem 1.5rem;
        border-left: 2px solid #E8E0D8;
        margin-left: 0.5rem;
    }

    .tp-step:last-child {
        border-left: 2px solid transparent;
    }

    .tp-step::before {
        content: '';
        position: absolute;
        left: -5px;
        top: 0.85rem;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #D4C5B5;
        border: 2px solid #FDFBF7;
    }

    .tp-step-active::before {
        background: #D4A03C;
        box-shadow: 0 0 0 3px rgba(212, 160, 60, 0.2);
        animation: tp-pulse 1.5s ease-in-out infinite;
    }

    .tp-step-done::before {
        background: #5A9E6F;
    }

    .tp-step-error::before {
        background: #C0504D;
    }

    @keyframes tp-pulse {
        0%, 100% { box-shadow: 0 0 0 2px rgba(212, 160, 60, 0.15); }
        50% { box-shadow: 0 0 0 6px rgba(212, 160, 60, 0.08); }
    }

    .tp-step-header {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-weight: 600;
        margin-bottom: 0.25rem;
    }

    .tp-icon {
        font-size: 0.95rem;
    }

    .tp-title {
        color: #4A3B32;
    }

    .tp-status {
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.1rem 0.45rem;
        border-radius: 9999px;
        margin-left: auto;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .tp-running {
        background: #FEF3C7;
        color: #92400E;
    }

    .tp-done {
        background: #D1FAE5;
        color: #065F46;
    }

    .tp-error {
        background: #FEE2E2;
        color: #991B1B;
    }

    .tp-details {
        padding-left: 1.35rem;
    }

    .tp-detail-line {
        color: #6B5F52;
        font-size: 0.8rem;
        line-height: 1.5;
        padding: 0.1rem 0;
    }

    .tp-detail-line strong {
        color: #4A3B32;
    }

    .tp-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.3rem 0.75rem;
        margin-top: 0.3rem;
        padding: 0.4rem 0.6rem;
        background: rgba(74, 59, 50, 0.04);
        border-radius: 6px;
        font-size: 0.75rem;
    }

    .tp-meta-item {
        color: #6B5F52;
    }

    .tp-meta-key {
        font-weight: 600;
        color: #4A3B32;
    }
    
    .suggestion-grid-container [data-testid="stVerticalBlock"] > div {
        align-items: stretch !important;
    }
</style>
"""

def apply_custom_styles():
    """Apply all custom CSS styles to the app"""
    st.markdown(MAIN_STYLES, unsafe_allow_html=True)


def apply_sidebar_styles():
    """Apply sidebar-specific styles"""
    st.markdown(SIDEBAR_STYLES, unsafe_allow_html=True)


def apply_sidebar_hover_styles():
    """Apply sidebar hover effects for chat rows"""
    st.markdown(SIDEBAR_HOVER_STYLES, unsafe_allow_html=True)


def apply_chat_styles():
    """Apply chat-specific styles"""
    st.markdown(CHAT_STYLES, unsafe_allow_html=True)