"""
UI Configuration for PayInsight AI
Contains all UI-related settings, labels, and content
"""

# ==========================================
# USER PROFILE CONFIGURATION
# ==========================================
USER_PROFILE = {
    "name": "Alex Johnson",
    "role": "Financial Analyst",
    "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=Alex"
}

# ==========================================
# HOME PAGE CONFIGURATION
# ==========================================
HOME_DATA = {
    "badge_text": "INTELLIGENT ANALYTICS",
    "title": "PayInsight AI",
    "subtitle": "Your autonomous partner in transaction data analysis.",
    "feature_cards": [
        {
            "title": "Multi-Agent AI System",
            "description": "Powered by specialized AI agents working together to deliver comprehensive insights"
        },
        {
            "title": "Real-Time Analytics",
            "description": "Analyze 250K+ transactions with instant query processing and visualization"
        },
        {
            "title": "Natural Language Queries",
            "description": "Ask questions in plain English and get detailed analytical responses"
        },
        {
            "title": "Advanced Visualizations",
            "description": "Interactive charts, trends, and dashboards for deep data exploration"
        }
    ]
}

# ==========================================
# CHAT SUGGESTIONS
# ==========================================
CHAT_SUGGESTIONS = [
    {
        "title": "Transaction Analysis",
        "subtitle": "Show me failed transactions this month"
    },
    {
        "title": "Revenue Trends",
        "subtitle": "What's the revenue trend by merchant category?"
    },
    {
        "title": "Fraud Detection",
        "subtitle": "Analyze fraud patterns across states"
    },
    {
        "title": "Performance Metrics",
        "subtitle": "Compare transaction success rates by bank"
    },
    {
        "title": "Time Analysis",
        "subtitle": "Show peak transaction hours and patterns"
    },
    {
        "title": "Geographic Insights",
        "subtitle": "Which states have the highest transaction volume?"
    }
]

# ==========================================
# SIDEBAR MENU CONFIGURATION
# ==========================================
MAIN_MENU = [
    {"id": "home", "label": "Home", "icon": ":material/home:"},
    {"id": "chat", "label": "Chat", "icon": ":material/chat:"},
    {"id": "dashboard", "label": "Dashboard", "icon": ":material/dashboard:"},
    {"id": "analytics", "label": "Analytics", "icon": ":material/analytics:"},
    {"id": "report", "label": "Reports", "icon": ":material/description:"},
]

SETTINGS_MENU = [
    {"id": "settings", "label": "Settings", "icon": ":material/settings:"},
    {"id": "profile", "label": "Profile", "icon": ":material/person:"},
    {"id": "help", "label": "Help", "icon": ":material/help:"},
]

# ==========================================
# RECENT ACTIVITY (CHAT HISTORY)
# ==========================================
# This will be dynamically populated from session state
# Placeholder for initial state
RECENT_ACTIVITY_PLACEHOLDER = [
    {"id": "chat_1", "title": "Transaction Analysis", "timestamp": "2h ago", "is_active": False},
    {"id": "chat_2", "title": "Revenue Trends", "timestamp": "5h ago", "is_active": False},
]

# ==========================================
# DASHBOARD CONFIGURATION
# ==========================================
DASHBOARD_CONFIG = {
    "title": "Transaction Analytics Dashboard",
    "subtitle": "Real-time insights from your transaction data",
    "kpi_labels": {
        "total_transactions": "Total Transactions",
        "success_rate": "Success Rate",
        "total_revenue": "Total Revenue",
        "fraud_rate": "Fraud Rate",
        "avg_transaction": "Avg Transaction",
        "active_merchants": "Active Merchants"
    }
}

# ==========================================
# ANALYTICS CONFIGURATION
# ==========================================
ANALYTICS_CONFIG = {
    "title": "Advanced Analytics",
    "subtitle": "Deep dive into transaction patterns and insights",
    "sections": {
        "gateway_performance": "Payment Gateway Performance",
        "fraud_analysis": "Fraud Detection Analysis",
        "geographic": "Geographic Distribution",
        "time_analysis": "Time-based Patterns",
        "merchant_analysis": "Merchant Category Analytics"
    }
}

# ==========================================
# CHART COLORS (Earthy Professional Theme)
# ==========================================
COLORS = {
    "primary": "#4A3B32",      # Dark Brown
    "secondary": "#6B5F52",    # Medium Brown
    "sage": "#A8C5B5",         # Sage Green
    "sage_light": "rgba(168, 197, 181, 0.2)",
    "blue": "#8DA399",         # Muted Blue
    "grey": "#E0DED9",         # Warm Grey
    "accent": "#D4A574",       # Warm Accent
    "red": "#C62828",          # Alert Red
    "cream": "#FDFBF7",        # Background
    "white": "#FFFFFF",
    "success": "#10B981",      # Green
    "warning": "#F59E0B",      # Amber
    "danger": "#EF4444"        # Red
}

COLOR_SEQUENCE = [
    COLORS["primary"], 
    COLORS["sage"], 
    COLORS["blue"], 
    COLORS["grey"], 
    COLORS["accent"]
]

# ==========================================
# SVG ICONS (Optional Custom Icons)
# ==========================================
SVG_ICONS = {
    # Add custom SVG icons here if needed
}

# ==========================================
# SETTINGS DEFAULTS
# ==========================================
DEFAULT_SETTINGS = {
    "theme": "earthy_professional",
    "temperature": 0.7,
    "max_tokens": 4096,
    "cache_enabled": True,
    "show_reasoning": True,
    "auto_export": False
}
