# --- START OF FILE components/analytics.py ---
"""
Analysis Component for PayInsight AI
Core + Advanced Analytics using Real Transaction Data

Features:
- Real Transaction Data Analysis
- India-Specific Metrics (UPI, Payment Methods, States)
- Advanced Visualizations
- Fraud Detection Analytics
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from components.styles import get_analysis_css
from components.ui_config import COLORS, ANALYTICS_CONFIG
from src.utils.data_loader import data_loader

# ==========================================
# DATA LOADING FROM REAL TRANSACTION DATA
# ==========================================

def load_analytics_data():
    """
    Loads and processes data for analytics from real transaction CSV.
    Returns aggregated analytics data.
    """
    try:
        # Load real transaction data
        df = data_loader.load_data()
        
        # Calculate gateway/bank performance
        bank_stats = df.groupby('sender_bank').agg({
            'transaction_id': 'count',
            'transaction_status': lambda x: (x == 'SUCCESS').sum() / len(x) * 100
        }).reset_index()
        bank_stats.columns = ['bank', 'volume', 'success_rate']
        bank_stats = bank_stats.sort_values('volume', ascending=False).head(10)
        
        # Fraud analysis
        fraud_by_category = df.groupby('merchant_category')['fraud_flag'].agg(['sum', 'count']).reset_index()
        fraud_by_category['fraud_rate'] = (fraud_by_category['sum'] / fraud_by_category['count'] * 100)
        fraud_by_category = fraud_by_category.sort_values('fraud_rate', ascending=False).head(10)
        
        # Geographic distribution
        state_stats = df.groupby('sender_state').agg({
            'transaction_id': 'count',
            'amount_inr': 'sum'
        }).reset_index()
        state_stats.columns = ['state', 'txn_count', 'revenue']
        state_stats = state_stats.sort_values('txn_count', ascending=False).head(10)
        
        # Time-based patterns
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        hourly_stats = df.groupby('hour').agg({
            'transaction_id': 'count',
            'transaction_status': lambda x: (x == 'SUCCESS').sum() / len(x) * 100
        }).reset_index()
        hourly_stats.columns = ['hour', 'volume', 'success_rate']
        
        # Device/Network analysis
        device_stats = df.groupby('device_type')['transaction_id'].count().to_dict()
        network_stats = df.groupby('network_type')['transaction_id'].count().to_dict() if 'network_type' in df.columns else {}
        
        # Merchant category analysis
        category_stats = df.groupby('merchant_category').agg({
            'transaction_id': 'count',
            'amount_inr': 'sum'
        }).reset_index()
        category_stats.columns = ['category', 'txn_count', 'revenue']
        category_stats = category_stats.sort_values('revenue', ascending=False)
        
        return {
            "gateways": bank_stats['bank'].tolist(),
            "success_rates": bank_stats['success_rate'].tolist(),
            "volumes": bank_stats['volume'].tolist(),
            "fraud_categories": fraud_by_category['merchant_category'].tolist(),
            "fraud_rates": fraud_by_category['fraud_rate'].tolist(),
            "states": state_stats['state'].tolist(),
            "state_txn_counts": state_stats['txn_count'].tolist(),
            "state_revenues": state_stats['revenue'].tolist(),
            "hourly_volume": hourly_stats['volume'].tolist(),
            "hourly_hours": hourly_stats['hour'].tolist(),
            "device_stats": device_stats,
            "network_stats": network_stats,
            "category_names": category_stats['category'].tolist(),
            "category_revenues": category_stats['revenue'].tolist(),
            "category_counts": category_stats['txn_count'].tolist()
        }
        
    except Exception as e:
        st.error(f"Error loading analytics data: {str(e)}")
        return {}

# ==========================================
# CHART BUILDERS
# ==========================================

def render_gateway_perf(data):
    """
    Combined Chart: Success Rate (Bar) & Volume (Line)
    Context: Indian Gateways (Razorpay, PayU, etc.)
    """
    fig = go.Figure()
    
    # Success Rate Bars
    fig.add_trace(go.Bar(
        x=data["gateways"],
        y=data["success_rates"],
        name="Success Rate (%)",
        marker_color=COLORS["primary"],
        text=[f"{v:.1f}%" for v in data["success_rates"]],
        textposition="auto",
        yaxis="y1"
    ))
    
    # Volume Line
    fig.add_trace(go.Scatter(
        x=data["gateways"],
        y=data["volumes"],
        name="Volume (Txns)",
        mode="lines+markers",
        line=dict(color=COLORS["accent"], width=3),
        yaxis="y2"
    ))

    fig.update_layout(
        title="Gateway Performance (SR% vs Volume)",
        yaxis=dict(title="Success Rate (%)", range=[80, 100], gridcolor='#E5E1DB'),
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.2),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_latency_box(data):
    """
    Box Plot: Real-Time Payment Latency (UPI vs IMPS vs Cards)
    """
    fig = go.Figure()
    
    for i, network in enumerate(data["networks"]):
        color = COLORS["upi"] if "UPI" in network else (COLORS["accent"] if "Card" in network else COLORS["secondary"])
        
        fig.add_trace(go.Box(
            y=data["y_values"][i],
            name=network,
            boxpoints='outliers', 
            marker_color=color,
            line_width=1.5
        ))

    fig.update_layout(
        title="Network Latency Distribution (ms)",
        yaxis=dict(title="Milliseconds", gridcolor='#E5E1DB'),
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    return fig

def render_india_geo_heatmap(data):
    """
    Heatmap: State-wise Transaction Volume
    (Replaces Choropleth for reliability without external GeoJSON)
    """
    # Sort for visual hierarchy
    df = pd.DataFrame(data).sort_values("values", ascending=True)
    
    fig = go.Figure(go.Bar(
        x=df["values"],
        y=df["locations"],
        orientation='h',
        marker=dict(color=df["values"], colorscale="Blues"),
        text=[f"SR: {sr}%" for sr in df["success_rate"]],
        textposition="auto"
    ))
    
    fig.update_layout(
        title="Top Indian States by Volume (₹ Cr)",
        xaxis=dict(showgrid=True, gridcolor='#E5E1DB'),
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_sankey_flow(data):
    """
    Sankey: Cross-Device / Payment Journey
    """
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15, thickness=20,
            line=dict(color="black", width=0.5),
            label=data["node_labels"],
            color=COLORS["primary"]
        ),
        link=dict(
            source=data["source"],
            target=data["target"],
            value=data["values"],
            color=data["colors"]
        )
    )])
    fig.update_layout(
        title="Cross-Device Payment Journey",
        font=dict(size=10, color=COLORS["primary"]),
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_kyc_funnel(data):
    """
    Funnel: User Onboarding (Aadhaar/PAN context)
    """
    fig = go.Figure(go.Funnel(
        y=data["stages"],
        x=data["values"] if "values" in data else data["users"], # Handle key variation
        textinfo="value+percent previous",
        marker={"color": [COLORS["secondary"], COLORS["primary"], COLORS["accent"], COLORS["success"], COLORS["success"]]}
    ))
    fig.update_layout(
        title="Onboarding & KYC Funnel",
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_leakage_waterfall(data):
    """
    Waterfall: Revenue Leakage & MDR Analysis
    """
    fig = go.Figure(go.Waterfall(
        measure=data["measure"],
        x=data["x"],
        textposition="outside",
        text=data["text"],
        y=data["y"],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": COLORS["danger"]}},
        increasing={"marker": {"color": COLORS["success"]}},
        totals={"marker": {"color": COLORS["primary"]}}
    ))
    fig.update_layout(
        title="Net Revenue Analysis (MDR Impact)",
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(title="Financial Impact")
    )
    return fig

def render_fraud_velocity(data):
    """
    Line: Fraud Attempts per Hour
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["hours"], y=data["attempts"],
        mode='lines+markers', name='Attempts',
        line=dict(color=COLORS["danger"], width=2)
    ))
    fig.add_trace(go.Scatter(
        x=data["hours"], y=data["threshold"],
        mode='lines', name='Threshold',
        line=dict(color=COLORS["secondary"], dash='dash')
    ))
    fig.update_layout(
        title="Fraud Velocity (Hits/Hour)",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(title="Attempts"),
        legend=dict(orientation="h", y=-0.2)
    )
    return fig

