# --- START OF FILE components/reports.py ---
"""
components/reports.py
Refactored to use latest Streamlit APIs:
  - st.columns(gap, vertical_alignment, border)
  - st.container(horizontal, horizontal_alignment, key)
  - st.form(border, width)
  - st.dataframe(key)
  - st.plotly_chart(key)

Layout  : Header -> Configuration card -> [Main tabs + Right filters panel] -> Action bar
Data    : All data sourced via ReportDataService interface. No mock data here.
Export  : PDF (reportlab + plotly charts via kaleido), Excel (openpyxl), CSV (pandas)
Preview : In-page preview for all three formats, toggled by the Preview button

Backend integration — implement src/report_service.py:
    class ReportDataService:
        def get_kpi_summary(self, filters) -> dict
        def get_ai_insights(self, report_type, filters) -> dict
        def get_metric_data(self, metric_name, filters) -> dict
        def get_trend_data(self, granularity, filters) -> dict
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import re
import io
import csv
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
try:
    from src.report_service import ReportDataService
    data_service = ReportDataService()
except ImportError:
    try:
        from test_ui import MockReportDataService
        data_service = MockReportDataService()
    except ImportError:
        data_service = None

from components.styles import get_report_css

# ==========================================
# 2. METRIC CATEGORIES
# ==========================================
try:
    from metric_registry import METRIC_CATEGORIES
except ImportError:
    # Metric categories aligned with backend schema (transaction dataset columns)
    # Backend columns: transaction_id, timestamp, transaction_type, merchant_category,
    # amount_inr, transaction_status, sender_age_group, receiver_age_group, sender_state,
    # sender_bank, receiver_bank, device_type, network_type, fraud_flag, hour_of_day,
    # day_of_week, is_weekend
    METRIC_CATEGORIES = {
        "Transaction Overview": {
            "icon_color": "#EAE5E0",   # primary tint
            "metrics": [
                "Total transaction volume",
                "Total transaction value (amount_inr)",
                "Average transaction value",
                "Transaction success rate",
                "Transaction failure rate",
                "Transaction pending rate",
                "Transaction volume by type (P2P/P2M/Bill Payment/Recharge)",
                "Transaction trends (daily/weekly)",
                "Peak transaction hours (hour_of_day)",
                "Weekend vs weekday volume",
            ],
        },
        "Device & Network": {
            "icon_color": "#E4EBD9",   # rupay tint
            "metrics": [
                "Volume by device type (Android/iOS/Web)",
                "Success rate by device type",
                "Failure rate by device type",
                "Volume by network type (4G/5G/WiFi)",
                "Success rate by network type",
                "Device × Network matrix",
                "Fraud rate by device type",
                "Fraud rate by network type",
            ],
        },
        "Fraud & Risk": {
            "icon_color": "#F5DDD9",   # danger tint
            "metrics": [
                "Overall fraud flag rate",
                "Fraud rate by transaction type",
                "Fraud rate by sender state",
                "Fraud rate by sender bank",
                "Fraud rate by age group",
                "High-risk hour analysis",
                "Fraud flag count",
                "Fraud rate trends",
            ],
        },
        "Geographic Distribution": {
            "icon_color": "#E2EBD8",   # rupay soft tint
            "metrics": [
                "Volume by sender state",
                "Value by sender state",
                "Success rate by sender state",
                "Failure rate by sender state",
                "Top 10 states by volume",
                "State-wise fraud rate",
            ],
        },
        "Bank Performance": {
            "icon_color": "#E5E1DB",   # secondary tint
            "metrics": [
                "Volume by sender bank",
                "Volume by receiver bank",
                "Success rate by sender bank",
                "Success rate by receiver bank",
                "Sender × Receiver bank matrix",
                "Bank-wise fraud rate",
                "Bank-wise average transaction value",
            ],
        },
        "Temporal Patterns": {
            "icon_color": "#F5EDDA",   # warning tint
            "metrics": [
                "Hourly distribution (24h pattern)",
                "Day of week distribution",
                "Peak vs off-peak comparison",
                "Weekend vs weekday comparison",
                "Hourly success/failure rates",
                "Hour × Day heatmap",
            ],
        },
        "Age Group Analysis": {
            "icon_color": "#EDE8E3",   # primary soft tint
            "metrics": [
                "Volume by sender age group",
                "Value by sender age group",
                "Average transaction by age group",
                "P2P receiver age group distribution",
                "Age group × transaction type breakdown",
                "Fraud rate by age group",
            ],
        },
        "Merchant Category": {
            "icon_color": "#DFF0E7",   # success tint
            "metrics": [
                "P2M volume by merchant category",
                "P2M value by merchant category",
                "Success rate by merchant category",
                "Top merchant categories",
                "Merchant category trends",
            ],
        },
        "Comparative Analysis": {
            "icon_color": "#F0DEDA",   # danger softest tint
            "metrics": [
                "Android vs iOS comparison",
                "4G vs 5G comparison",
                "P2P vs P2M comparison",
                "Weekday vs weekend comparison",
                "Bank performance comparison",
                "State performance comparison",
            ],
        },
    }


# ==========================================
# UTILITY: category key
# ==========================================
def _cat_key(category_name: str) -> str:
    return category_name.lower().replace(" ", "_").replace("&", "and")


def _get_all_selected_flat() -> list:
    result = []
    for v in st.session_state.get("rg_selected_metrics", {}).values():
        result.extend(v)
    return result


def _get_selected_for_category(category_name: str) -> list:
    return st.session_state.get("rg_selected_metrics", {}).get(_cat_key(category_name), [])


# ==========================================
# BACKEND INTEGRATION HELPER
# ==========================================
def get_report_query_params() -> dict:
    """
    Returns a clean, structured dict that the backend can consume directly.
    Call this from your ReportDataService or API handler instead of reading
    session_state keys individually.

    Shape returned:
    {
        "report_type":   str,         # e.g. "Revenue Report"
        "start_date":    date,
        "end_date":      date,
        "sender_state":  str,
        "device_type":   str,
        "metrics":       list[str],   # from config-card multiselect
        "dimensions":    list[str],
        "selected_metric_ids": list[str],  # from category checkboxes (flat)
        "ai": {
            "enabled":   bool,
            "depth":     str,   # "Summary" | "Detailed" | "Executive"
            "custom_query": str,  # free-text prompt entered by user (may be "")
        },
        "email_log":     list[dict],  # [{email, timestamp, metric_count}, ...]
        "output_format": str,
    }
    """
    date_range = st.session_state.get("rg_date_range",
                                       (datetime.now() - timedelta(days=30), datetime.now()))
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
        end_date   = datetime.now().date()

    return {
        "report_type":         st.session_state.get("rg_report_type", "Revenue Report"),
        "start_date":          start_date,
        "end_date":            end_date,
        "sender_state":        st.session_state.get("rg_region_filter", "All States"),
        "device_type":         st.session_state.get("rg_platform_filter", "All"),
        "metrics":             st.session_state.get("rg_metrics_select", []),
        "dimensions":          st.session_state.get("rg_dimensions_select", []),
        "selected_metric_ids": _get_all_selected_flat(),
        "ai": {
            "enabled":      st.session_state.get("rg_ai_insights", "Yes") == "Yes",
            "depth":        st.session_state.get("rg_ai_insight_depth", "Summary"),
            "custom_query": st.session_state.get("rg_ai_custom_query", ""),
        },
        "email_log":    st.session_state.get("rg_email_log", []),
        "output_format": st.session_state.get("rg_output_format", "PDF Document (.pdf)"),
    }



# ==========================================
# 4. STATE INITIALIZATION
# ==========================================
def _init_state():
    defaults = {
        "rg_selected_metrics":  {},
        "rg_email_log":         [],
        "rg_trend_granularity": "Daily",
        "rg_ai_insights":       "Yes",
        "rg_ai_insight_depth":  "Summary",
        "rg_ai_custom_query":   "",
        "rg_region_filter":     "All States",
        "rg_platform_filter":   "All",
        "rg_output_format":     "PDF Document (.pdf)",
        "rg_report_type":       "Revenue Report",
        "rg_preview_open":      False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Guarantee every category has a list entry
    for cat_name in METRIC_CATEGORIES:
        ck = _cat_key(cat_name)
        if ck not in st.session_state["rg_selected_metrics"]:
            st.session_state["rg_selected_metrics"][ck] = []


# ==========================================
# FILTERS DICT
# ==========================================
def _build_filters(start_date, end_date) -> dict:
    return {
        "start_date":     start_date,
        "end_date":       end_date,
        "report_type":    st.session_state.get("rg_report_type", "Revenue Report"),
        "sender_state":   st.session_state.get("rg_region_filter", "All States"),
        "device_type":    st.session_state.get("rg_platform_filter", "All"),
        "metrics":        st.session_state.get("rg_metrics_select", []),
        "dimensions":     st.session_state.get("rg_dimensions_select", []),
        "ai_depth":       st.session_state.get("rg_ai_insight_depth", "Summary"),
        "ai_custom_query": st.session_state.get("rg_ai_custom_query", ""),
    }


# ==========================================
# CAPABILITY CHECKS
# ==========================================
def _reportlab_ok() -> bool:
    try:
        import reportlab  # noqa
        return True
    except ImportError:
        return False


def _kaleido_ok() -> bool:
    try:
        import kaleido  # noqa
        return True
    except ImportError:
        return False


def _openpyxl_ok() -> bool:
    try:
        import openpyxl  # noqa
        return True
    except ImportError:
        return False


# ==========================================
# CHART BUILDER (shared by UI renderer and PDF exporter)
# ==========================================
def _build_metric_figure(metric_name: str, data: dict, height: int = 200):
    """
    Returns a plotly Figure or None (for kpi type).
    data shapes:
      kpi   : {"type":"kpi",   "value":str, "delta":str, "positive":bool}
      donut : {"type":"donut", "value":int(0-100), ...}
      line  : {"type":"line",  "values":list, "labels":list, ...}
      bar   : {"type":"bar",   "values":list, "labels":list, ...}
    """
    chart_type = data.get("type", "kpi")

    if chart_type == "donut":
        val = data.get("value", 0)
        fig = go.Figure(go.Pie(
            values=[val, max(0, 100 - val)],
            labels=[metric_name, ""],
            hole=0.65,
            marker_colors=[COLORS["primary"], COLORS["bg"]],
            textinfo="none",
            hoverinfo="skip",
            showlegend=False,
        ))
        fig.add_annotation(
            text=f"{val}%", x=0.5, y=0.5,
            font=dict(size=18, color=COLORS["primary"]),
            showarrow=False,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=height,
            title=dict(text=metric_name, font=dict(size=12, color=COLORS["secondary"])),
        )
        return fig

    if chart_type == "line":
        fig = go.Figure(go.Scatter(
            x=data.get("labels", []),
            y=data.get("values", []),
            mode="lines",
            fill="tozeroy",
            line=dict(color=COLORS["primary"], width=2),
            fillcolor="rgba(74,59,50,0.08)",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=height,
            title=dict(text=metric_name, font=dict(size=12, color=COLORS["secondary"])),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor=COLORS["bg"]),
            font=dict(family="'DM Sans','Segoe UI',sans-serif"),
        )
        return fig

    if chart_type == "bar":
        fig = go.Figure(go.Bar(
            x=data.get("labels", []),
            y=data.get("values", []),
            marker_color=COLORS["secondary"],
            marker_opacity=0.8,
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=height,
            title=dict(text=metric_name, font=dict(size=12, color=COLORS["secondary"])),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor=COLORS["bg"]),
            font=dict(family="'DM Sans','Segoe UI',sans-serif"),
        )
        return fig

    return None  # kpi type has no figure


def render_metric_widget(metric_name: str, data: dict, height: int = 200):
    """Render a single metric widget in the Streamlit UI."""
    chart_type = data.get("type", "kpi")

    if chart_type == "kpi":
        delta_color = COLORS["success"] if data.get("positive", True) else COLORS["danger"]
        safe_key = f"mw_{re.sub(r'[^a-z0-9]', '_', metric_name[:30].lower())}"
        with st.container(key=safe_key):
            st.markdown(
                f"<p style='color:#6B7280; font-size:0.8rem; font-weight:600;"
                f"text-transform:uppercase; letter-spacing:0.04em; margin:0;'>"
                f"{metric_name}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='color:#111827; font-size:1.8rem; font-weight:700;"
                f"margin:0.25rem 0 0 0; line-height:1.2;'>"
                f"{data.get('value', '—')}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='color:{delta_color}; font-size:0.82rem; font-weight:600;"
                f"margin:0.25rem 0 0 0;'>"
                f"{data.get('delta', '')} "
                f"<span style='color:#9CA3AF; font-weight:400;'>vs last period</span></p>",
                unsafe_allow_html=True,
            )
    else:
        fig = _build_metric_figure(metric_name, data, height)
        if fig:
            safe_key = f"chart_{re.sub(r'[^a-z0-9]', '_', metric_name[:30].lower())}"
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False}, key=safe_key)


# ==========================================
# EXPORT: shared row builder
# ==========================================
def _build_metrics_rows(data_service, filters: dict) -> list:
    rows = []
    for cat_name in METRIC_CATEGORIES:
        for metric in _get_selected_for_category(cat_name):
            if data_service:
                resp  = data_service.get_metric_data(metric, filters)
                mdata = resp.get("data", {}) if resp.get("status") == "success" else {}
            else:
                mdata = {}
            mtype = mdata.get("type", "kpi")
            if mtype == "donut":
                value = f"{mdata.get('value', '—')}%"
            elif mtype in ("line", "bar"):
                vals  = mdata.get("values", [])
                value = f"{vals[-1]:,}" if vals else "—"
            else:
                value = mdata.get("value", "—")
            rows.append({
                "Category": cat_name,
                "Metric":   metric,
                "Value":    value,
                "Delta":    mdata.get("delta", "—"),
                "Trend":    "Up" if mdata.get("positive", True) else "Down",
            })
    return rows


# ==========================================
# EXPORT: PDF
# ==========================================
def _fig_to_png_bytes(fig, width: int = 500, height: int = 250):
    if not _kaleido_ok():
        return None
    try:
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None


def _generate_pdf(data_service, filters: dict, kpi_data: list, ai_insights: dict) -> bytes:
    start_date  = filters["start_date"]
    end_date    = filters["end_date"]
    report_type = filters["report_type"]
    granularity = st.session_state.get("rg_trend_granularity", "Daily")
    import re as _re

    if not _reportlab_ok():
        lines = ["PRIME ANALYST - REPORT",
                 f"{report_type} | {start_date} to {end_date} | {granularity}", "="*60]
        if not _kaleido_ok():
            lines.append("[Charts omitted: install kaleido for chart images: "
                         "pip install kaleido]")
        if ai_insights.get("narrative"):
            lines += ["", "AI INSIGHTS",
                      _re.sub(r"<[^>]+>", "", ai_insights["narrative"])]
        for row in _build_metrics_rows(data_service, filters):
            lines.append(f"{row['Category']} | {row['Metric']} | {row['Value']} | {row['Delta']}")
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(lines).encode("utf-8")

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, Image as RLImage,
    )
    from reportlab.lib.enums import TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    C_DARK   = HexColor(COLORS["primary"])
    C_MUTED  = HexColor(COLORS["secondary"])
    C_SECND  = HexColor(COLORS["secondary"])   # replaces C_BLUE
    C_BORDER = HexColor("#E5E0D8")             # mid-tone between card and bg
    C_BG     = HexColor(COLORS["bg"])
    C_GREEN  = HexColor(COLORS["success"])
    C_RED    = HexColor(COLORS["danger"])

    styles = getSampleStyleSheet()
    title_s   = ParagraphStyle("T", parent=styles["Normal"], fontSize=22,
                                fontName="Helvetica-Bold", textColor=C_DARK, spaceAfter=4)
    sub_s     = ParagraphStyle("S", parent=styles["Normal"], fontSize=10,
                                fontName="Helvetica", textColor=C_MUTED, spaceAfter=16)
    section_s = ParagraphStyle("Se", parent=styles["Normal"], fontSize=8,
                                fontName="Helvetica-Bold", textColor=C_MUTED,
                                spaceBefore=14, spaceAfter=6)
    body_s    = ParagraphStyle("B", parent=styles["Normal"], fontSize=9,
                                fontName="Helvetica", textColor=C_DARK,
                                spaceAfter=6, leading=14)
    footer_s  = ParagraphStyle("F", parent=styles["Normal"], fontSize=7,
                                fontName="Helvetica", textColor=C_MUTED, alignment=TA_CENTER)

    def _hr():
        return HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=8)

    def _tbl_style(rows_count):
        base = [
            ("BACKGROUND", (0, 0), (-1, 0), C_BG),
            ("TEXTCOLOR",  (0, 0), (-1, 0), C_MUTED),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, 0), 7),
            ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",   (0, 1), (-1, -1), 9),
            ("TEXTCOLOR",  (0, 1), (-1, -1), C_DARK),
            ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
            ("ALIGN",      (0, 0), (0, -1), "LEFT"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("BOX",        (0, 0), (-1, -1), 0.5, C_BORDER),
            ("INNERGRID",  (0, 0), (-1, -1), 0.5, C_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ]
        for i in range(1, rows_count):
            if i % 2 == 0:
                base.append(("BACKGROUND", (0, i), (-1, i), C_BG))
        return TableStyle(base)

    story = []
    story.append(Paragraph("Prime Analyst", title_s))
    story.append(Paragraph(
        f"{report_type}  |  {start_date.strftime('%b %d, %Y')} - "
        f"{end_date.strftime('%b %d, %Y')}  |  {granularity}", sub_s))
    story.append(_hr())

    # KPIs
    if kpi_data:
        story.append(Paragraph("KEY PERFORMANCE INDICATORS", section_s))
        kpi_rows = [["METRIC", "VALUE", "CHANGE", "DIRECTION"]]
        for k in kpi_data:
            kpi_rows.append([k.get("label",""), k.get("value","—"),
                             k.get("delta","—"),
                             "Up" if k.get("positive", True) else "Down"])
        t = Table(kpi_rows, colWidths=["40%","20%","20%","20%"])
        t.setStyle(_tbl_style(len(kpi_rows)))
        story.append(t)
        story.append(Spacer(1, 12))

    # AI Insights
    if ai_insights.get("narrative"):
        story.append(_hr())
        story.append(Paragraph("AI INSIGHTS", section_s))
        story.append(Paragraph(_re.sub(r"<[^>]+>", "", ai_insights["narrative"]), body_s))
        for flag in ai_insights.get("risk_flags", []):
            story.append(Paragraph(f"  - {_re.sub(r'<[^>]+>', '', flag)}", body_s))
        if ai_insights.get("recommendations"):
            story.append(Paragraph("Recommendations:", section_s))
            for i, rec in enumerate(ai_insights["recommendations"], 1):
                story.append(Paragraph(f"  {i}. {_re.sub(r'<[^>]+>', '', rec)}", body_s))
        story.append(Spacer(1, 10))

    # ── Revenue Trends chart ─────────────────────────────────────────────
    if data_service and _kaleido_ok():
        granularity_val = st.session_state.get("rg_trend_granularity", "Daily")
        tr = data_service.get_trend_data(granularity_val, filters)
        td = tr.get("data", {}) if tr.get("status") == "success" else {}
        if td:
            trend_fig = go.Figure(go.Bar(
                x=td.get("labels", []),
                y=td.get("values", []),
                marker_color=COLORS["success"],
                marker_opacity=0.85,
            ))
            trend_fig.update_layout(
                paper_bgcolor="white",
                plot_bgcolor="white",
                margin=dict(l=10, r=10, t=30, b=10),
                height=220,
                title=dict(text=f"Revenue Trends ({granularity_val})",
                           font=dict(size=12, color=COLORS["secondary"])),
                xaxis=dict(showgrid=False, tickfont=dict(size=9)),
                yaxis=dict(showgrid=True, gridcolor="#E5E0D8",
                           tickprefix="$", tickformat=",.0f"),
                font=dict(family="Helvetica"),
            )
            png = _fig_to_png_bytes(trend_fig, width=500, height=220)
            if png:
                story.append(_hr())
                story.append(Paragraph("REVENUE TRENDS", section_s))
                img_buf = io.BytesIO(png)
                rl_img  = RLImage(img_buf, width=160*mm, height=70*mm)
                story.append(rl_img)
                story.append(Spacer(1, 12))

    # Metrics table + charts
    all_flat = _get_all_selected_flat()
    if all_flat:
        story.append(_hr())
        story.append(Paragraph("SELECTED METRICS", section_s))

        metric_rows = [["CATEGORY", "METRIC", "VALUE", "DELTA", "TREND"]]
        chart_items = []

        for cat_name in METRIC_CATEGORIES:
            selected = _get_selected_for_category(cat_name)
            for metric in selected:
                if data_service:
                    resp  = data_service.get_metric_data(metric, filters)
                    mdata = resp.get("data", {}) if resp.get("status") == "success" else {}
                else:
                    mdata = {}
                mtype = mdata.get("type", "kpi")
                if mtype == "donut":
                    val = f"{mdata.get('value','—')}%"
                elif mtype in ("line", "bar"):
                    vals = mdata.get("values", [])
                    val  = f"{vals[-1]:,}" if vals else "—"
                else:
                    val = mdata.get("value", "—")
                trend = "Up" if mdata.get("positive", True) else "Down"
                metric_rows.append([
                    cat_name[:22], metric[:38], val,
                    mdata.get("delta", "—"), trend,
                ])
                if mtype != "kpi":
                    fig = _build_metric_figure(metric, mdata, height=220)
                    if fig and _kaleido_ok():
                        png = _fig_to_png_bytes(fig, width=480, height=220)
                        if png:
                            chart_items.append((metric, png))

        m_tbl = Table(metric_rows, colWidths=["22%","36%","14%","14%","14%"])
        ts = _tbl_style(len(metric_rows))
        # Color trend cell
        for i in range(1, len(metric_rows)):
            pos = metric_rows[i][4] == "Up"
            ts._cmds.append(("TEXTCOLOR", (4, i), (4, i), C_GREEN if pos else C_RED))
        m_tbl.setStyle(ts)
        story.append(m_tbl)
        story.append(Spacer(1, 16))

        # Chart images
        if chart_items:
            story.append(_hr())
            story.append(Paragraph("METRIC CHARTS", section_s))
            for m_name, png_bytes in chart_items:
                story.append(Paragraph(m_name, body_s))
                img_buf = io.BytesIO(png_bytes)
                rl_img  = RLImage(img_buf, width=160*mm, height=75*mm)
                story.append(rl_img)
                story.append(Spacer(1, 8))

    story.append(Spacer(1, 16))
    story.append(_hr())
    story.append(Paragraph(
        f"Generated by Prime Analyst  |  "
        f"{datetime.now().strftime('%B %d, %Y at %H:%M')}  |  Confidential",
        footer_s,
    ))
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ==========================================
# EXPORT: Excel
# ==========================================
def _generate_excel(data_service, filters: dict, kpi_data: list) -> bytes:
    buf = io.BytesIO()
    engine = "openpyxl" if _openpyxl_ok() else "xlsxwriter"
    with pd.ExcelWriter(buf, engine=engine) as writer:
        if kpi_data:
            pd.DataFrame(kpi_data).to_excel(writer, sheet_name="KPIs", index=False)
        rows = _build_metrics_rows(data_service, filters)
        if rows:
            pd.DataFrame(rows).to_excel(writer, sheet_name="Metrics", index=False)
        meta = pd.DataFrame([{
            "Report Type":  filters["report_type"],
            "Start Date":   str(filters["start_date"]),
            "End Date":     str(filters["end_date"]),
            "Sender State": filters.get("sender_state", "All States"),
            "Device Type":  filters.get("device_type", "All"),
            "Generated At": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }])
        meta.to_excel(writer, sheet_name="Metadata", index=False)
    buf.seek(0)
    return buf.read()


# ==========================================
# EXPORT: CSV
# ==========================================
def _generate_csv(data_service, filters: dict, kpi_data: list) -> bytes:
    out = io.StringIO()
    w   = csv.writer(out)
    w.writerow(["PRIME ANALYST - REPORT"])
    w.writerow([f"Type: {filters['report_type']}",
                f"Period: {filters['start_date']} to {filters['end_date']}"])
    w.writerow([])
    if kpi_data:
        w.writerow(["--- KEY PERFORMANCE INDICATORS ---"])
        w.writerow(["Label", "Value", "Delta", "Direction"])
        for k in kpi_data:
            w.writerow([k.get("label"), k.get("value"), k.get("delta"),
                        "Up" if k.get("positive", True) else "Down"])
        w.writerow([])
    rows = _build_metrics_rows(data_service, filters)
    if rows:
        w.writerow(["--- METRICS ---"])
        w.writerow(["Category", "Metric", "Value", "Delta", "Trend"])
        for r in rows:
            w.writerow([r["Category"], r["Metric"], r["Value"], r["Delta"], r["Trend"]])
    w.writerow([])
    w.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    return out.getvalue().encode("utf-8")


# ==========================================
# AI INSIGHTS PANEL
# ==========================================
def _render_ai_insights_panel(ai_insights: dict, report_type: str):
    """
    Renders AI insights inside a bordered container using only st.* components.
    ai_insights shape:
      { status, depth, narrative, bullets, risk_flags, recommendations, generated_at }
    """
    status = ai_insights.get("status", "unavailable")
    depth  = ai_insights.get("depth", "Summary")

    with st.container(key="rg_ai_panel", border=True):
        hdr_col, badge_col = st.columns([4, 1])
        with hdr_col:
            st.markdown(
                f"<p style='font-size:14px;font-weight:700;"
                f"color:#111827;margin:0'>AI Insights</p>",
                unsafe_allow_html=True,
            )
        with badge_col:
            st.markdown(
                f"<span class='rg-generated-badge'>{depth.upper()}</span>",
                unsafe_allow_html=True,
            )

        if status == "unavailable":
            st.info("AI Insights require a connected backend. "
                    "Enable once the backend is available.")
            return

        if status == "loading":
            with st.spinner("Generating AI insights..."):
                pass
            return

        narrative = ai_insights.get("narrative", "")
        if narrative:
            st.markdown(narrative, unsafe_allow_html=True)

        risk_flags = ai_insights.get("risk_flags", [])
        if risk_flags and depth in ("Detailed", "Executive"):
            st.divider()
            st.markdown(
                f"<p style='font-size:11px;font-weight:700;color:{COLORS['danger']};"
                f"text-transform:uppercase;letter-spacing:.05em;margin:0'>Risk Flags</p>",
                unsafe_allow_html=True,
            )
            for flag in risk_flags:
                st.warning(flag)

        bullets = ai_insights.get("bullets", [])
        if bullets and depth in ("Detailed", "Executive"):
            st.divider()
            st.markdown(
                f"<p style='font-size:11px;font-weight:700;color:#6B7280;"
                f"text-transform:uppercase;letter-spacing:.05em;margin:0'>Key Findings</p>",
                unsafe_allow_html=True,
            )
            for b in bullets:
                st.markdown(f"- {b}")

        recs = ai_insights.get("recommendations", [])
        if recs and depth == "Executive":
            st.divider()
            st.markdown(
                f"<p style='font-size:11px;font-weight:700;color:{COLORS['success']};"
                f"text-transform:uppercase;letter-spacing:.05em;margin:0'>Recommendations</p>",
                unsafe_allow_html=True,
            )
            for i, rec in enumerate(recs, 1):
                st.markdown(f"**{i}.** {rec}")

        gen_time = ai_insights.get("generated_at", "")
        if gen_time:
            st.caption(f"Generated {gen_time}")


# ==========================================
# SUMMARY TAB
# ==========================================
def _render_summary_tab(data_service, filters: dict):
    report_type = filters.get("report_type", "Revenue Report")

    if st.session_state.get("rg_ai_insights", "Yes") == "Yes":
        if data_service:
            ai_resp = data_service.get_ai_insights(report_type, filters)
            ai_data = ai_resp.get("data", {"status": "unavailable"})
        else:
            ai_data = {"status": "unavailable"}
        _render_ai_insights_panel(ai_data, report_type)

    # KPI Cards — HTML-rendered to use explicit earthy trend colors
    # (avoids Streamlit's default red/green delta palette)
    if data_service:
        kpi_resp = data_service.get_kpi_summary(filters)
        kpis = kpi_resp.get("data", []) if kpi_resp.get("status") == "success" else []
    else:
        kpis = []

    with st.container(key="rg_kpi_row"):
        if not kpis:
            st.info("KPI data will appear here once the backend is connected.")
        else:
            kpi_cols = st.columns(len(kpis))
            for idx, (col, kpi) in enumerate(zip(kpi_cols, kpis)):
                with col:
                    positive     = kpi.get("positive", True)
                    trend_color  = "#4A7C59" if positive else "#B44C3A"   # earthy sage / terracotta
                    trend_bg     = "rgba(74, 124, 89, 0.10)" if positive else "rgba(180, 76, 58, 0.10)"
                    trend_arrow  = "↑" if positive else "↓"
                    delta        = kpi.get("delta", "")
                    with st.container(key=f"rg_kpi_{idx}", border=True):
                        st.markdown(
                            f"<p style='color:#6B7280; font-size:0.78rem; font-weight:600; "
                            f"text-transform:uppercase; letter-spacing:0.04em; margin:0;'>"
                            f"{kpi.get('label', '')}</p>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"<p style='color:#111827; font-size:1.8rem; font-weight:700; "
                            f"margin:0.25rem 0 0.5rem 0; line-height:1.2;'>"
                            f"{kpi.get('value', '—')}</p>",
                            unsafe_allow_html=True,
                        )
                        if delta:
                            st.markdown(
                                f"<span style='display:inline-flex; align-items:center; gap:4px; "
                                f"background:{trend_bg}; color:{trend_color}; font-size:0.82rem; "
                                f"font-weight:600; padding:3px 8px; border-radius:6px;'>"
                                f"{trend_arrow} {delta}</span>",
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            f"<p style='color:#9CA3AF; font-size:0.75rem; margin:0.5rem 0 0;'>"
                            f"{kpi.get('subtext', 'vs. previous 30 days')}</p>",
                            unsafe_allow_html=True,
                        )

    # Revenue Trends
    with st.container(key="rg_trends_section", border=True):
        trend_hdr, gran_col = st.columns([3, 1])
        with trend_hdr:
            st.markdown(
                f"<p style='font-size:13px;font-weight:700;"
                f"color:#111827;margin:0'>Revenue Trends</p>",
                unsafe_allow_html=True,
            )
        with gran_col:
            st.radio(
                "Granularity",
                ["Daily", "Weekly", "Monthly"],
                horizontal=True,
                label_visibility="collapsed",
                key="rg_trend_granularity",
            )

        granularity = st.session_state.get("rg_trend_granularity", "Daily")
        if data_service:
            tr = data_service.get_trend_data(granularity, filters)
            td = tr.get("data", {}) if tr.get("status") == "success" else {}
        else:
            td = {}

        if td:
            fig = go.Figure(go.Bar(
                x=td.get("labels", []),
                y=td.get("values", []),
                marker_color=COLORS["success"],
                marker_opacity=0.85,
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=8, b=0),
                height=220,
                xaxis=dict(showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor=COLORS["bg"],
                           tickprefix="$", tickformat=",.0f"),
                font=dict(family="'DM Sans','Segoe UI',sans-serif"),
            )
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False}, key="rg_trend_chart")
        else:
            st.info("Connect the backend to see revenue trends.")


# ==========================================
# CHARTS TAB
# ==========================================
def _render_charts_tab(data_service, filters: dict):
    all_flat = _get_all_selected_flat()
    if not all_flat:
        st.info("Select metrics using the category panel on the right to preview charts here.")
        return
    if not data_service:
        st.warning("Connect the backend to populate metric charts.")
        return

    MAX_CHARTS  = 20
    chart_count = 0

    for cat_name in METRIC_CATEGORIES:
        selected = _get_selected_for_category(cat_name)
        if not selected:
            continue
        with st.container(key=f"charts_sec_{_cat_key(cat_name)}"):
            st.markdown(f"<p class='preview-section-header'>{cat_name}</p>",
                        unsafe_allow_html=True)
            c_a, c_b = st.columns(2)
            cols = [c_a, c_b]
            for i, metric in enumerate(selected):
                if chart_count >= MAX_CHARTS:
                    remaining = len(all_flat) - MAX_CHARTS
                    st.caption(f"+ {remaining} more metrics included in the full export")
                    return
                resp  = data_service.get_metric_data(metric, filters)
                mdata = resp.get("data", {"type":"kpi","value":"—","delta":"—","positive":True})
                with cols[i % 2]:
                    render_metric_widget(metric, mdata, height=180)
                chart_count += 1


# ==========================================
# TABLES TAB
# ==========================================
def _render_tables_tab(data_service, filters: dict):
    if not data_service:
        st.warning("Connect the backend to populate metric tables.")
        return

    any_shown = False
    for cat_name in METRIC_CATEGORIES:
        selected = _get_selected_for_category(cat_name)
        if not selected:
            continue
        any_shown = True
        with st.container(key=f"tables_sec_{_cat_key(cat_name)}"):
            st.markdown(f"<p class='preview-section-header'>{cat_name}</p>",
                        unsafe_allow_html=True)
            rows = []
            for metric in selected:
                resp  = data_service.get_metric_data(metric, filters)
                mdata = resp.get("data", {})
                mtype = mdata.get("type", "kpi")
                if mtype == "donut":
                    val = f"{mdata.get('value','—')}%"
                elif mtype in ("line","bar"):
                    vals = mdata.get("values", [])
                    val  = f"{vals[-1]:,}" if vals else "—"
                else:
                    val = mdata.get("value","—")
                rows.append({
                    "Metric": metric,
                    "Value":  val,
                    "Delta":  mdata.get("delta","—"),
                    "Trend":  "Up" if mdata.get("positive",True) else "Down",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not any_shown:
        st.info("Select metrics using the category panel on the right to see tables here.")


# ==========================================
# FULL REPORT TAB
# ==========================================
def _render_full_report_tab(data_service, filters: dict, start_date, end_date):
    all_flat    = _get_all_selected_flat()
    report_type = filters["report_type"]
    granularity = st.session_state.get("rg_trend_granularity", "Daily")

    with st.container(key="rg_full_meta"):
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Report Type", report_type)
        with m2:
            st.metric("Date Range",
                      f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")
        with m3:
            st.metric("Granularity", granularity)
        with m4:
            st.metric("Metrics Selected", len(all_flat))

    if not all_flat:
        st.info("Select metrics using the category panel on the right to include "
                "them in the full report.")
        return

    for cat_name in METRIC_CATEGORIES:
        selected = _get_selected_for_category(cat_name)
        if not selected:
            continue
        with st.expander(f"**{cat_name}** — {len(selected)} metrics", expanded=False):
            if data_service:
                rows = []
                for metric in selected:
                    resp  = data_service.get_metric_data(metric, filters)
                    mdata = resp.get("data", {})
                    mtype = mdata.get("type","kpi")
                    val   = (f"{mdata.get('value')}%" if mtype == "donut"
                             else mdata.get("value","—"))
                    rows.append({"Metric": metric, "Value": val,
                                 "Delta": mdata.get("delta","—")})
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                for metric in selected:
                    st.markdown(f"- {metric}")


# ==========================================
# PREVIEW PANEL
# ==========================================
def _render_preview(data_service, filters: dict, kpi_data: list,
                    ai_insights: dict, start_date, end_date):
    """In-page preview for all three formats — shown below the action bar."""
    output_format = st.session_state.get("rg_output_format", "PDF Document (.pdf)")
    all_flat      = _get_all_selected_flat()
    report_type   = filters["report_type"]
    import re as _re

    with st.container(key="rg_preview_panel", border=True):
        st.markdown(
            f"<p style='font-size:13px;font-weight:700;color:#111827;margin:0 0 4px'>"
            f"Report Preview</p>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"{report_type}  |  "
            f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}  |  "
            f"Format: {output_format}  |  {len(all_flat)} metrics"
        )
        st.divider()

        # Format capability warnings
        if "PDF" in output_format:
            if not _reportlab_ok():
                st.warning("Install `reportlab` for PDF export: `pip install reportlab`")
            if not _kaleido_ok():
                st.caption("Install `kaleido` to embed charts in PDF: `pip install kaleido`")
        elif "Excel" in output_format and not _openpyxl_ok():
            st.warning("Install `openpyxl` for Excel export: `pip install openpyxl`")

        # KPI preview — earthy HTML badges (no st.metric red/green)
        if kpi_data:
            st.markdown("**Key Performance Indicators**")
            n = min(len(kpi_data), 4)
            kpi_preview_cols = st.columns(n)
            for col, kpi in zip(kpi_preview_cols, kpi_data[:n]):
                with col:
                    positive    = kpi.get("positive", True)
                    trend_color = "#4A7C59" if positive else "#B44C3A"
                    trend_bg    = "rgba(74, 124, 89, 0.10)" if positive else "rgba(180, 76, 58, 0.10)"
                    trend_arrow = "↑" if positive else "↓"
                    delta       = kpi.get("delta", "")
                    st.markdown(
                        f"<p style='color:#6B7280;font-size:0.75rem;font-weight:600;"
                        f"text-transform:uppercase;letter-spacing:0.04em;margin:0;'>"
                        f"{kpi.get('label','')}</p>"
                        f"<p style='color:#111827;font-size:1.4rem;font-weight:700;"
                        f"margin:0.2rem 0;'>{kpi.get('value','—')}</p>"
                        + (f"<span style='background:{trend_bg};color:{trend_color};"
                           f"font-size:0.78rem;font-weight:600;padding:2px 7px;"
                           f"border-radius:5px;'>{trend_arrow} {delta}</span>" if delta else ""),
                        unsafe_allow_html=True,
                    )

        # AI Insights narrative preview
        if st.session_state.get("rg_ai_insights", "Yes") == "Yes" and ai_insights.get("narrative"):
            st.divider()
            st.markdown("**AI Insights**")
            clean = _re.sub(r"<[^>]+>", "", ai_insights.get("narrative", ""))
            st.info(clean)

        # Metrics table preview
        if all_flat:
            st.divider()
            st.markdown("**Selected Metrics**")
            rows = _build_metrics_rows(data_service, filters)
            if rows:
                with st.container(key="rg_preview_metrics_tbl"):
                    st.dataframe(pd.DataFrame(rows), use_container_width=True,
                                 hide_index=True, height=280)

        # ── Chart preview ──────────────────────────────────────────────
        if all_flat and data_service:
            st.divider()
            st.markdown("**Metric Charts**")
            chart_rendered = 0
            MAX_PREVIEW_CHARTS = 6
            for cat_name in METRIC_CATEGORIES:
                selected = _get_selected_for_category(cat_name)
                if not selected:
                    continue
                cols = st.columns(2)
                col_idx = 0
                for metric in selected:
                    if chart_rendered >= MAX_PREVIEW_CHARTS:
                        remaining = len(all_flat) - MAX_PREVIEW_CHARTS
                        st.caption(f"+ {remaining} more charts included in the full export")
                        break
                    resp  = data_service.get_metric_data(metric, filters)
                    mdata = resp.get("data", {}) if resp.get("status") == "success" else {}
                    if mdata.get("type", "kpi") == "kpi":
                        continue  # KPI scalars are shown in the table above
                    fig = _build_metric_figure(metric, mdata, height=180)
                    if fig:
                        safe_key = (f"prev_chart_{chart_rendered}_"
                                    f"{re.sub(r'[^a-z0-9]', '_', metric[:20].lower())}")
                        with cols[col_idx % 2]:
                            st.plotly_chart(fig, use_container_width=True,
                                            config={"displayModeBar": False},
                                            key=safe_key)
                        col_idx += 1
                        chart_rendered += 1
                else:
                    continue
                break  # inner break propagated


# ==========================================
# METRIC CATEGORY SELECTOR (Right panel)
# Fixed counter + proper state sync
# ==========================================
def _render_category_selector():
    """
    Expandable metric category checkboxes.
    Counter fix: reads count directly from rg_selected_metrics each render cycle.
    Select All uses rerun to ensure the counter updates immediately.
    """
    st.markdown("<p class='report-section-label'>Select Metrics by Category</p>",
                unsafe_allow_html=True)

    for cat_name, cat_data in METRIC_CATEGORIES.items():
        metrics  = cat_data["metrics"] if isinstance(cat_data, dict) else cat_data
        ck       = _cat_key(cat_name)
        sel_list = st.session_state["rg_selected_metrics"].get(ck, [])
        sel_count = len(sel_list)
        total     = len(metrics)

        with st.expander(f"**{cat_name}**  {sel_count}/{total}", expanded=False):

            # Select All  — value driven by actual state, not widget memory
            all_on = (sel_count == total)
            sa = st.checkbox(
                f"Select all ({total})",
                value=all_on,
                key=f"rg_sa_{ck}",
            )
            if sa and not all_on:
                st.session_state["rg_selected_metrics"][ck] = list(metrics)
                st.rerun()
            elif not sa and all_on:
                st.session_state["rg_selected_metrics"][ck] = []
                st.rerun()

            st.divider()

            # Individual metrics
            for i, metric in enumerate(metrics):
                checked = metric in st.session_state["rg_selected_metrics"][ck]
                val = st.checkbox(metric, value=checked, key=f"rg_{ck}_m{i}")
                # Sync to canonical list
                currently_in = metric in st.session_state["rg_selected_metrics"][ck]
                if val and not currently_in:
                    st.session_state["rg_selected_metrics"][ck].append(metric)
                elif not val and currently_in:
                    st.session_state["rg_selected_metrics"][ck].remove(metric)


# ==========================================
# 5. MAIN RENDER FUNCTION
# ==========================================
def render_reports():
    """
    Main entry point for the Reports Generator page.

    Layout:
      1. Header bar     [Reports Generator title  |  Report Type selector]
      2. Config card    [Metrics | Dimensions | Date Range | AI toggle | Reset]
      3. Main area      [Tabs]  +  [Right: Advanced Filters panel]
         Tabs: Summary | Charts | Tables | Full Report
      4. Action bar     single container with:
                        [last updated info | Share via Email | Preview | Generate Report]
      5. Preview panel  shown below action bar when Preview is toggled
    """
    try:
        st.markdown(get_report_css(), unsafe_allow_html=True)
    except:
        pass

    # JavaScript MutationObserver: patches Streamlit's inline-style red colors
    # to earthy theme on every React re-render. Requires Streamlit >= 1.31.
    # Falls back silently on older versions.
    _JS_EARTHY_PATCH = """
