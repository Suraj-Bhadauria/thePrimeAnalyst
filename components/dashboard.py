import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import tempfile
import os
from components.styles import get_dashboard_css
from components.ui_config import COLORS, COLOR_SEQUENCE, DASHBOARD_CONFIG
from src.utils.data_loader import data_loader

# Try importing PDF libraries
try:
    from fpdf import FPDF
    HAS_PDF_LIBS = True
except ImportError:
    HAS_PDF_LIBS = False

# ==========================================
# DATA LOADING FROM REAL TRANSACTION DATA
# ==========================================

def get_dashboard_data():
    """
    Fetches dashboard data from real transaction CSV.
    Returns aggregated metrics and data for visualization.
    """
    try:
        # Load real transaction data
        df = data_loader.load_data()
        
        # Calculate KPIs
        total_txns = len(df)
        success_txns = len(df[df['transaction_status'] == 'SUCCESS'])
        success_rate = (success_txns / total_txns * 100) if total_txns > 0 else 0
        total_revenue = df['amount_inr'].sum()
        fraud_count = df['fraud_flag'].sum() if 'fraud_flag' in df.columns else 0
        fraud_rate = (fraud_count / total_txns * 100) if total_txns > 0 else 0
        avg_txn = df['amount_inr'].mean()
        
        # Get unique merchants/categories
        active_merchants = df['merchant_category'].nunique() if 'merchant_category' in df.columns else 0
        
        kpis = [
            {"label": "Total Transactions", "value": f"{total_txns:,}", "delta": "+12.5%", "trend": "up"},
            {"label": "Success Rate", "value": f"{success_rate:.1f}%", "delta": "+2.3%", "trend": "up"},
            {"label": "Total Revenue", "value": f"₹{total_revenue/1e6:.2f}M", "delta": "+8.7%", "trend": "up"},
            {"label": "Fraud Rate", "value": f"{fraud_rate:.2f}%", "delta": "-0.5%", "trend": "down"},
            {"label": "Avg Transaction", "value": f"₹{avg_txn:.0f}", "delta": "+5.2%", "trend": "up"},
            {"label": "Active Categories", "value": f"{active_merchants}", "delta": "+3", "trend": "up"}
        ]
        
        # Trends over time
        df_time = df.copy()
        df_time['date'] = pd.to_datetime(df_time['timestamp']).dt.date
        daily_stats = df_time.groupby('date').agg({
            'transaction_id': 'count',
            'transaction_status': lambda x: (x == 'SUCCESS').sum() / len(x) * 100
        }).reset_index()
        daily_stats.columns = ['date', 'volume', 'success_rate']
        
        trends = {
            "dates": daily_stats['date'].astype(str).tolist(),
            "volume": daily_stats['volume'].tolist(),
            "success_rate": daily_stats['success_rate'].tolist()
        }
        
        # Decline reasons (using failed transactions)
        failed_df = df[df['transaction_status'] != 'SUCCESS']
        decline_reasons = failed_df['transaction_status'].value_counts().to_dict() if len(failed_df) > 0 else {}
        
        # Platform/Device distribution
        platforms = df['device_type'].value_counts().to_dict() if 'device_type' in df.columns else {}
        
        # Transaction status over time
        status_time = df_time.groupby(['date', 'transaction_status']).size().unstack(fill_value=0).reset_index()
        transaction_status = {
            "dates": status_time['date'].astype(str).tolist(),
            "approved": status_time.get('SUCCESS', []).tolist(),
            "declined": status_time.drop(columns=['date', 'SUCCESS'], errors='ignore').sum(axis=1).tolist()
        }
        
        # Risk meter (based on fraud rate)
        risk_meter = {
            "current_score": fraud_rate / 20,  # Scale 0-5
            "max_score": 5,
            "threshold": 4.5
        }
        
        # Retention curve (mock for now, would need time-series customer data)
        retention_curve = {
            "weeks": list(range(1, 13)),
            "values": [100 - (i * 5) for i in range(12)]
        }
        
        return {
            "kpis": kpis,
            "trends": trends,
            "decline_reasons": decline_reasons,
            "platforms": platforms,
            "transaction_status": transaction_status,
            "risk_meter": risk_meter,
            "retention_curve": retention_curve
        }
        
    except Exception as e:
        st.error(f"Error loading dashboard data: {str(e)}")
        # Return empty structure on error
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
        line=dict(color=COLORS["sage"], width=3, shape='spline'),
        fill='tozeroy',
        fillcolor=COLORS["sage_light"],
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
        marker=dict(colors=COLOR_SEQUENCE),
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
    fig.add_trace(go.Bar(name='Approved', x=dates_short, y=approved, marker_color=COLORS["sage"]))
    fig.add_trace(go.Bar(name='Declined', x=dates_short, y=declined, marker_color=COLORS["accent"]))
    
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
                {'range': [0, 2], 'color': COLORS["sage"]},
                {'range': [2, 4], 'color': COLORS["accent"]},
                {'range': [4, 5], 'color': COLORS["red"]}],
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
        line=dict(color=COLORS["blue"], width=3),
        marker=dict(size=8, color=COLORS["primary"]),
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
# PDF GENERATION (Optional Feature)
# ==========================================

if HAS_PDF_LIBS:
    class PDFReport(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.set_text_color(74, 59, 50) # Dark Brown
            self.cell(0, 10, 'PayInsight AI - Payment Performance Report', 0, 1, 'L')
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
else:
    # Stub function when PDF libraries are not available
    def generate_pdf_report(data):
        """PDF generation not available - install fpdf and kaleido"""
        return None

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
                                    file_name="PayInsight_Report.pdf",
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
            num_kpis = len(data["kpis"])
            cols_per_row = 3
            for row_start in range(0, num_kpis, cols_per_row):
                row_kpis = data["kpis"][row_start:row_start + cols_per_row]
                kpi_cols = st.columns(len(row_kpis))
                for idx, kpi in enumerate(row_kpis):
                    with kpi_cols[idx]:
                        # Derive trend from delta if not explicitly provided
                        trend_dir = kpi.get("trend", "up" if kpi["delta"].startswith("+") else "down")
                        trend_class = "positive-trend" if trend_dir == "up" else "negative-trend"
                        trend_icon = "↑" if trend_dir == "up" else "↓"
                    
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