def render_dispute_win_rates(data):
    """
    Combined Bar/Line: Dispute Reasons & Win Rates
    """
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=data["reasons"],
        y=data["win_rate"],
        name="Win Rate (%)",
        marker_color=COLORS["success"],
        text=[f"{v}%" for v in data["win_rate"]],
        textposition="auto"
    ))
    
    fig.add_trace(go.Scatter(
        x=data["reasons"],
        y=data["volume"],
        name="Volume",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=COLORS["primary"])
    ))
    
    fig.update_layout(
        title="Dispute Resolution by Reason",
        yaxis=dict(title="Win Rate %", range=[0, 100]),
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.2),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_token_heatmap(data):
    """
    Heatmap: Tokenization Success (RBI Compliance)
    """
    # Defensive check for structure variations
    z_vals = data["values"]
    x_vals = data["devices"]
    y_vals = data["providers"]
    
    fig = go.Figure(data=go.Heatmap(
        z=z_vals, x=x_vals, y=y_vals,
        colorscale="Greens",
        text=[[f"{val}%" for val in row] for row in z_vals],
        texttemplate="%{text}",
        showscale=False
    ))
    fig.update_layout(
        title="Tokenization Success (RBI CoF)",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS["primary"])
    )
    return fig

# ==========================================
# UI COMPONENTS
# ==========================================

