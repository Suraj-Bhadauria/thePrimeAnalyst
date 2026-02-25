# --- START OF FILE components/analytics.py ---
"""
components/analytics.py
Refactored to use latest Streamlit APIs:
  - st.columns(gap, vertical_alignment, border)
  - st.container(horizontal, horizontal_alignment, key)
  - st.form(border, width)
  - st.dataframe(key)
  - st.plotly_chart(key)
"""
import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Chart color constants for Plotly (Python-side; must stay as hex values).
# primary, secondary, bg, and card mirror the values set in .streamlit/config.toml.
COLORS = {
    "primary":   "#4A3B32",  # = theme.primaryColor / theme.textColor
    "secondary": "#6B5F52",
    "accent":    "#2563EB",
    "success":   "#4A7C59",
    "warning":   "#C17F24",
    "danger":    "#B44C3A",
    "upi":       "#C2673A",
    "rupay":     "#5C7A3E",
    "bg":        "#F2F1EF",  # = theme.secondaryBackgroundColor
    "card":      "#F9F8F6",  # = theme.sidebar.backgroundColor
}

CHART_COLORS_BROWN = [
    "#4A3B32", "#6B5F52", "#8C7B6E", "#A89890",
    "#B5A99F", "#C9BFB8", "#D9D0CA", "#F2F1EF",
]

FRAUD_HEATMAP_SCALE = [
    [0.0, "#F2F1EF"], [0.3, "#D4B896"],
    [0.6, "#C2673A"], [0.8, "#B44C3A"], [1.0, "#4A3B32"],
]

DIVERGING_SCALE = [
    [0.0,  "rgba(180, 76, 58, 1)"],
    [0.25, "rgba(180, 76, 58, 0.4)"],
    [0.5,  "rgba(242, 241, 239, 1)"],
    [0.75, "rgba(74, 124, 89, 0.4)"],
    [1.0,  "rgba(74, 124, 89, 1)"],
]

# ==========================================
# 1. INTEGRATION LAYER
# ==========================================

class _NullAnalyticsService:
    """Returns empty data structures so the UI renders without a backend."""
    _EMPTY = {"status": "success", "data": {}}

    def _empty(self, *a, **kw):
        return self._EMPTY

    get_kpi_summary = get_transaction_overview = get_comparison_data = _empty
    get_temporal_analysis = get_state_distribution = get_failure_analysis = _empty
    get_statistical_tests = get_rankings = get_bank_performance = _empty
    get_fraud_analysis = get_filtered_transactions = get_network_graph_data = _empty
    get_trend_analysis = get_correlation_analysis = _empty

try:
    from backend.analytics_service import AnalyticsService
    data_service = AnalyticsService()
except ImportError:
    try:
        from test_ui import MockAnalyticsService
        data_service = MockAnalyticsService()
    except ImportError:
        data_service = _NullAnalyticsService()

from components.styles import get_analytics_css

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def _format_currency(value):
    if value >= 10000000: return f"₹{value / 10000000:.2f} Cr"
    elif value >= 100000: return f"₹{value / 100000:.2f} L"
    elif value >= 1000:   return f"₹{value / 1000:.1f} k"
    else:                 return f"₹{value:.0f}"

def _format_number(value):
    if value >= 1000000: return f"{value / 1000000:.1f}M"
    elif value >= 1000:  return f"{value / 1000:.1f}k"
    return str(value)

def _map_to_scale(values, scale):
    """Maps a list of values to colors in a scale proportionally."""
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        return [scale[0]] * len(values)
    return [
        scale[int((v - min_v) / (max_v - min_v) * (len(scale) - 1))]
        for v in values
    ]

def _render_kpi_card(title, value, trend, change_pct, icon=None):
    """
    Renders a KPI card using a keyed st.container.
    key → .st-key-kpi_{slug} for CSS targeting.
    """
    trend_color = COLORS["success"] if trend == "up" else COLORS["danger"]
    trend_icon  = "↑" if trend == "up" else "↓"
    if trend == "neutral":
        trend_color = "#9CA3AF"
        trend_icon  = "→"

    card_key = f"kpi_{title.lower().replace(' ', '_')}"
    with st.container(border=True, key=card_key):
        st.markdown(
            f"<p style='color:#6B7280; font-size:0.8rem; font-weight:600; margin:0; "
            f"text-transform:uppercase; letter-spacing:0.04em;'>"
            f"{icon + ' ' if icon else ''}{title}</p>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<p style='color:#111827; font-size:1.8rem; font-weight:700; "
            f"margin:0.25rem 0 0 0; line-height:1.2;'>{value}</p>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<p style='color:{trend_color}; font-size:0.82rem; font-weight:600; "
            f"margin:0.25rem 0 0 0;'>"
            f"{trend_icon} {abs(change_pct)}% "
            f"<span style='color:#9CA3AF; font-weight:400;'>vs last period</span></p>",
            unsafe_allow_html=True
        )

