# pip install reportlab   (for PDF export)

# ============================================================
# HOW TO RUN & TEST THIS FILE
# ============================================================
# 1. Install deps:  pip install streamlit plotly pandas numpy reportlab
# 2. Standalone test:
#       streamlit run reports.py
#    This works because __main__ block calls st.set_page_config + render_reports()
#
# 3. Integration test — in your main app.py:
#       from components.reports import render_reports
#       if page == "reports": render_reports()
# ============================================================

"""
Reports Component for PayInsight AI
Redesigned UI matching analysis page design language
Real PDF export with reportlab
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import re
import io
from datetime import datetime, timedelta
from components.styles import get_report_css


# ============================================================
# STATE INITIALIZATION
# ============================================================
def _init_reports_state():
    """Initialize session state for reports"""
    if 'selected_metrics' not in st.session_state:
        st.session_state.selected_metrics = {}
    if 'email_log' not in st.session_state:
        st.session_state.email_log = []


# ============================================================
# METRIC CATEGORIES (Import from registry with fallback)
# ============================================================
try:
    from metric_registry import METRIC_CATEGORIES
except ImportError:
    # Fallback if metric_registry.py is not available
    METRIC_CATEGORIES = {
        "Transaction Overview": {
            "icon_color": "#DBEAFE",
            "metrics": [
                "Total transaction volume",
                "Transaction success rate",
                "Average transaction value",
                "Peak transaction hours",
                "Transaction velocity (TPM)",
                "Failed transactions",
                "Transaction growth rate"
            ]
        },
        "Revenue & Finance": {
            "icon_color": "#D1FAE5",
            "metrics": [
                "Gross transaction revenue",
                "Net revenue after fees",
                "Average revenue per user (ARPU)",
                "Revenue by payment method",
                "Monthly recurring revenue (MRR)",
                "Payment gateway fees"
            ]
        },
        "Fraud & Risk": {
            "icon_color": "#FEE2E2",
            "metrics": [
                "Fraud detection rate",
                "Chargeback ratio",
                "False positive rate",
                "High-risk transaction count",
                "Blocked transaction count",
                "Fraud loss amount"
            ]
        },
        "Authorization": {
            "icon_color": "#FEF3C7",
            "metrics": [
                "Authorization success rate",
                "Authorization decline rate",
                "3DS authentication rate",
                "Issuer decline breakdown",
                "Soft decline recovery rate"
            ]
        },
        "Settlement": {
            "icon_color": "#E0E7FF",
            "metrics": [
                "Settlement speed (avg days)",
                "Settlement failure rate",
                "Pending settlement volume",
                "Reconciliation accuracy",
                "Cross-border settlement time"
            ]
        },
        "Customer & Merchant": {
            "icon_color": "#FCE7F3",
            "metrics": [
                "Active customer count",
                "New customer acquisition",
                "Customer lifetime value (CLV)",
                "Merchant onboarding rate",
                "Customer satisfaction score (CSAT)",
                "Payment method preference distribution"
            ]
        }
    }


# ============================================================
# CSS STYLES
# ============================================================


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _reportlab_available() -> bool:
    """Check if reportlab is installed"""
    try:
        import reportlab
        return True
    except ImportError:
        return False


def _generate_mock_metric_data(metric_name: str, seed: int = 42):
    """Generate mock data for a metric based on its name"""
    np.random.seed(abs(hash(metric_name)) % 10000 + seed)
    
    metric_lower = metric_name.lower()
    
    # Determine chart type based on metric name
    if "rate" in metric_lower or "%" in metric_lower or "ratio" in metric_lower:
        # Donut chart
        value = int(np.random.uniform(65, 98))
        delta = f"+{np.random.randint(1, 8)}%"
        positive = True
        return {
            "type": "donut",
            "value": value,
            "delta": delta,
            "positive": positive
        }
    
    elif "revenue" in metric_lower or "value" in metric_lower or "arpu" in metric_lower or "clv" in metric_lower:
        # Line chart
        days = 7
        base = np.random.uniform(50000, 150000)
        trend = np.random.uniform(-5000, 15000)
        values = [int(base + trend * i + np.random.normal(0, 5000)) for i in range(days)]
        labels = [f"Day {i+1}" for i in range(days)]
        delta = f"+{abs(values[-1] - values[0]):,.0f}"
        positive = values[-1] > values[0]
        return {
            "type": "line",
            "values": values,
            "labels": labels,
            "delta": delta,
            "positive": positive
        }
    
    elif "count" in metric_lower or "volume" in metric_lower or "users" in metric_lower:
        # Bar chart
        categories = 5
        values = [int(np.random.uniform(1000, 50000)) for _ in range(categories)]
        labels = [f"Cat {i+1}" for i in range(categories)]
        delta = f"+{np.random.randint(100, 5000):,}"
        positive = True
        return {
            "type": "bar",
            "values": values,
            "labels": labels,
            "delta": delta,
            "positive": positive
        }
    
    else:
        # KPI card
        if "speed" in metric_lower or "time" in metric_lower or "days" in metric_lower:
            value = f"{np.random.uniform(0.5, 3.5):.1f} days"
        elif "$" in metric_lower or "amount" in metric_lower:
            value = f"${np.random.randint(10000, 500000):,}"
        else:
            value = f"{np.random.randint(1000, 99999):,}"
        
        delta_val = np.random.randint(5, 25)
        positive = np.random.choice([True, False], p=[0.6, 0.4])
        delta = f"+{delta_val}%" if positive else f"-{delta_val}%"
        
        return {
            "type": "kpi",
            "value": value,
            "delta": delta,
            "positive": positive
        }


def render_metric_widget(metric_name: str, data: dict, height: int = 200):
    """Render a single metric widget (shared between analytics and reports)"""
    chart_type = data["type"]
    
    if chart_type == "kpi":
        delta_class = "positive" if data["positive"] else "negative"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{metric_name}</div>
            <div class="kpi-value">{data['value']}</div>
            <span class="kpi-delta {delta_class}">{data['delta']}</span>
        </div>
        """, unsafe_allow_html=True)
    
    elif chart_type == "donut":
        remaining = max(0, 100 - data["value"])
        fig = go.Figure(go.Pie(
            values=[data["value"], remaining],
            labels=[metric_name, ""],
            hole=0.65,
            marker_colors=["#2563EB", "#E8E6E1"],
            textinfo="none",
            hoverinfo="skip",
            showlegend=False
        ))
        fig.add_annotation(
            text=f"{data['value']}%",
            x=0.5, y=0.5,
            font=dict(size=18, color="#1A1614"),
            showarrow=False
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=height,
            title=dict(text=metric_name, font=dict(size=12, color="#6B6560"))
        )
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
    
    elif chart_type == "line":
        fig = go.Figure(go.Scatter(
            x=data["labels"],
            y=data["values"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="#2563EB", width=2),
            fillcolor="rgba(37,99,235,0.08)"
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=height,
            title=dict(text=metric_name, font=dict(size=12, color="#6B6560")),
            xaxis=dict(showgrid=False, showline=False),
            yaxis=dict(showgrid=True, gridcolor="#F0EEE9", showline=False),
            font=dict(family="'DM Sans', 'Segoe UI', sans-serif")
        )
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
    
    elif chart_type == "bar":
        fig = go.Figure(go.Bar(
            x=data["labels"],
            y=data["values"],
            marker_color="#2563EB",
            marker_opacity=0.8
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=height,
            title=dict(text=metric_name, font=dict(size=12, color="#6B6560")),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#F0EEE9"),
            font=dict(family="'DM Sans', 'Segoe UI', sans-serif")
        )
        st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})