def render_ai_query_bar():
    """Natural Language Query Interface"""
    with st.container():
        st.markdown("### 🤖 Ask PayInsight")
        c1, c2 = st.columns([5, 1])
        with c1:
            query = st.text_input(
                "AI Query", 
                placeholder="e.g., 'Analyze UPI declines for HDFC Bank in Mumbai' or 'Project revenue if MDR drops by 0.2%'",
                label_visibility="collapsed"
            )
        with c2:
            ask_btn = st.button("Analyze", type="primary", use_container_width=True)
        
        if ask_btn and query:
            st.success(f"Analysis generated for: **'{query}'**")
            with st.expander("✨ AI Insight", expanded=True):
                st.markdown("**Observation:** High failure rate (12%) detected for **UPI Intent** transactions on **iOS** devices during peak hours (6-9 PM).")
                st.markdown("**Root Cause:** Timeout responses from Partner Bank A's switch.")
                st.caption("Recommendation: Enable dynamic routing to Bank B for iOS traffic.")

def render_filter_bar():
    """India-Specific Global Filters"""
    with st.expander("🛠️ Filters (India Region)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.selectbox("Payment Mode", ["All", "UPI (Collect)", "UPI (Intent)", "RuPay Credit", "Netbanking"])
        with c2:
            st.selectbox("State/Region", ["All India", "Maharashtra", "Karnataka", "NCR", "Tamil Nadu"])
        with c3:
            st.selectbox("Bank/Issuer", ["All Banks", "HDFC", "SBI", "ICICI", "Axis"])
        with c4:
            st.selectbox("Timeframe", ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "YTD"])

def render_what_if_simulator():
    """Predictive Modeling Tool"""
    st.markdown("### 🔮 What-If Simulator")
    st.caption("Predict revenue impact based on fee changes and downtime.")
    
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.slider("Increase MDR (%)", 0.0, 2.0, 0.0, 0.1, help="Merchant Discount Rate Impact")
    with sc2:
        st.slider("UPI Downtime (Min/Day)", 0, 60, 0, 5, help="Bank Switch Downtime")
    with sc3:
        # Mock calculation
        st.metric("Projected Revenue Impact", "₹-12.5K", "-0.8%")

# ==========================================
# MAIN RENDER FUNCTION
# ==========================================