# ==========================================
# 3. FILTER COMPONENT
# ==========================================

def render_filters():
    """
    Renders filter panel in the right column.
    Uses st.container(key=) for CSS scoping and
    st.form(border=False, width="stretch") per docs.
    """
    with st.container(border=True, key="analytics_filter_panel"):
        st.markdown("### Filters")

        if 'analytics_filters' not in st.session_state:
            st.session_state.analytics_filters = {
                "date_range": (datetime.now() - timedelta(days=30), datetime.now()),
                "transaction_type": [], "transaction_status": [], "device_type": [],
                "network_type": [], "sender_state": [], "sender_bank": [], "sender_age_group": []
            }

        # border=False — outer container already provides the card border
        # width="stretch" — correct API for filling parent column width
        with st.form("analytics_filter_form", border=False, width="stretch"):
            st.markdown("**Time Period**")
            date_range = st.date_input(
                "Range",
                value=st.session_state.analytics_filters["date_range"],
                key="filter_date",
                label_visibility="collapsed"
            )
            st.markdown("**Transaction Type**")
            txn_types = st.multiselect(
                "Type",
                options=["P2P", "P2M", "Bill Payment", "Recharge"],
                default=st.session_state.analytics_filters["transaction_type"],
                label_visibility="collapsed"
            )
            st.markdown("**Status**")
            statuses = st.multiselect(
                "Status",
                options=["SUCCESS", "FAILED", "PENDING"],
                default=st.session_state.analytics_filters["transaction_status"],
                label_visibility="collapsed"
            )
            st.markdown("**Device Type**")
            devices = st.multiselect(
                "Device",
                options=["Android", "iOS", "Web"],
                default=st.session_state.analytics_filters["device_type"],
                label_visibility="collapsed"
            )
            st.markdown("**Network Type**")
            networks = st.multiselect(
                "Network",
                options=["4G", "5G", "WiFi"],
                default=st.session_state.analytics_filters["network_type"],
                label_visibility="collapsed"
            )
            st.markdown("**Sender Bank**")
            banks = st.multiselect(
                "Bank",
                options=["SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "BOB", "Yes Bank"],
                default=st.session_state.analytics_filters["sender_bank"],
                label_visibility="collapsed"
            )
            st.markdown("**Age Group**")
            age_groups = st.multiselect(
                "Age Group",
                options=["18-25", "26-35", "36-45", "46-55", "56+"],
                default=st.session_state.analytics_filters["sender_age_group"],
                label_visibility="collapsed"
            )
            st.markdown("**Sender State**")
            states = st.multiselect(
                "State",
                options=["Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Gujarat",
                         "Uttar Pradesh", "West Bengal", "Rajasthan", "Telangana", "Kerala"],
                default=st.session_state.analytics_filters["sender_state"],
                label_visibility="collapsed"
            )
            submitted = st.form_submit_button(
                "Apply Filters",
                type="primary",
                use_container_width=True,
                icon=":material/filter_alt:"
            )
            if submitted:
                st.session_state.analytics_filters = {
                    "date_range": date_range,
                    "transaction_type": txn_types,
                    "transaction_status": statuses,
                    "device_type": devices,
                    "network_type": networks,
                    "sender_bank": banks,
                    "sender_age_group": age_groups,
                    "sender_state": states
                }
                st.rerun()

        # key= gives .st-key-filter_reset_btn for CSS scoping
        if st.button(
            "Reset Filters",
            type="tertiary",
            use_container_width=True,
            key="filter_reset_btn",
            icon=":material/restart_alt:"
        ):
            st.session_state.analytics_filters = {
                "date_range": (datetime.now() - timedelta(days=30), datetime.now()),
                "transaction_type": [], "transaction_status": [], "device_type": [],
                "network_type": [], "sender_state": [], "sender_bank": [], "sender_age_group": []
            }
            st.rerun()

    return st.session_state.analytics_filters

# ==========================================
# 4. SUB-SECTION RENDERERS
# ==========================================

def render_kpi_section(kpi_data):
    """
    Renders 8 KPI cards in two rows of 4.
    gap="small" tightens spacing between cards.
    vertical_alignment="top" keeps card tops flush.
    """
    st.markdown("### Overview")

    # Row 1 — gap="small" is 1rem, matches container padding rhythm
    c1, c2, c3, c4 = st.columns(4, gap="small", vertical_alignment="top")
    with c1: _render_kpi_card("Total Volume",    _format_number(kpi_data["total_volume"]["value"]),     kpi_data["total_volume"]["trend"],    kpi_data["total_volume"]["change_pct"])
    with c2: _render_kpi_card("Total Value",     _format_currency(kpi_data["total_value"]["value"]),    kpi_data["total_value"]["trend"],     kpi_data["total_value"]["change_pct"])
    with c3: _render_kpi_card("Success Rate",    f"{kpi_data['success_rate']['value']}%",               kpi_data["success_rate"]["trend"],    kpi_data["success_rate"]["change_pct"])
    with c4: _render_kpi_card("Avg Transaction", _format_currency(kpi_data["avg_txn_amount"]["value"]), kpi_data["avg_txn_amount"]["trend"],  kpi_data["avg_txn_amount"]["change_pct"])

    # Row 2
    c5, c6, c7, c8 = st.columns(4, gap="small", vertical_alignment="top")
    with c5: _render_kpi_card("Fraud Flags",  _format_number(kpi_data["fraud_flags"]["value"]),  kpi_data["fraud_flags"]["trend"],  kpi_data["fraud_flags"]["change_pct"])
    with c6: _render_kpi_card("Active Users", _format_number(kpi_data["active_users"]["value"]), kpi_data["active_users"]["trend"], kpi_data["active_users"]["change_pct"])
    with c7:
        hour_val = kpi_data["peak_hour"]["value"]
        period = "AM" if hour_val < 12 else "PM"
        display_hour = hour_val if hour_val <= 12 else hour_val - 12
        display_hour = 12 if display_hour == 0 else display_hour
        _render_kpi_card("Peak Hour", f"{display_hour} {period}", "neutral", 0)
    with c8: _render_kpi_card("Failure Rate", f"{kpi_data['failure_rate']['value']}%", kpi_data["failure_rate"]["trend"], kpi_data["failure_rate"]["change_pct"])


def render_transaction_overview(data):
    """Renders Volume and Value metrics tabs."""
    st.divider()
    with st.container(border=True, key="section_txn_overview"):
        st.subheader("Transaction Analysis")

        tab_vol, tab_val = st.tabs(["Volume Metrics", "Value Metrics"])

        with tab_vol:
            # [1, 2] ratio — pie/status bar left, trend area right
            c1, c2 = st.columns([1, 2], gap="small", vertical_alignment="top")
            with c1:
                df_type = pd.DataFrame(data["volume_by_type"])
                fig_type = px.pie(df_type, names='type', values='count', hole=0.6,
                                  title="Transaction Type Distribution",
                                  color_discrete_sequence=CHART_COLORS_BROWN)
                fig_type.update_layout(showlegend=False, height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_type, use_container_width=True, key="chart_txn_type_dist")

                df_status = pd.DataFrame(data["volume_by_status"])
                fig_status = px.bar(df_status, x='status', y='count', color='status',
                                    title="Status Breakdown",
                                    color_discrete_map={
                                        "SUCCESS": COLORS["success"],
                                        "FAILED":  COLORS["danger"],
                                        "PENDING": COLORS["warning"]
                                    })
                fig_status.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_status, use_container_width=True, key="chart_txn_status")

            with c2:
                df_trend = pd.DataFrame(data["daily_trend"])
                fig_trend = px.area(df_trend, x='date', y='count',
                                    title="Daily Transaction Volume (Last 30 Days)",
                                    color_discrete_sequence=[COLORS["primary"]])
                fig_trend.update_xaxes(showgrid=False)
                fig_trend.update_yaxes(showgrid=True, gridcolor=COLORS["bg"])
                fig_trend.update_traces(fillcolor='rgba(74, 59, 50, 0.12)')
                fig_trend.update_layout(height=580, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_trend, use_container_width=True, key="chart_daily_trend")

        with tab_val:
            c1, c2 = st.columns(2, gap="small", vertical_alignment="top")
            with c1:
                df_dist = pd.DataFrame(data["amount_distribution"])
                fig_dist = px.bar(df_dist, x='range', y='count',
                                  title="Transaction Amount Distribution",
                                  labels={'range': 'Amount Range (₹)', 'count': 'Frequency'},
                                  color_discrete_sequence=[COLORS["primary"]])
                fig_dist.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_dist, use_container_width=True, key="chart_amount_dist")

            with c2:
                df_avg = pd.DataFrame(data["avg_amount_by_type"])
                fig_avg = px.bar(df_avg, x='avg_amount', y='type', orientation='h',
                                 title="Average Transaction Value by Type",
                                 color='avg_amount',
                                 color_continuous_scale=CHART_COLORS_BROWN)
                fig_avg.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_avg, use_container_width=True, key="chart_avg_amount")