<script>
(function patchEarthy() {
    var BROWN       = '#4A3B32',
        BROWN_SOFT  = 'rgba(74,59,50,0.07)',
        GREEN       = '#4A7C59',
        GREY        = '#D9D0CA',
        TAG_BG      = '#EAE5E0',
        TAG_BORDER  = '#C9BFB8';

    function isRed(v) {
        return v && /rgb\(\s*25[0-9],\s*[4-9][0-9],\s*[4-9][0-9]\)|rgb\(\s*255,\s*7[0-9]/.test(v);
    }

    function patch() {
        /* ── Tag pills ── */
        document.querySelectorAll('[data-baseweb="tag"]').forEach(function(el) {
            el.style.setProperty('background-color', TAG_BG,     'important');
            el.style.setProperty('color',            BROWN,      'important');
            el.style.setProperty('border-color',     TAG_BORDER, 'important');
        });

        /* ── Radio: outer ring border + inner dot bg ── */
        document.querySelectorAll('[data-baseweb="radio"]').forEach(function(radio) {
            /* Remove any selection highlight on the label row */
            var label = radio.querySelector('label');
            if (label) label.style.setProperty('background-color', 'transparent', 'important');

            radio.querySelectorAll('div').forEach(function(d) {
                var s = d.style;
                if (isRed(s.backgroundColor)) s.setProperty('background-color', BROWN, 'important');
                if (isRed(s.borderColor))     s.setProperty('border-color',     BROWN, 'important');
            });
        });

        /* ── Remove brown bg from toggle - entire container + stWidgetLabel wrapper ── */
        document.querySelectorAll('[data-testid="stToggle"]').forEach(function(toggle) {
            toggle.style.setProperty('background-color', 'transparent', 'important');
            toggle.style.setProperty('background', 'transparent', 'important');
            
            // Target the stWidgetLabel parent wrapper specifically
            var labelWrapper = toggle.querySelector('[data-testid="stWidgetLabel"]');
            if (labelWrapper && labelWrapper.parentElement) {
                labelWrapper.parentElement.style.setProperty('background-color', 'transparent', 'important');
                labelWrapper.parentElement.style.setProperty('background', 'transparent', 'important');
            }
            
            toggle.querySelectorAll('*').forEach(function(el) {
                if (el.getAttribute('role') === 'switch') return;
                el.style.setProperty('background-color', 'transparent', 'important');
                el.style.setProperty('background', 'transparent', 'important');
            });
        });

        /* ── Remove brown bg from stRadio wrapper rows ── */
        document.querySelectorAll('[data-testid="stRadio"] > div > div > div').forEach(function(el) {
            el.style.setProperty('background-color', 'transparent', 'important');
        });

        /* ── Tab highlight bar ── */
        document.querySelectorAll('[data-baseweb="tab-highlight"]').forEach(function(el) {
            el.style.setProperty('background-color', BROWN, 'important');
        });

        /* ── Checkbox fill ── */
        document.querySelectorAll('[data-testid="stCheckbox"] div').forEach(function(d) {
            if (isRed(d.style.backgroundColor)) d.style.setProperty('background-color', BROWN, 'important');
            if (isRed(d.style.borderColor))     d.style.setProperty('border-color',     BROWN, 'important');
        });
    }

    /* Run immediately + on every DOM/attribute mutation */
    patch();
    new MutationObserver(patch).observe(document.body, {
        childList: true, subtree: true,
        attributes: true,
        attributeFilter: ['style', 'aria-checked', 'aria-selected', 'aria-pressed']
    });
})();
</script>
"""
    try:
        st.html(_JS_EARTHY_PATCH)
    except AttributeError:
        pass  # st.html() requires Streamlit >= 1.31
    _init_state()

    # =========================================================
    # 1. HEADER BAR
    # =========================================================
    with st.container(key="rg_header"):
        h_left, h_right = st.columns([2, 1])
        with h_left:
            st.markdown(
                f"<h2 style='color:#111827;font-size:20px;"
                f"font-weight:700;margin:0'>Reports Generator</h2>",
                unsafe_allow_html=True,
            )
        with h_right:
            st.selectbox(
                "Report Type",
                ["Revenue Report", "Fraud & Risk Report", "Settlement Report",
                 "Customer Report", "Executive Summary", "Compliance Report"],
                key="rg_report_type",
            )

    report_type = st.session_state.get("rg_report_type", "Revenue Report")

    # =========================================================
    # 2. CONFIGURATION CARD
    # =========================================================
    with st.container(key="rg_config_card", border=True):
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])

        with c1:
            st.multiselect(
                "Select Metrics",
                ["Transaction Volume", "Transaction Value", "Success Rate",
                 "Failure Rate", "Fraud Rate", "Pending Rate",
                 "Avg Transaction Value", "Peak Hour Volume"],
                default=["Transaction Volume", "Transaction Value", "Success Rate"],
                key="rg_metrics_select",
            )
        with c2:
            st.multiselect(
                "Select Dimensions",
                ["Transaction Type", "Sender State", "Device Type", "Network Type",
                 "Sender Bank", "Sender Age Group", "Merchant Category"],
                default=["Transaction Type", "Sender State"],
                key="rg_dimensions_select",
            )
        with c3:
            date_range = st.date_input(
                "Date Range",
                value=(datetime.now() - timedelta(days=30), datetime.now()),
                key="rg_date_range",
            )
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                start_date, end_date = date_range
            else:
                start_date = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
                end_date   = datetime.now().date()
        with c4:
            st.markdown("<p style='font-weight:600;font-size:0.9rem;margin-bottom:0px;'>AI Insights?</p>", unsafe_allow_html=True)
            st.radio(
                "AI Insights",
                ["Yes", "No"],
                horizontal=True,
                label_visibility="collapsed",
                key="rg_ai_insights",
            )
        with c5:
            st.write("")
            if st.button("Reset Filters", key="rg_reset"):
                # Delete all widget keys so they revert to defaults on rerun
                _keys_to_reset = [
                    "rg_report_type", "rg_metrics_select", "rg_dimensions_select",
                    "rg_date_range", "rg_ai_insights", "rg_region_filter",
                    "rg_platform_filter", "rg_ai_insight_depth", "rg_ai_custom_query",
                    "rg_output_format", "rg_trend_granularity", "rg_selected_metrics",
                    "rg_preview_open",
                ]
                for _k in _keys_to_reset:
                    st.session_state.pop(_k, None)
                st.rerun()

    filters = _build_filters(start_date, end_date)

    # Pre-fetch shared data
    if data_service:
        kpi_resp    = data_service.get_kpi_summary(filters)
        kpi_data    = kpi_resp.get("data", []) if kpi_resp.get("status") == "success" else []
        ai_resp     = data_service.get_ai_insights(report_type, filters)
        ai_insights = ai_resp.get("data", {})
    else:
        kpi_data    = []
        ai_insights = {}

    # =========================================================
    # 3. MAIN CONTENT + RIGHT FILTERS
    # =========================================================
    main_col, right_col = st.columns([3, 1], gap="medium")

    with main_col:
        with st.container(key="rg_tabs_area"):
            tab_sum, tab_charts, tab_tables, tab_full = st.tabs(
                ["Summary", "Charts", "Tables", "Full Report"]
            )
            with tab_sum:
                _render_summary_tab(data_service, filters)
            with tab_charts:
                _render_charts_tab(data_service, filters)
            with tab_tables:
                _render_tables_tab(data_service, filters)
            with tab_full:
                _render_full_report_tab(data_service, filters, start_date, end_date)

    with right_col:
        with st.container(key="rg_right_panel", border=True):
            st.markdown(
                f"<p style='font-size:13px;font-weight:700;"
                f"color:#111827;margin:0 0 8px'>Advanced Filters</p>",
                unsafe_allow_html=True,
            )

            # Sender State Filter
            st.markdown("<p class='report-section-label'>Sender State</p>",
                        unsafe_allow_html=True)
            st.radio(
                "Sender State",
                [
                    "All States",
                    "Maharashtra",
                    "Karnataka",
                    "Delhi",
                    "Tamil Nadu",
                    "Gujarat",
                    "Uttar Pradesh",
                    "West Bengal",
                    "Rajasthan",
                    "Telangana",
                    "Kerala",
                ],
                label_visibility="collapsed",
                key="rg_region_filter",
            )

            # Device Type
            st.markdown("<p class='report-section-label'>Device Type</p>",
                        unsafe_allow_html=True)
            try:
                st.segmented_control(
                    "Device Type",
                    options=["All", "Android", "iOS", "Web"],
                    label_visibility="collapsed",
                    key="rg_platform_filter",
                )
            except AttributeError:
                st.radio("Device Type", ["All", "Android", "iOS", "Web"],
                         horizontal=True, label_visibility="collapsed",
                         key="rg_platform_filter")

            # AI Insight Depth
            st.markdown("<p class='report-section-label'>AI Insight Depth</p>",
                        unsafe_allow_html=True)
            try:
                st.segmented_control(
                    "AI Depth",
                    options=["Summary", "Detailed", "Executive"],
                    label_visibility="collapsed",
                    key="rg_ai_insight_depth",
                )
            except AttributeError:
                st.radio("AI Depth", ["Summary", "Detailed", "Executive"],
                         horizontal=True, label_visibility="collapsed",
                         key="rg_ai_insight_depth")

            # AI Custom Query  — text field passed directly to the backend
            st.markdown("<p class='report-section-label'>AI Query (optional)</p>",
                        unsafe_allow_html=True)
            st.text_area(
                "AI custom query",
                placeholder="e.g. Focus on fraud trends in North America…",
                label_visibility="collapsed",
                height=72,
                key="rg_ai_custom_query",
            )

            # Output Format
            st.markdown("<p class='report-section-label'>Output Format</p>",
                        unsafe_allow_html=True)
            st.selectbox(
                "Format",
                ["PDF Document (.pdf)", "Excel (.xlsx)", "CSV (.csv)"],
                label_visibility="collapsed",
                key="rg_output_format",
            )

            st.caption("Estimated generation time: ~15 seconds")
            st.divider()

            _render_category_selector()

    # =========================================================
    # 4. ACTION BAR  — single container for all three actions
    # =========================================================
    with st.container(key="rg_action_bar", border=True):
        all_flat = _get_all_selected_flat()
        output_format = st.session_state.get("rg_output_format", "PDF Document (.pdf)")

        info_col, btns_col = st.columns([2, 3])

        with info_col:
            st.caption(
                f"Last updated: just now   |   **{len(all_flat)}** metrics selected"
            )

        with btns_col:
            b_email, b_preview, b_generate = st.columns(3)

            # Share via Email
            with b_email:
                with st.popover("Share via Email", use_container_width=True):
                    email_input = st.text_input(
                        "Recipient email",
                        placeholder="email@company.com",
                        label_visibility="collapsed",
                        key="rg_email_input",
                    )
                    if st.button("Send Report", key="rg_email_send",
                                 use_container_width=True):
                        if re.match(r"^[^@]+@[^@]+\.[^@]+$", email_input or ""):
                            st.session_state["rg_email_log"].append({
                                "email":        email_input,
                                "timestamp":    datetime.now().isoformat(),
                                "metric_count": len(all_flat),
                            })
                            st.toast(f"Report queued for {email_input}")
                        else:
                            st.error("Enter a valid email address")

            # Preview toggle
            with b_preview:
                if st.button("Preview", use_container_width=True, key="rg_preview_btn"):
                    st.session_state["rg_preview_open"] = \
                        not st.session_state.get("rg_preview_open", False)

            # Generate / Download  (adapts to selected format)
            with b_generate:
                if "Excel" in output_format:
                    excel_bytes = _generate_excel(data_service, filters, kpi_data)
                    st.download_button(
                        "Generate Report",
                        data=excel_bytes,
                        file_name=(f"primeanalyst_"
                                   f"{report_type.lower().replace(' ','_')}"
                                   f"_{start_date}.xlsx"),
                        mime=("application/vnd.openxmlformats-officedocument"
                              ".spreadsheetml.sheet"),
                        key="rg_dl_excel",
                        use_container_width=True,
                    )
                elif "CSV" in output_format:
                    csv_bytes = _generate_csv(data_service, filters, kpi_data)
                    st.download_button(
                        "Generate Report",
                        data=csv_bytes,
                        file_name=(f"primeanalyst_"
                                   f"{report_type.lower().replace(' ','_')}"
                                   f"_{start_date}.csv"),
                        mime="text/csv",
                        key="rg_dl_csv",
                        use_container_width=True,
                    )
                else:  # PDF
                    pdf_bytes = _generate_pdf(data_service, filters, kpi_data, ai_insights)
                    ext  = "pdf" if _reportlab_ok() else "txt"
                    mime = "application/pdf" if _reportlab_ok() else "text/plain"
                    st.download_button(
                        "Generate Report",
                        data=pdf_bytes,
                        file_name=(f"primeanalyst_"
                                   f"{report_type.lower().replace(' ','_')}"
                                   f"_{start_date}.{ext}"),
                        mime=mime,
                        key="rg_dl_pdf",
                        use_container_width=True,
                    )

    # =========================================================
    # 5. PREVIEW PANEL  (below action bar, toggled by button)
    # =========================================================
    if st.session_state.get("rg_preview_open", False):
        _render_preview(data_service, filters, kpi_data, ai_insights, start_date, end_date)


# Standalone execution for testing
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Prime Analyst Reports")
    render_reports()