def render_analytics():
    """Main Entry Point"""
    st.markdown(get_analysis_css(), unsafe_allow_html=True)
    
    # 1. Load Real Data
    data = load_analytics_data()
    if not data:
        st.warning("No analytics data available. Please check your data source.")
        return

    # 2. Header
    st.title(ANALYTICS_CONFIG['title'])
    st.markdown(ANALYTICS_CONFIG['subtitle'])
    
    # 3. Analytics Tabs
    tab_perf, tab_fraud, tab_geo, tab_time = st.tabs([
        "⚡ Performance", 
        "🛡️ Fraud Analysis", 
        "🌍 Geographic", 
        "⏰ Time Patterns"
    ])

    # --- TAB 1: PERFORMANCE ---
    with tab_perf:
        st.subheader("Payment Gateway/Bank Performance")
        if data.get("gateways"):
            st.plotly_chart(render_gateway_perf(data), use_container_width=True)
        else:
            st.info("No gateway performance data available")
            
        # Device & Network Distribution
        st.subheader("Device & Network Distribution")
        col1, col2 = st.columns(2)
        with col1:
            if data.get("device_stats"):
                fig_device = px.pie(
                    names=list(data["device_stats"].keys()),
                    values=list(data["device_stats"].values()),
                    title="Device Distribution",
                    color_discrete_sequence=[COLORS["primary"], COLORS["sage"], COLORS["blue"]]
                )
                st.plotly_chart(fig_device, use_container_width=True)
        with col2:
            if data.get("network_stats"):
                fig_network = px.pie(
                    names=list(data["network_stats"].keys()),
                    values=list(data["network_stats"].values()),
                    title="Network Distribution",
                    color_discrete_sequence=[COLORS["accent"], COLORS["grey"], COLORS["primary"]]
                )
                st.plotly_chart(fig_network, use_container_width=True)
    
    # --- TAB 2: FRAUD ANALYSIS ---
    with tab_fraud:
        st.subheader("Fraud Detection by Merchant Category")
        if data.get("fraud_categories"):
            fig_fraud = go.Figure(go.Bar(
                x=data["fraud_categories"],
                y=data["fraud_rates"],
                marker_color=COLORS["red"],
                text=[f"{v:.2f}%" for v in data["fraud_rates"]],
                textposition="auto"
            ))
            fig_fraud.update_layout(
                title="Fraud Rate by Merchant Category",
                xaxis_title="Category",
                yaxis_title="Fraud Rate (%)",
                height=400
            )
            st.plotly_chart(fig_fraud, use_container_width=True)
        else:
            st.info("No fraud data available")
    
    # --- TAB 3: GEOGRAPHIC ANALYSIS ---
    with tab_geo:
        st.subheader("State-wise Transaction Analysis")
        if data.get("states"):
            col1, col2 = st.columns(2)
            with col1:
                fig_states = go.Figure(go.Bar(
                    x=data["state_txn_counts"],
                    y=data["states"],
                    orientation='h',
                    marker_color=COLORS["sage"],
                    text=[f"{v:,}" for v in data["state_txn_counts"]],
                    textposition="auto"
                ))
                fig_states.update_layout(
                    title="Top States by Transaction Volume",
                    xaxis_title="Transaction Count",
                    height=400
                )
                st.plotly_chart(fig_states, use_container_width=True)
            
            with col2:
                fig_revenue = go.Figure(go.Bar(
                    x=data["state_revenues"],
                    y=data["states"],
                    orientation='h',
                    marker_color=COLORS["accent"],
                    text=[f"₹{v/1e6:.1f}M" for v in data["state_revenues"]],
                    textposition="auto"
                ))
                fig_revenue.update_layout(
                    title="Top States by Revenue",
                    xaxis_title="Revenue (₹)",
                    height=400
                )
                st.plotly_chart(fig_revenue, use_container_width=True)
        else:
            st.info("No geographic data available")
    
    # --- TAB 4: TIME PATTERNS ---
    with tab_time:
        st.subheader("Hourly Transaction Patterns")
        if data.get("hourly_hours"):
            fig_time = go.Figure()
            fig_time.add_trace(go.Scatter(
                x=data["hourly_hours"],
                y=data["hourly_volume"],
                mode='lines+markers',
                line=dict(color=COLORS["primary"], width=3),
                fill='tozeroy',
                fillcolor=COLORS["sage_light"],
                name="Volume"
            ))
            fig_time.update_layout(
                title="Transaction Volume by Hour of Day",
                xaxis_title="Hour of Day",
                yaxis_title="Transaction Count",
                height=400
            )
            st.plotly_chart(fig_time, use_container_width=True)
            
            # Merchant Category Revenue
            st.subheader("Merchant Category Analysis")
            if data.get("category_names"):
                fig_category = go.Figure(go.Bar(
                    x=data["category_revenues"],
                    y=data["category_names"],
                    orientation='h',
                    marker_color=COLORS["blue"],
                    text=[f"₹{v/1e6:.1f}M" for v in data["category_revenues"]],
                    textposition="auto"
                ))
                fig_category.update_layout(
                    title="Revenue by Merchant Category",
                    xaxis_title="Revenue (₹)",
                    height=400
                )
                st.plotly_chart(fig_category, use_container_width=True)
        else:
            st.info("No time pattern data available")

    # Footer Actions
    st.markdown("---")
    col_x, col_y = st.columns([6, 1])
    with col_y:
        if st.button("Export Full Report", type="primary", use_container_width=True):
            st.toast("Exporting PDF Report...", icon="📥")

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    render_analytics()