def render_comparison_section(data):
    """Renders Device and Network comparisons."""
    with st.container(border=True, key="section_comparison"):
        st.subheader("Device & Network Performance")

        tab_dev, tab_net = st.tabs(["Device Comparison", "Network Comparison"])

        with tab_dev:
            c1, c2 = st.columns(2, gap="small", vertical_alignment="top")
            with c1:
                df_dev = pd.DataFrame(data["device_metrics"])
                df_dev_melt = df_dev.melt(
                    id_vars=['device_type'],
                    value_vars=['success_rate', 'failure_rate'],
                    var_name='metric', value_name='percentage'
                )
                fig_dev = px.bar(df_dev_melt, x='device_type', y='percentage',
                                 color='metric', barmode='group',
                                 title="Success vs Failure Rate by Device",
                                 color_discrete_map={
                                     "success_rate": COLORS["success"],
                                     "failure_rate": COLORS["danger"]
                                 })
                fig_dev.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_dev, use_container_width=True, key="chart_device_rates")

            with c2:
                fig_dev_vol = px.pie(df_dev, names='device_type', values='volume',
                                     title="Volume Share by Device",
                                     color_discrete_sequence=CHART_COLORS_BROWN)
                fig_dev_vol.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_dev_vol, use_container_width=True, key="chart_device_vol")

        with tab_net:
            c1, c2 = st.columns(2, gap="small", vertical_alignment="top")
            with c1:
                df_net = pd.DataFrame(data["network_metrics"])
                fig_net = px.bar(df_net, x='network_type', y='success_rate',
                                 color='success_rate',
                                 title="Success Rate by Network Type",
                                 range_y=[80, 100],
                                 color_continuous_scale=CHART_COLORS_BROWN[::-1])
                fig_net.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_net, use_container_width=True, key="chart_network_sr")
            with c2:
                fig_net_dist = px.pie(df_net, names='network_type', values='volume',
                                      title="Network Usage Distribution",
                                      color_discrete_sequence=CHART_COLORS_BROWN[::-1])
                fig_net_dist.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_net_dist, use_container_width=True, key="chart_network_dist")