def _generate_pdf(selected_metrics: dict, start_date, end_date, 
                  report_type: str, granularity: str) -> bytes:
    """Generate PDF report using reportlab"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, 
                                         Table, TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=20*mm, leftMargin=20*mm,
            topMargin=20*mm, bottomMargin=20*mm
        )
        
        # Color definitions
        COLOR_DARK    = HexColor("#1A1614")
        COLOR_MUTED   = HexColor("#6B6560")
        COLOR_BLUE    = HexColor("#2563EB")
        COLOR_BORDER  = HexColor("#E8E6E1")
        COLOR_BG      = HexColor("#F2F1EF")
        COLOR_GREEN   = HexColor("#10B981")
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle("Title", parent=styles["Normal"],
            fontSize=22, fontName="Helvetica-Bold", textColor=COLOR_DARK,
            spaceAfter=4)
        subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"],
            fontSize=10, fontName="Helvetica", textColor=COLOR_MUTED,
            spaceAfter=16)
        section_style = ParagraphStyle("Section", parent=styles["Normal"],
            fontSize=8, fontName="Helvetica-Bold", textColor=COLOR_MUTED,
            spaceBefore=16, spaceAfter=8)
        metric_name_style = ParagraphStyle("MetricName", parent=styles["Normal"],
            fontSize=10, fontName="Helvetica", textColor=COLOR_MUTED,
            spaceAfter=2)
        metric_value_style = ParagraphStyle("MetricValue", parent=styles["Normal"],
            fontSize=18, fontName="Helvetica-Bold", textColor=COLOR_DARK,
            spaceAfter=4)
        
        story = []
        
        # ── HEADER ──
        story.append(Paragraph("PayInsight AI", title_style))
        story.append(Paragraph(
            f"{report_type} Report · {start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')} · {granularity}",
            subtitle_style
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=COLOR_BORDER, spaceAfter=12))
        
        # ── SUMMARY ROW ──
        total_metrics = sum(len(v) for v in selected_metrics.values())
        summary_data = [
            ["TOTAL METRICS", "DATE RANGE", "REPORT TYPE", "GRANULARITY"],
            [str(total_metrics),
             f"{start_date.strftime('%b %d')} – {end_date.strftime('%b %d, %Y')}",
             report_type,
             granularity]
        ]
        summary_table = Table(summary_data, colWidths=["25%","35%","20%","20%"])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), COLOR_BG),
            ("TEXTCOLOR",    (0,0), (-1,0), COLOR_MUTED),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,0), 7),
            ("FONTNAME",     (0,1), (-1,1), "Helvetica-Bold"),
            ("FONTSIZE",     (0,1), (-1,1), 14),
            ("TEXTCOLOR",    (0,1), (-1,1), COLOR_DARK),
            ("TEXTCOLOR",    (0,1), (0,1),  COLOR_BLUE),
            ("ALIGN",        (0,0), (-1,-1), "CENTER"),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("ROWBACKGROUNDS",(0,0),(-1,-1),[COLOR_BG, HexColor("#FFFFFF")]),
            ("BOX",          (0,0), (-1,-1), 0.5, COLOR_BORDER),
            ("INNERGRID",    (0,0), (-1,-1), 0.5, COLOR_BORDER),
            ("TOPPADDING",   (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 16))
        
        # ── METRICS BY CATEGORY ──
        for category, metrics_list in selected_metrics.items():
            if not metrics_list:
                continue
            
            # Category heading
            category_display = category.replace("_", " ").title().replace("And", "&")
            story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=8))
            story.append(Paragraph(category_display.upper(), section_style))
            
            # Metrics table
            table_data = [["METRIC", "VALUE", "DELTA", "TREND"]]
            
            for metric in metrics_list:
                mock_data = _generate_mock_metric_data(metric)
                if mock_data["type"] == "kpi":
                    value = mock_data["value"]
                    delta = mock_data["delta"]
                    trend = "↑" if mock_data["positive"] else "↓"
                elif mock_data["type"] == "donut":
                    value = f"{mock_data['value']}%"
                    delta = mock_data["delta"]
                    trend = "↑" if mock_data["positive"] else "↓"
                else:
                    vals = mock_data.get("values", [0])
                    value = f"{vals[-1]:,}" if vals else "—"
                    delta = f"+{abs(vals[-1] - vals[0]):,}" if len(vals) > 1 else "—"
                    trend = "↑" if len(vals) > 1 and vals[-1] > vals[0] else "↓"
                
                table_data.append([metric, value, delta, trend])
            
            metrics_table = Table(table_data, colWidths=["45%", "20%", "20%", "15%"])
            
            # Row styles
            row_styles = [
                ("BACKGROUND",   (0,0),  (-1,0),  COLOR_BG),
                ("TEXTCOLOR",    (0,0),  (-1,0),  COLOR_MUTED),
                ("FONTNAME",     (0,0),  (-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",     (0,0),  (-1,0),  7),
                ("FONTNAME",     (0,1),  (-1,-1), "Helvetica"),
                ("FONTSIZE",     (0,1),  (-1,-1), 10),
                ("TEXTCOLOR",    (0,1),  (-1,-1), COLOR_DARK),
                ("TEXTCOLOR",    (1,1),  (1,-1),  COLOR_BLUE),
                ("ALIGN",        (1,0),  (-1,-1), "CENTER"),
                ("ALIGN",        (0,0),  (0,-1),  "LEFT"),
                ("VALIGN",       (0,0),  (-1,-1), "MIDDLE"),
                ("BOX",          (0,0),  (-1,-1), 0.5, COLOR_BORDER),
                ("INNERGRID",    (0,0),  (-1,-1), 0.5, COLOR_BORDER),
                ("TOPPADDING",   (0,0),  (-1,-1), 7),
                ("BOTTOMPADDING",(0,0),  (-1,-1), 7),
                ("LEFTPADDING",  (0,0),  (-1,-1), 8),
            ]
            
            # Alternating rows
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    row_styles.append(("BACKGROUND", (0,i), (-1,i), COLOR_BG))
            
            # Color trend arrows
            for i in range(1, len(table_data)):
                trend_val = table_data[i][3]
                if trend_val == "↑":
                    row_styles.append(("TEXTCOLOR", (3,i), (3,i), COLOR_GREEN))
                else:
                    row_styles.append(("TEXTCOLOR", (3,i), (3,i), HexColor("#EF4444")))
            
            metrics_table.setStyle(TableStyle(row_styles))
            story.append(metrics_table)
            story.append(Spacer(1, 8))
        
        # ── FOOTER ──
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=8))
        story.append(Paragraph(
            f"Generated by PayInsight AI · {datetime.now().strftime('%B %d, %Y at %H:%M')} · Confidential",
            ParagraphStyle("Footer", parent=styles["Normal"],
                fontSize=8, fontName="Helvetica", textColor=COLOR_MUTED,
                alignment=TA_CENTER)
        ))
        
        doc.build(story)
        buffer.seek(0)
        return buffer.read()
    
    except ImportError:
        # Fallback: return a plain text report as bytes
        lines = [
            "PAYINSIGHT AI — REPORT",
            f"{report_type} · {start_date} to {end_date} · {granularity}",
            "=" * 60,
            ""
        ]
        for category, metrics_list in selected_metrics.items():
            if not metrics_list:
                continue
            lines.append(category.replace("_", " ").upper())
            lines.append("-" * 40)
            for metric in metrics_list:
                lines.append(f"  {metric}: (mock data — install reportlab for formatted PDF)")
            lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(lines).encode("utf-8")


# ============================================================
# MAIN RENDER FUNCTION
# ============================================================
def render_reports():
    """
    Main render function for redesigned reports page
    Matches analysis page design language
    """
    
    # Apply CSS
    st.markdown(get_report_css(), unsafe_allow_html=True)
    
    # Initialize state
    _init_reports_state()
    
    # Two-column layout: config (1) and preview (2)
    col_config, col_preview = st.columns([1, 2], gap="large")
    
    # ===== LEFT COLUMN: CONFIG PANEL =====
    with col_config:
        st.markdown('<div class="report-config-card">', unsafe_allow_html=True)
        
        # 1. Panel header
        st.markdown("""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
            <span style="font-size:14px;color:#6B6560;">⚙</span>
            <span style="font-size:10px;font-weight:700;letter-spacing:2px;
                         text-transform:uppercase;color:#6B6560;">Report Configuration</span>
        </div>
        <div style="height:1px;background:#E8E6E1;margin-bottom:16px;"></div>
        """, unsafe_allow_html=True)
        
        # 2. Selected metrics count
        all_selected_flat = []
        for v in st.session_state.selected_metrics.values():
            all_selected_flat.extend(v)
        st.metric("Selected Metrics", len(all_selected_flat))
        
        # 3. Date range
        st.markdown('<span class="report-section-label">Date Range</span>', unsafe_allow_html=True)
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("From", value=datetime.now()-timedelta(days=30),
                                        label_visibility="collapsed", key="report_start_date")
        with col_d2:
            end_date = st.date_input("To", value=datetime.now(),
                                      label_visibility="collapsed", key="report_end_date")
        
        # 4. Report type (segmented control via radio)
        st.markdown('<span class="report-section-label">Report Type</span>', unsafe_allow_html=True)
        report_type = st.radio("Report Type", ["Summary", "Detailed", "Executive"],
                               horizontal=True, label_visibility="collapsed",
                               key="report_type_radio")
        
        # 5. Granularity
        st.markdown('<span class="report-section-label">Granularity</span>', unsafe_allow_html=True)
        granularity = st.radio("Granularity", ["Daily", "Weekly", "Monthly"],
                               horizontal=True, label_visibility="collapsed",
                               key="report_granularity_radio")
        
        # 6. Metric selectors
        st.markdown('<span class="report-section-label">Select Metrics</span>', unsafe_allow_html=True)
        
        for category_name, category_data in METRIC_CATEGORIES.items():
            # Extract metrics list (handle both dict and list formats)
            if isinstance(category_data, dict) and "metrics" in category_data:
                metrics = category_data["metrics"]
            elif isinstance(category_data, list):
                metrics = category_data
            else:
                metrics = []
            
            category_key = category_name.lower().replace(" ", "_").replace("&", "and")
            if category_key not in st.session_state.selected_metrics:
                st.session_state.selected_metrics[category_key] = []
            
            selected_count = len(st.session_state.selected_metrics[category_key])
            
            with st.expander(f"**{category_name}**  {selected_count}/{len(metrics)}", expanded=False):
                # Select All
                all_checked = len(st.session_state.selected_metrics[category_key]) == len(metrics)
                select_all_key = f"report_selectall_{category_key}"
                
                if st.checkbox(f"Select all ({len(metrics)})", value=all_checked,
                               key=select_all_key):
                    st.session_state.selected_metrics[category_key] = metrics.copy()
                else:
                    if all_checked:
                        st.session_state.selected_metrics[category_key] = []
                
                st.markdown('<div style="height:1px;background:#F0EEE9;margin:6px 0 8px;"></div>',
                            unsafe_allow_html=True)
                
                # Individual metrics
                for i, metric in enumerate(metrics):
                    is_selected = metric in st.session_state.selected_metrics[category_key]
                    checked = st.checkbox(metric, value=is_selected,
                                          key=f"report_{category_key}_m{i}")
                    if checked and metric not in st.session_state.selected_metrics[category_key]:
                        st.session_state.selected_metrics[category_key].append(metric)
                    elif not checked and metric in st.session_state.selected_metrics[category_key]:
                        st.session_state.selected_metrics[category_key].remove(metric)
        
        # 7. Clear All
        st.markdown('<div class="report-clear-btn">', unsafe_allow_html=True)
        if st.button("✕  Clear All", key="report_clear_all", width='stretch'):
            st.session_state.selected_metrics = {}
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)  # close config card
    
    # ===== RIGHT COLUMN: PREVIEW PANEL =====
    with col_preview:
        st.markdown('<div class="report-preview-card">', unsafe_allow_html=True)
        
        # Preview header
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;
                    padding-bottom:14px;border-bottom:1px solid #E8E6E1;margin-bottom:16px;">
            <div>
                <div class="preview-report-title">{report_type} Report Preview</div>
                <div class="preview-report-dates">
                    {start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}
                </div>
            </div>
            <div class="live-badge">
                <div class="live-dot"></div>
                LIVE
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Recalculate selected metrics
        all_selected_flat = []
        for v in st.session_state.selected_metrics.values():
            all_selected_flat.extend(v)
        
        if not all_selected_flat:
            # Empty state
            st.markdown("""
            <div class="preview-empty-state">
                <div class="preview-empty-icon">🗋</div>
                <div class="preview-empty-text">
                    Select metrics from the left panel to preview your report
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Render metrics by category
            chart_count = 0
            MAX_PREVIEW_CHARTS = 6
            
            for category_name, category_data in METRIC_CATEGORIES.items():
                category_key = category_name.lower().replace(" ", "_").replace("&", "and")
                selected_in_cat = st.session_state.selected_metrics.get(category_key, [])
                
                if not selected_in_cat:
                    continue
                
                st.markdown(f'<div class="preview-section-header">{category_name}</div>',
                            unsafe_allow_html=True)
                
                col_a, col_b = st.columns(2)
                cols = [col_a, col_b]
                
                for i, metric in enumerate(selected_in_cat):
                    if chart_count >= MAX_PREVIEW_CHARTS:
                        remaining = len(all_selected_flat) - MAX_PREVIEW_CHARTS
                        st.markdown(
                            f'<div style="color:#9CA3AF;font-size:12px;font-style:italic;'
                            f'padding:8px 0;">+ {remaining} more metrics in full export</div>',
                            unsafe_allow_html=True
                        )
                        break
                    
                    mock_data = _generate_mock_metric_data(metric)
                    with cols[i % 2]:
                        render_metric_widget(metric, mock_data, height=180)
                    chart_count += 1
                
                if chart_count >= MAX_PREVIEW_CHARTS:
                    break
            
            # Export bar
            st.markdown(f"""
            <div class="export-action-bar">
                <div class="export-bar-info">
                    <strong>{len(all_selected_flat)}</strong> metrics · {report_type} · {granularity}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
            
            with btn_col1:
                st.markdown('<div class="export-btn-dark">', unsafe_allow_html=True)
                pdf_bytes = _generate_pdf(st.session_state.selected_metrics,
                                          start_date, end_date, report_type, granularity)
                ext = "pdf" if _reportlab_available() else "txt"
                mime = "application/pdf" if _reportlab_available() else "text/plain"
                st.download_button("⬇ PDF", data=pdf_bytes,
                                   file_name=f"payinsight_{report_type.lower()}_{start_date}.{ext}",
                                   mime=mime, key="report_export_pdf",
                                   width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)
                
                if not _reportlab_available():
                    st.caption("💡 Install reportlab for PDF: `pip install reportlab`")
            
            with btn_col2:
                st.markdown('<div class="export-btn-outline">', unsafe_allow_html=True)
                st.button("⬇ Excel", key="report_export_excel", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)
            
            with btn_col3:
                st.markdown('<div class="export-btn-outline">', unsafe_allow_html=True)
                with st.popover("✉ Email", width='stretch'):
                    email = st.text_input("Send to", placeholder="email@company.com",
                                          key="report_email_input")
                    if st.button("Send", key="report_email_send"):
                        import re
                        if re.match(r'^[^@]+@[^@]+\.[^@]+$', email or ""):
                            st.session_state.email_log.append({
                                "email": email,
                                "timestamp": datetime.now().isoformat(),
                                "metric_count": len(all_selected_flat)
                            })
                            st.toast(f"Report queued for {email} ✓", icon="✉️")
                        else:
                            st.error("Enter a valid email")
                st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)  # close preview card


# ============================================================
# STANDALONE TESTING
# ============================================================
if __name__ == "__main__":
    st.set_page_config(
        page_title="PayInsight AI - Reports",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    render_reports()
