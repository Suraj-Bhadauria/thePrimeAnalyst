# --- START OF FILE src/components/help.py ---
import streamlit as st
from components.styles import get_help_css


def render_help():
    """Renders the Help page with documentation, FAQs, and support."""
    
    # Apply help page styles
    st.markdown(get_help_css(), unsafe_allow_html=True)
    
    st.title("Help Center")
    st.caption("Find answers and get support")
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.divider()
    
    # FAQ Section
    st.subheader("Frequently Asked Questions")
    
    with st.expander("How do I connect my payment provider?"):
        st.markdown("""
        To connect your payment provider:
        1. Navigate to **Settings** → **API & Integrations**
        2. Click **Connect** next to your provider
        3. Follow the authorization flow
        4. Your data will sync automatically
        
        Supported providers: Stripe, PayPal, Square, QuickBooks
        """)
    
    with st.expander("How can I export my data?"):
        st.markdown("""
        You can export data in multiple ways:
        - **Reports Page**: Generate custom reports in PDF, Excel, or CSV format
        - **Settings**: Export all your account data under **Data & Privacy**
        - **API**: Use our REST API for programmatic access
        """)
    
    with st.expander("What metrics are available in Analytics?"):
        st.markdown("""
        Available metrics include:
        - Revenue (total, average, trends)
        - Transaction volume and success rates
        - User activity and engagement
        - Geographic distribution
        - Segment breakdowns
        - Custom calculated fields
        """)
    
    with st.expander("How do I create a custom query?"):
        st.markdown("""
        To create custom queries:
        1. Go to the **New Chat** page
        2. Type your question in natural language
        3. Our AI will analyze your data and provide insights
        4. You can refine with follow-up questions
        
        Example: "Show me all transactions over $1000 in the last 30 days"
        """)
    
    with st.expander("Is my data secure?"):
        st.markdown("""
        Yes! We take security seriously:
        - End-to-end encryption for all data
        - SOC 2 Type II certified
        - GDPR and PCI-DSS compliant
        - Regular security audits
        - Two-factor authentication available
        
        See our [Security Policy](#) for more details.
        """)
    
    with st.expander("How do I manage my subscription?"):
        st.markdown("""
        Manage your subscription via:
        1. Navigate to **Settings** → **Billing** (coming soon)
        2. View current plan and usage
        3. Upgrade, downgrade, or cancel as needed
        
        For billing questions, contact: billing@primeanalyst.ai
        """)
    
    st.divider()
    
    # Contact Support
    st.subheader("Contact Support")
    st.markdown("#### Submit a Ticket")
    
    support_category = st.selectbox(
        "Category",
        options=["Technical Issue", "Billing", "Feature Request", "Other"]
    )
    
    support_subject = st.text_input("Subject")
    support_message = st.text_area("Describe your issue", height=150)
    
    if st.button("Submit Ticket", type="primary", use_container_width=True):
        st.success("Support ticket submitted! We'll respond within 24 hours.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()
    
    # System Information
    with st.expander("System Information"):
        st.code("""
App Version: 1.0.0
Last Updated: March 15, 2024
Environment: Production
API Status: Operational
Database: Connected
Cache: Enabled
        """)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