def render_temporal_analysis(data):
    """Renders Hourly and Weekly patterns."""
    with st.container(border=True, key="section_temporal"):
        st.subheader("Temporal Patterns")

        # [2, 1] — hourly line chart wider, weekly bar chart narrower
        c1, c2 = st.columns([2, 1], gap="small", vertical_alignment="top")
        with c1:
            df_hour = pd.DataFrame(data["hourly_distribution"])
            fig_hour = px.line(df_hour, x='hour', y='count',
                               title="Hourly Transaction Traffic (24h)",
                               markers=True, line_shape='spline',
                               color_discrete_sequence=[COLORS["success"]])
            fig_hour.add_annotation(
                x=data["peak_hours"][0], y=max(df_hour['count']),
                text="Peak Hour", showarrow=True, arrowhead=1
            )
            fig_hour.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_hour, use_container_width=True, key="chart_hourly")

        with c2:
            df_week = pd.DataFrame(data["day_of_week"])
            fig_week = px.bar(df_week, x='day', y='count',
                              title="Weekly Volume Pattern",
                              color='count',
                              color_continuous_scale=CHART_COLORS_BROWN[::-1])
            fig_week.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_week, use_container_width=True, key="chart_weekly")


def render_geo_and_failure(geo_data, fail_data):
    """Renders State distribution and Failure Analysis side by side."""
    with st.container(border=True, key="section_geo_failure"):
        # vertical_alignment="top" keeps subheaders flush across columns
        c1, c2 = st.columns(2, gap="medium", vertical_alignment="top")

        with c1:
            st.subheader("Geographic Distribution")
            df_geo = pd.DataFrame(geo_data["top_states"])
            fig_geo = px.bar(df_geo, x='volume', y='state', orientation='h',
                             title="Top 10 States by Volume",
                             color='volume',
                             color_continuous_scale=CHART_COLORS_BROWN[::-1])
            fig_geo.update_layout(
                yaxis={'categoryorder': 'total ascending'},
                height=280, margin=dict(l=10, r=10, t=30, b=10)
            )
            st.plotly_chart(fig_geo, use_container_width=True, key="chart_geo")

        with c2:
            st.subheader("Failure Analysis")
            st.metric("Overall Failure Rate", f"{fail_data['overall_failure_rate']}%", "-0.5% vs avg")
            df_fail_trend = pd.DataFrame(fail_data["failure_trend"])
            fig_fail = px.line(df_fail_trend, x='date', y='rate',
                               title="Failure Rate Trend (Last 30 Days)",
                               color_discrete_sequence=[COLORS["danger"]])
            fig_fail.add_hline(y=5.0, line_dash="dot",
                               annotation_text="Threshold (5%)",
                               annotation_position="bottom right")
            fig_fail.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_fail, use_container_width=True, key="chart_failure_trend")


