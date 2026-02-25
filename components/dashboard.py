"""
Dashboard Component for Prime Analyst
High-end analytics dashboard with earthy professional theme.
Features:
- Dynamic data loading
- PDF Export with Charts
- Unified Layout
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import tempfile
import os
from components.styles import get_dashboard_css

# Try importing PDF libraries
try:
    from fpdf import FPDF
    HAS_PDF_LIBS = True
except ImportError:
    HAS_PDF_LIBS = False
    # Create a dummy base class so PDFReport definition doesn't crash at import
    class FPDF:
        pass

# ==========================================
# CONFIG & STYLE CONSTANTS
# ==========================================

# Earthy Color Palette
COLORS = {
    "primary":   "#4A3B32",
    "secondary": "#6B5F52",
    "accent":    "#2563EB",
    "success":   "#4A7C59",
    "warning":   "#C17F24",
    "danger":    "#B44C3A",
    "upi":       "#C2673A",
    "rupay":     "#5C7A3E",
    "bg":        "#F2F1EF",
    "card":      "#F9F8F6",
}

CHART_COLORS_BROWN = [
    "#4A3B32", "#6B5F52", "#8C7B6E", "#A89890",
    "#B5A99F", "#C9BFB8", "#D9D0CA", "#F2F1EF",
]

FRAUD_HEATMAP_SCALE = [
    "#F2F1EF","#D4B896","#8C7B6E", "#C2673A", "#B44C3A", "#4A3B32",
]

DIVERGING_SCALE = [
    "rgba(180, 76, 58, 1)",
    "rgba(180, 76, 58, 0.4)",
    "rgba(242, 241, 239, 1)",
    "rgba(74, 124, 89, 0.4)",
    "rgba(74, 124, 89, 1)",
]


# ==========================================
# DATA LOADING INTERFACE
# ==========================================

def get_dashboard_data():
    """
    Fetches dashboard data.
    Priority 1: MockData from test_ui.py (for dev/demo)
    Priority 2: Returns empty template structure (for production integration)
    """
    try:
        from test_ui import MockData
        # Use the dynamic generator if available, else static
        if hasattr(MockData, 'get_dashboard_data'):
            return MockData.get_dashboard_data()
        return MockData.DASHBOARD_DATA
    except ImportError:
        # PRODUCTION FALLBACK TEMPLATE
        return {
            "kpis": [],
            "trends": {"dates": [], "volume": [], "success_rate": []},
            "decline_reasons": {},
            "platforms": {},
            "transaction_status": {"dates": [], "approved": [], "declined": []},
            "risk_meter": {"current_score": 0, "max_score": 5, "threshold": 4.5},
            "retention_curve": {"weeks": [], "values": []}
        }

# ==========================================
# CHART FACTORY FUNCTIONS
# ==========================================

def create_trend_chart(data):
    if not data.get("dates"): return go.Figure()
    
    df = pd.DataFrame({
        'Date': pd.to_datetime(data["dates"]),
        'Success Rate': data["success_rate"]
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Success Rate'],
        mode='lines',
        line=dict(color=COLORS["primary"], width=3, shape='spline'),
        fill='tozeroy',
        fillcolor="rgba(180, 76, 58, 0.05)",
        hovertemplate='<b>%{x|%b %d}</b><br>Success: %{y:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text="Authorization Rates Trend", font=dict(size=14, color=COLORS["primary"])),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Arial, sans-serif", size=10, color=COLORS["primary"]),
        margin=dict(l=0, r=0, t=30, b=0),
        height=250,
        xaxis=dict(showgrid=False, showline=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(224, 222, 217, 0.3)', showline=False, range=[90, 100])
    )
    return fig

def create_decline_chart(data):
    if not data: return go.Figure()
    
    labels = list(data.keys())
    values = list(data.values())
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(colors=FRAUD_HEATMAP_SCALE[::-1]),
        textinfo='none', # Hides text on slices
        hovertemplate='<b>%{label}</b><br>%{percent}<extra></extra>'
    )])
    
    # Center text
    fig.add_annotation(
        text=f'<b>{sum(values)}</b><br><span style="font-size:10px">Declines</span>',
        showarrow=False,
        font=dict(size=14, color=COLORS["primary"])
    )
    
    fig.update_layout(
        title=dict(text="Decline Reasons", font=dict(size=14, color=COLORS["primary"])),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=30, b=30),
        height=250,
        showlegend=True,
        legend=dict(
            orientation="h", 
            yanchor="top", 
            y=-0.1, 
            xanchor="center", 
            x=0.5,
            font=dict(size=9)
        )
    )
    return fig

def create_platform_chart(data):
    if not data: return go.Figure()
    
    df = pd.DataFrame({
        'Platform': list(data.keys()),
        'Percentage': list(data.values())
    }).sort_values('Percentage', ascending=True)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df['Platform'],
        x=df['Percentage'],
        orientation='h',
        marker=dict(color=COLORS["primary"]),
        text=df['Percentage'].apply(lambda x: f'{x}%'),
        textposition='auto',
        hovertemplate='%{y}: %{x}%<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text="Revenue by Platform", font=dict(size=14, color=COLORS["primary"])),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS["primary"], size=10),
        margin=dict(l=0, r=0, t=30, b=0),
        height=250,
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False)
    )
    return fig

def create_status_chart(data):
    if not data.get("dates"): return go.Figure()
    
    dates_short = [d[5:] for d in data["dates"]] 
    approved = data["approved"]
    declined = data["declined"]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Approved', x=dates_short, y=approved, marker_color=COLORS["success"]))
    fig.add_trace(go.Bar(name='Declined', x=dates_short, y=declined, marker_color=COLORS["danger"]))
    
    fig.update_layout(
        title=dict(text="Transaction Status", font=dict(size=14, color=COLORS["primary"])),
        barmode='stack',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS["primary"], size=10),
        margin=dict(l=0, r=0, t=30, b=0),
        height=250,
        legend=dict(orientation="h", y=1.0, x=1, xanchor="right", font=dict(size=9)),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(224, 222, 217, 0.3)')
    )
    return fig

def create_risk_chart(data):
    if not data: return go.Figure()
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = data["current_score"],
        # title = {'text': "Fraud Rate %", 'font': {'size': 14, 'color': COLORS["primary"]}},
        gauge = {
            'axis': {'range': [None, data["max_score"]], 'tickwidth': 1, 'tickcolor': COLORS["primary"]},
            'bar': {'color': COLORS["primary"]},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 2], 'color': COLORS["success"]},
                {'range': [2, 4], 'color': COLORS["warning"]},
                {'range': [4, 5], 'color': COLORS["danger"]}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': data["threshold"]}
        }
    ))
    
    fig.update_layout(
        title=dict(text="Fraud Risk Monitor", font=dict(size=14, color=COLORS["primary"])),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS["primary"]),
        margin=dict(l=30, r=30, t=40, b=10),
        height=220
    )
    return fig

def create_retention_chart(data):
    if not data.get("weeks"): return go.Figure()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["weeks"], y=data["values"],
        mode='lines+markers',
        line=dict(color=COLORS["warning"], width=3),
        marker=dict(size=8, color=COLORS["danger"]),
        hovertemplate='%{y}% Retention<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text="User Retention (DAU/MAU)", font=dict(size=14, color=COLORS["primary"])),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=COLORS["primary"], size=10),
        margin=dict(l=0, r=0, t=30, b=0),
        height=220,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(224, 222, 217, 0.3)', range=[0, 50])
    )
    return fig

# ==========================================
# PDF GENERATION
# ==========================================

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(74, 59, 50) # Dark Brown
        self.cell(0, 10, 'Prime Analyst - Payment Performance Report', 0, 1, 'L')
        self.set_font('Arial', '', 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Generated on {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_report(data):
    """
    Generates a PDF report using FPDF and Plotly static image export.
    Returns bytes of the PDF.
    """
    pdf = PDFReport()
    pdf.add_page()
    
    # 1. ADD KPIS SUMMARY
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(74, 59, 50)
    pdf.cell(0, 10, 'Key Performance Indicators', 0, 1, 'L')
    pdf.set_font('Arial', '', 11)
    
    # Simple table-like structure for KPIs
    col_width = pdf.w / 4.5
    for kpi in data["kpis"]:
        pdf.cell(col_width, 8, kpi["label"], 0, 0)
    pdf.ln(8)
    
    pdf.set_font('Arial', 'B', 14)
    for kpi in data["kpis"]:
        pdf.cell(col_width, 10, kpi["value"], 0, 0)
    pdf.ln(12)
    
    # 2. GENERATE AND EMBED CHARTS
    # We create temporary files for the chart images
    charts_to_render = [
        (create_trend_chart(data["trends"]), create_decline_chart(data["decline_reasons"])),
        (create_platform_chart(data["platforms"]), create_status_chart(data["transaction_status"])),
        (create_risk_chart(data["risk_meter"]), create_retention_chart(data["retention_curve"]))
    ]
    
    temp_files = []
    
    try:
        y_pos = pdf.get_y() + 5
        
        for row_charts in charts_to_render:
            # Check for page break
            if y_pos > 200:
                pdf.add_page()
                y_pos = 20
            
            x_pos = 10
            max_h = 0
            
            for fig in row_charts:
                try:
                    # Convert plotly figure to static image (requires kaleido)
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        # Use scale=2 for better resolution
                        fig.write_image(tmp.name, width=500, height=350, scale=2)
                        temp_files.append(tmp.name)
                        
                        # Add to PDF
                        # Width ~90mm per chart
                        pdf.image(tmp.name, x=x_pos, y=y_pos, w=90)
                        x_pos += 95
                except Exception as e:
                    pdf.set_xy(x_pos, y_pos)
                    pdf.set_font('Arial', 'I', 8)
                    pdf.multi_cell(90, 10, f"Chart could not be generated.\n(Error: {str(e)})")
                    x_pos += 95
            
            y_pos += 75 # Move down for next row
            
    finally:
        # Cleanup temp files
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# DASHBOARD RENDERING
# ==========================================

def render_dashboard():
    """
    Renders the Payment Performance dashboard.
    """
    
    # Apply dashboard CSS
    st.markdown(get_dashboard_css(), unsafe_allow_html=True)
    
    # Load Data
    data = get_dashboard_data()
    
    # ===== HEADER SECTION =====
    with st.container():
        st.markdown('<span class="dashboard-header-container"></span>', unsafe_allow_html=True)
        
        # Header Row
        header_col1, header_col2 = st.columns([0.7, 0.3], gap="medium", vertical_alignment="center")
        
        with header_col1:
            st.markdown('<div class="dashboard-header">', unsafe_allow_html=True)
            st.markdown('<h1 class="dashboard-title">Payment Performance</h1>', unsafe_allow_html=True)
            st.markdown(
                '<p class="dashboard-subtitle">Real-time analytics for your payment processing ecosystem.</p>',
                unsafe_allow_html=True
            )
            st.markdown('</div>', unsafe_allow_html=True)
        
        with header_col2:
            c1, c2 = st.columns(2, gap="small")
            
            with c1:
                with st.popover(":material/date_range:", use_container_width=True):
                    st.markdown("**Select Range**")
                    st.radio("Range", ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "This Quarter"], label_visibility="collapsed")
                    st.button("Apply", type="primary", use_container_width=True)
            
            with c2:
                # PDF EXPORT LOGIC
                if HAS_PDF_LIBS:
                    # 2-step process to avoid lag on load
                    if st.button(":material/picture_as_pdf:", use_container_width=True):
                        with st.spinner("Generating PDF Report..."):
                            try:
                                pdf_bytes = generate_pdf_report(data)
                                st.download_button(
                                    label=":material/download:",
                                    data=pdf_bytes,
                                    file_name="PrimeAnalyst_Report.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )
                                st.success("Report ready!")
                            except Exception as e:
                                st.error(f"Export failed: {str(e)}")
                                st.caption("Ensure 'kaleido' and 'fpdf' are installed.")
                else:
                    st.button("Export", disabled=True, help="Install 'fpdf' and 'kaleido' to enable PDF export.", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ===== ROW 1: KPI CARDS =====
        if data.get("kpis"):
            kpi_cols = st.columns(4)
            for idx, kpi in enumerate(data["kpis"]):
                with kpi_cols[idx]:
                    trend_class = "positive-trend" if kpi["trend"] == "up" else "negative-trend"
                    trend_icon = "↑" if kpi["trend"] == "up" else "↓"
                    
                    kpi_html = f"""
                    <div class="dashboard-card">
                        <p class="metric-label">{kpi["label"]}</p>
                        <p class="metric-value">{kpi["value"]}</p>
                        <span class="metric-delta {trend_class}">
                            <span class="trend-icon">{trend_icon}</span>
                            {kpi["delta"]}
                        </span>
                    </div>
                    """
                    st.markdown(kpi_html, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
        
        # ===== UNIFIED CHART BOX (Rows 2, 3, 4) =====
        # Wrapping all charts in ONE styled container as requested
        with st.container():
            st.markdown('<span class="chart-card-container"></span>', unsafe_allow_html=True)
            
            # --- ROW 2: Auth & Decline ---
            r2_c1, r2_c2 = st.columns([2, 1], gap="large")
            with r2_c1:
                st.plotly_chart(create_trend_chart(data["trends"]), use_container_width=True, config={'displayModeBar': False})
            with r2_c2:
                st.plotly_chart(create_decline_chart(data["decline_reasons"]), use_container_width=True, config={'displayModeBar': False})
            
            st.markdown("<br>", unsafe_allow_html=True)

            # --- ROW 3: Revenue & Status ---
            r3_c1, r3_c2 = st.columns(2, gap="large")
            with r3_c1:
                st.plotly_chart(create_platform_chart(data["platforms"]), use_container_width=True, config={'displayModeBar': False})
            with r3_c2:
                st.plotly_chart(create_status_chart(data["transaction_status"]), use_container_width=True, config={'displayModeBar': False})
            
            st.markdown("<br>", unsafe_allow_html=True)

            # --- ROW 4: Risk & Retention ---
            r4_c1, r4_c2 = st.columns([1, 2], gap="large")
            with r4_c1:
                st.plotly_chart(create_risk_chart(data["risk_meter"]), use_container_width=True, config={'displayModeBar': False})
            with r4_c2:
                st.plotly_chart(create_retention_chart(data["retention_curve"]), use_container_width=True, config={'displayModeBar': False})


if __name__ == "__main__":
    st.set_page_config(layout="wide")
    render_dashboard()