# ==========================================
# PHASE 2: ADVANCED RENDER FUNCTIONS
# ==========================================

def render_statistical_analysis(stats_data):
    """Phase 2A: Descriptive Stats and Confidence Intervals."""
    st.divider()
    with st.container(border=True, key="section_stats"):
        st.subheader("Statistical Deep Dive")

        tab_desc, tab_conf, tab_tests = st.tabs(
            ["Descriptive Stats", "Confidence Intervals", "Hypothesis Tests"]
        )

        with tab_desc:
            c1, c2 = st.columns([1, 2], gap="medium", vertical_alignment="top")
            with c1:
                ds = stats_data["descriptive_stats"]
                with st.container(border=True, key="stats_desc_card"):
                    st.markdown(f"**Mean:** {_format_currency(ds['mean'])}")
                    st.markdown(f"**Median:** {_format_currency(ds['median'])}")
                    st.markdown(f"**Std Dev:** {_format_currency(ds['std_dev'])}")
                    st.markdown(f"**Skewness:** {ds['skewness']}")
                    st.markdown(f"**Kurtosis:** {ds['kurtosis']}")

            with c2:
                fig_dist = px.bar(
                    x=stats_data["distribution"]["bins"],
                    y=stats_data["distribution"]["counts"],
                    title="Transaction Amount Distribution (with Normal Curve)",
                    labels={'x': 'Amount Bin', 'y': 'Frequency'},
                    color_discrete_sequence=[COLORS["primary"]]
                )
                fig_dist.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_dist, use_container_width=True, key="chart_stats_dist")

        with tab_conf:
            st.info("Wilson Score Interval (95% Confidence) for Success Rates")
            ci = stats_data["confidence_intervals"]
            fig_ci = go.Figure()
            fig_ci.add_trace(go.Scatter(
                x=["Success Rate"], y=[ci["mean"]],
                error_y=dict(
                    type='data',
                    array=[ci["upper"] - ci["mean"]],
                    arrayminus=[ci["mean"] - ci["lower"]]
                ),
                mode='markers',
                marker=dict(color=COLORS["success"], size=15),
                name="Mean"
            ))
            fig_ci.update_layout(
                title="Success Rate Variability Range",
                yaxis=dict(range=[90, 100]),
                height=280, margin=dict(l=10, r=10, t=30, b=10)
            )
            st.plotly_chart(fig_ci, use_container_width=True, key="chart_confidence")

        with tab_tests:
            st.dataframe(
                pd.DataFrame(stats_data["tests"]),
                use_container_width=True,
                key="df_hypothesis_tests"
            )


def render_rankings_section(rank_data):
    """Phase 2B: Rankings & Pareto Analysis."""
    with st.container(border=True, key="section_rankings"):
        st.subheader("Leaderboards & Rankings")

        c1, c2 = st.columns(2, gap="medium", vertical_alignment="top")
        with c1:
            st.markdown("**Top 5 States (Volume)**")
            df_top = pd.DataFrame(rank_data["top_performers"])
            st.dataframe(
                df_top,
                column_config={
                    "rank": "Rank",
                    "name": "State",
                    "value": st.column_config.ProgressColumn(
                        "Volume", format="%d",
                        min_value=0, max_value=max(df_top['value'])
                    ),
                    "success_rate": st.column_config.NumberColumn("Success %", format="%.1f%%")
                },
                hide_index=True,
                use_container_width=True,
                key="df_top_states"
            )

        with c2:
            st.markdown("**Pareto Analysis (80/20 Rule)**")
            pareto = rank_data["pareto_data"]
            colors = _map_to_scale(pareto["values"], CHART_COLORS_BROWN[::-1][:6])

            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(
                x=pareto["names"], y=pareto["values"],
                name='Volume', marker=dict(color=colors)
            ))
            fig_pareto.add_trace(go.Scatter(
                x=pareto["names"], y=pareto["cumulative_pct"],
                name='Cumulative %', yaxis='y2',
                mode='lines+markers',
                line=dict(color=COLORS["accent"], width=2),
                marker=dict(color=COLORS["accent"], size=6)
            ))
            fig_pareto.update_layout(
                yaxis=dict(title='Volume'),
                yaxis2=dict(title='Cumulative %', overlaying='y', side='right', range=[0, 110]),
                showlegend=False,
                height=280, margin=dict(l=10, r=10, t=30, b=10)
            )
            st.plotly_chart(fig_pareto, use_container_width=True, key="chart_pareto")
            st.caption(f"Insight: Top {pareto['cumulative_threshold']} states contribute to 80% of total volume.")


def render_bank_matrix(bank_data):
    """Phase 2D: Bank Performance Heatmap."""
    with st.container(border=True, key="section_bank_matrix"):
        st.subheader("Bank Interoperability Matrix")

        c1, c2 = st.columns([1, 2], gap="medium", vertical_alignment="top")
        with c1:
            st.markdown("**Top Sender Banks**")
            df_banks = pd.DataFrame(bank_data["sender_banks"])
            st.dataframe(
                df_banks[["bank", "success_rate", "fraud_rate"]],
                column_config={
                    "bank": "Bank",
                    "success_rate": st.column_config.NumberColumn("SR %", format="%.1f%%"),
                    "fraud_rate":   st.column_config.NumberColumn("Fraud %", format="%.2f%%")
                },
                hide_index=True,
                use_container_width=True,
                key="df_sender_banks"
            )

        with c2:
            matrix = bank_data["cross_bank_matrix"]
            fig_mx = px.density_heatmap(
                pd.DataFrame(matrix),
                x="receiver", y="sender", z="count",
                title="Sender vs Receiver Bank Volume",
                color_continuous_scale=CHART_COLORS_BROWN[::-1]
            )
            fig_mx.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_mx, use_container_width=True, key="chart_bank_matrix")


def render_fraud_deep_dive(fraud_data):
    """Phase 2E: Fraud Heatmap and Alert Table."""
    with st.container(border=True, key="section_fraud"):
        st.subheader("Fraud Deep Dive")

        c1, c2 = st.columns(2, gap="medium", vertical_alignment="top")
        with c1:
            st.markdown("**High-Risk Time Windows**")
            df_heat = pd.DataFrame(fraud_data["fraud_heatmap"])
            fig_heat = go.Figure(data=go.Heatmap(
                z=df_heat['fraud_count'],
                x=df_heat['hour'],
                y=df_heat['day'],
                colorscale=FRAUD_HEATMAP_SCALE
            ))
            fig_heat.update_layout(height=300, margin=dict(t=30, b=10, l=10, r=10))
            st.plotly_chart(fig_heat, use_container_width=True, key="chart_fraud_heatmap")

        with c2:
            st.markdown("**Recent High-Risk Alerts**")
            st.dataframe(
                pd.DataFrame(fraud_data["recent_fraud_transactions"]),
                column_config={
                    "transaction_id": "Txn ID",
                    "amount":     st.column_config.NumberColumn("Amount", format="₹%d"),
                    "risk_score": st.column_config.ProgressColumn("Risk Score", min_value=0, max_value=100),
                    "timestamp":  "Time"
                },
                hide_index=True,
                use_container_width=True,
                height=300,
                key="df_fraud_alerts"
            )


def render_transaction_table(txn_data):
    """Phase 2H: Detailed Drill-Down Table."""
    st.divider()
    with st.container(border=True, key="section_txn_table"):
        st.subheader("Transaction Drill-Down")

        df_txns = pd.DataFrame(txn_data["transactions"])

        # Horizontal container for search + export row
        # horizontal=True lays children side by side natively
        # vertical_alignment="bottom" keeps button flush with input baseline
        toolbar = st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="bottom",
            key="txn_toolbar"
        )
        with toolbar:
            search_query = st.text_input(
                "Search",
                placeholder="Transaction ID, status, amount…",
                label_visibility="collapsed",
                key="txn_search_input"
            )
            st.download_button(
                label="Export CSV",
                data=df_txns.to_csv(index=False).encode("utf-8"),
                file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="export_csv_btn",
                icon=":material/download:"
            )

        if search_query:
            df_txns = df_txns[
                df_txns.apply(
                    lambda row: row.astype(str).str.contains(search_query, case=False).any(),
                    axis=1
                )
            ]

        st.dataframe(
            df_txns,
            use_container_width=True,
            column_config={
                "amount":    st.column_config.NumberColumn("Amount", format="₹%d"),
                "status":    st.column_config.TextColumn("Status", help="Current state of txn"),
                "timestamp": st.column_config.DatetimeColumn("Timestamp", format="D MMM, HH:mm"),
            },
            height=400,
            key="df_transactions"
        )
        st.caption(f"Showing {len(df_txns)} of {txn_data['total_count']} records")


# ==========================================
# PHASE 3: ADVANCED INTELLIGENCE RENDERERS
# ==========================================

def render_network_analysis(net_data):
    """Phase 3A: P2P Network Graph."""
    st.divider()
    with st.container(border=True, key="section_network"):
        st.subheader("P2P Network Intelligence")

        # [3, 1] — graph wide, metrics panel narrow
        c1, c2 = st.columns([3, 1], gap="medium", vertical_alignment="top")
        with c1:
            edge_x, edge_y = [], []
            for edge in net_data["edges"]:
                src = next((n for n in net_data["nodes"] if n["id"] == edge["source"]), None)
                tgt = next((n for n in net_data["nodes"] if n["id"] == edge["target"]), None)
                if src and tgt:
                    edge_x.extend([src["x"], tgt["x"], None])
                    edge_y.extend([src["y"], tgt["y"], None])

            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#888'),
                hoverinfo='none', mode='lines'
            )
            node_x     = [n["x"] for n in net_data["nodes"]]
            node_y     = [n["y"] for n in net_data["nodes"]]
            node_text  = [
                f"ID: {n['id']}<br>Vol: {n['total_volume']}<br>Risk: {n['fraud_risk']}"
                for n in net_data["nodes"]
            ]
            node_color = [
                COLORS["danger"]  if n["fraud_risk"] == "high"
                else (COLORS["warning"] if n["fraud_risk"] == "medium" else COLORS["success"])
                for n in net_data["nodes"]
            ]
            node_size = [n["degree"] * 2 for n in net_data["nodes"]]

            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode='markers', hoverinfo='text', text=node_text,
                marker=dict(showscale=False, color=node_color, size=node_size, line_width=2)
            )

            fig_net = go.Figure(
                data=[edge_trace, node_trace],
                layout=go.Layout(
                    title=dict(text='Money Flow Graph (High Risk Clusters)', font=dict(size=16)),
                    showlegend=False, hovermode='closest',
                    margin=dict(b=10, l=10, r=10, t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=400,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
            )
            st.plotly_chart(fig_net, use_container_width=True, key="chart_network_graph")

        with c2:
            nm = net_data["metrics"]
            with st.container(border=True, key="network_metrics_card"):
                st.markdown(f"**Density:** {nm['density']}")
                st.markdown(f"**Avg Degree:** {nm['avg_degree']}")
                st.markdown(f"**Modularity:** {nm['modularity']}")
                st.divider()
                st.markdown(f":red[**Detected Cycles:** {len(net_data['cycles'])}]")
                st.markdown(f":orange[**Mule Hubs:** {len(net_data['hubs'])}]")

            st.markdown("##### Suspicious Cycles")
            for cycle in net_data["cycles"][:3]:
                st.error(f"{cycle['length']}-hop loop: ₹{_format_number(cycle['total_amount'])}")


def render_trend_forecast(trend_data):
    """Phase 3B: Time Series Forecasting."""
    with st.container(border=True, key="section_forecast"):
        st.subheader("Trend Forecasting (Prophet Model)")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data["historical"]["dates"],
            y=trend_data["historical"]["values"],
            name="Actual",
            line=dict(color=COLORS["primary"], width=2)
        ))
        fig.add_trace(go.Scatter(
            x=trend_data["forecast"]["dates"],
            y=trend_data["forecast"]["values"],
            name="Forecast",
            line=dict(color=COLORS["success"], width=2, dash='dash')
        ))
        fig.add_trace(go.Scatter(
            x=trend_data["forecast"]["dates"] + trend_data["forecast"]["dates"][::-1],
            y=trend_data["forecast"]["upper"] + trend_data["forecast"]["lower"][::-1],
            fill='toself',
            fillcolor='rgba(74, 124, 89, 0.12)',
            line=dict(color='rgba(74, 124, 89, 0)'),
            hoverinfo="skip", showlegend=False, name="95% Confidence"
        ))

        if trend_data.get("anomalies"):
            anom_dates = [a["date"] for a in trend_data["anomalies"]]
            anom_vals  = [a["value"] for a in trend_data["anomalies"]]
            fig.add_trace(go.Scatter(
                x=anom_dates, y=anom_vals,
                mode='markers', name="Anomaly",
                marker=dict(color=COLORS["danger"], size=10, symbol="x")
            ))

        fig.update_layout(
            title="Volume Forecast (Next 30 Days)",
            height=300, margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="h", y=-0.2),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_forecast")

        # Horizontal container for the 3 info/warning badges
        badges = st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            key="forecast_badges"
        )
        with badges:
            st.info(f"Peak Day: **{trend_data['seasonality']['peak_day']}**")
            st.info(f"Peak Hour: **{trend_data['seasonality']['peak_hour']}**")
            st.warning(f"Predicted Dip: **{trend_data['forecast']['min_date']}**")


def render_correlation_lab(corr_data):
    """Phase 3C: Correlation Matrix."""
    with st.container(border=True, key="section_correlation"):
        st.subheader("Correlation Lab")

        c1, c2 = st.columns(2, gap="medium", vertical_alignment="top")
        with c1:
            st.markdown("**Metric Relationships**")
            fig_corr = px.imshow(
                corr_data["matrix"],
                x=corr_data["labels"], y=corr_data["labels"],
                color_continuous_scale=DIVERGING_SCALE,
                zmin=-1, zmax=1, text_auto=".2f", aspect="auto"
            )
            fig_corr.update_layout(height=280, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig_corr, use_container_width=True, key="chart_correlation")

        with c2:
            st.markdown("**Multivariate Analysis**")
            fig_bub = px.scatter(
                corr_data["scatter_data"],
                x="avg_amount", y="success_rate",
                size="volume", color="fraud_rate",
                hover_name="entity",
                title="Entity Performance Cluster",
                labels={"avg_amount": "Avg Amount", "success_rate": "Success %"},
                color_continuous_scale=CHART_COLORS_BROWN[::-1]
            )
            fig_bub.update_layout(
                height=280, margin=dict(t=30, b=20, l=10, r=10),
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_bub, use_container_width=True, key="chart_bubble")


# ==========================================
# 5. MAIN RENDER FUNCTION
# ==========================================

def render_analytics():
    """Main entry point for the Analytics Page."""
    try:
        st.markdown(get_analytics_css(), unsafe_allow_html=True)
    except:
        pass

    if 'analytics_filters' not in st.session_state:
        st.session_state.analytics_filters = {
            "date_range": (datetime.now() - timedelta(days=30), datetime.now()),
            "transaction_type": [], "transaction_status": [], "device_type": [],
            "network_type": [], "sender_state": [], "sender_bank": [], "sender_age_group": []
        }

    filters = st.session_state.analytics_filters

    with st.spinner("Analyzing ecosystem..."):
        kpi_data       = data_service.get_kpi_summary()
        txn_data       = data_service.get_transaction_overview()
        comp_data      = data_service.get_comparison_data()
        temp_data      = data_service.get_temporal_analysis()
        geo_data       = data_service.get_state_distribution()
        fail_data      = data_service.get_failure_analysis()
        stats_data     = data_service.get_statistical_tests()
        rank_data      = data_service.get_rankings()
        bank_data      = data_service.get_bank_performance()
        fraud_data_adv = data_service.get_fraud_analysis()
        table_data     = data_service.get_filtered_transactions(filters)
        net_data       = data_service.get_network_graph_data(filters)
        trend_data     = data_service.get_trend_analysis()
        corr_data      = data_service.get_correlation_analysis()

    if kpi_data["status"] == "error":
        st.error(f"Failed to load analytics: {kpi_data.get('error')}")
        return

    # If no data is available (no backend, no mock), show empty state
    if not kpi_data.get("data"):
        st.title("Analytics Dashboard")
        st.info("No analytics data available. Connect a backend service or provide mock data to see insights here.")
        with st.container(border=True):
            st.markdown("### Overview")
            cols = st.columns(4, gap="small")
            for c in cols:
                with c:
                    st.metric("—", "N/A")
        return

    # === LAYOUT: Main Content (Left) | Filters (Right) ===
    # gap="medium" gives breathing room between content and filter panel
    main_col, filter_col = st.columns([5, 1], gap="medium", vertical_alignment="top")

    with filter_col:
        render_filters()

    with main_col:
        st.title("Analytics Dashboard")
        st.markdown(
            f"**Period:** {filters['date_range'][0].strftime('%Y-%m-%d')} "
            f"to {filters['date_range'][1].strftime('%Y-%m-%d')}"
        )

        render_kpi_section(kpi_data["data"])

        tab_overview, tab_deep_dive, tab_intel, tab_data_grid = st.tabs(
            ["Overview", "Deep Dive Analysis", "Network & Trends (Beta)", "Transaction Data"]
        )

        with tab_overview:
            render_transaction_overview(txn_data["data"])
            render_comparison_section(comp_data["data"])
            render_temporal_analysis(temp_data["data"])
            render_geo_and_failure(geo_data["data"], fail_data["data"])

        with tab_deep_dive:
            render_statistical_analysis(stats_data["data"])
            render_rankings_section(rank_data["data"])
            render_bank_matrix(bank_data["data"])
            render_fraud_deep_dive(fraud_data_adv["data"])

        with tab_intel:
            render_network_analysis(net_data["data"])
            render_trend_forecast(trend_data["data"])
            render_correlation_lab(corr_data["data"])

        with tab_data_grid:
            render_transaction_table(table_data["data"])


# Standalone execution for testing
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Prime Analyst Analytics")
    render_analytics()