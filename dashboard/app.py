import os
import time
import psycopg2
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Anomaly Detection Monitor", page_icon="🔍", layout="wide", initial_sidebar_state="collapsed")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "anomaly_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "anomaly_pass")
DB_NAME = os.getenv("DB_NAME", "anomaly_db")

BUFFER_SIZE = 300
CHANNELS = ["temperature", "vibration", "pressure"]
CHANNEL_COLORS = {"temperature": "#ff6b6b", "vibration": "#4ecdc4", "pressure": "#45aaf2"}
UNITS = {"temperature": "°C", "vibration": "mm/s", "pressure": "kPa"}

if "uptime_start" not in st.session_state:
    st.session_state.uptime_start = time.time()

def get_db():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=5
        )
    except psycopg2.OperationalError as e:
        st.error(f"❌ Database connection failed")
        st.info(f"Trying to connect to: {DB_HOST}:{DB_PORT}/{DB_NAME}\n\nError: {str(e)}")
        return None

st.markdown("""<style>
    .stApp { background: #0d0f14; color: #e0e0e0; }
    .metric-card { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 12px; padding: 16px 20px; text-align: center; }
    .metric-card .label { font-size: 11px; color: #888; letter-spacing: 1px; text-transform: uppercase; }
    .metric-card .value { font-size: 28px; font-weight: 700; color: #fff; margin: 4px 0; }
    .alert-row { background: rgba(255,80,80,0.08); border-left: 3px solid #ff5050; border-radius: 4px; padding: 6px 10px; margin: 4px 0; font-size: 12px; font-family: monospace; }
    h1, h2, h3 { color: #fff !important; }
</style>""", unsafe_allow_html=True)

col_title, col_status = st.columns([4, 1])
with col_title:
    st.markdown("# Real Time Anomaly Detection Monitor")
    st.caption(f"Database: `{DB_HOST}:{DB_PORT}/{DB_NAME}`")
with col_status:
    st.markdown("")
    uptime = int(time.time() - st.session_state.uptime_start)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    st.metric("Uptime", f"{h:02d}:{m:02d}:{s:02d}")

# Query stats
total = 0
anomalies = 0
rate = 0

try:
    conn = get_db()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sensor_readings")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sensor_readings WHERE is_anomaly = TRUE")
        anomalies = cur.fetchone()[0]
        cur.close()
        conn.close()
        rate = 100 * anomalies / max(total, 1)
        st.success("✓ Connected to database")
except Exception as e:
    st.warning(f"⚠️ Database query error: {str(e)}")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="metric-card"><div class="label">Messages Processed</div><div class="value">{total:,}</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="label">Anomalies Detected</div><div class="value" style="color:#ff6b6b">{anomalies:,}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="label">Anomaly Rate</div><div class="value">{rate:.1f}%</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="metric-card"><div class="label">Latest Data</div><div class="value" style="color:#45aaf2">Live</div></div>', unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.subheader("📈 Live Sensor Readings")

for ch in CHANNELS:
    try:
        conn = get_db()
        if not conn:
            st.warning(f"Cannot load {ch} - database unavailable")
            continue
            
        cur = conn.cursor()
        cur.execute(f"SELECT timestamp, value, is_anomaly FROM sensor_readings WHERE channel = %s ORDER BY timestamp DESC LIMIT {BUFFER_SIZE}", (ch,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        if not rows:
            st.info(f"No data for {ch} yet")
            continue
        
        rows = list(reversed(rows))
        ts = [row[0] for row in rows]
        vals = [row[1] for row in rows]
        anom = [row[2] for row in rows]
        
        color = CHANNEL_COLORS[ch]
        unit = UNITS[ch]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ts, y=vals, mode="lines", line=dict(color=color, width=1.5), showlegend=False))
        
        anom_x = [t for t, a in zip(ts, anom) if a]
        anom_y = [v for v, a in zip(vals, anom) if a]
        if anom_x:
            fig.add_trace(go.Scatter(x=anom_x, y=anom_y, mode="markers", marker=dict(color="#ff0000", size=9, symbol="x", line=dict(width=2)), showlegend=False))
        
        if len(vals) >= 10:
            rm = pd.Series(vals).rolling(10).mean().tolist()
            fig.add_trace(go.Scatter(x=ts, y=rm, mode="lines", line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"), showlegend=False))
        
        fig.update_layout(title=dict(text=f"{ch.title()}  ({unit})", font=dict(size=14)), margin=dict(l=0, r=0, t=35, b=0), height=230, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,17,23,0.7)", xaxis=dict(showgrid=False, showticklabels=False), yaxis=dict(gridcolor="rgba(255,255,255,0.07)", color="#aaa"), font=dict(color="#ddd"))
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{ch}_{time.time()}")
    except Exception as e:
        st.warning(f"Error loading {ch} data: {str(e)}")

left, right = st.columns([1, 1])
with left:
    try:
        rates = {}
        for ch in CHANNELS:
            conn = get_db()
            if conn:
                cur = conn.cursor()
                cur.execute(f"SELECT SUM(CASE WHEN is_anomaly = TRUE THEN 1 ELSE 0 END), COUNT(*) FROM sensor_readings WHERE channel = %s", (ch,))
                anom_count, total_ch = cur.fetchone()
                cur.close()
                conn.close()
                rates[ch] = 100 * (anom_count or 0) / max(total_ch, 1)
        
        if rates:
            fig = go.Figure(go.Bar(x=list(rates.keys()), y=list(rates.values()), marker_color=[CHANNEL_COLORS[ch] for ch in rates], text=[f"{v:.1f}%" for v in rates.values()], textposition="outside"))
            fig.update_layout(title="Anomaly Rate by Channel (%)", margin=dict(l=0, r=0, t=35, b=0), height=220, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,17,23,0.7)", yaxis=dict(gridcolor="rgba(255,255,255,0.07)", color="#aaa"), font=dict(color="#ddd"), xaxis=dict(color="#ddd"))
            st.plotly_chart(fig, use_container_width=True, key=f"rate_chart_{time.time()}")
    except Exception as e:
        st.warning(f"Error loading anomaly rates: {str(e)}")

with right:
    st.subheader("🚨 Alert Log")
    try:
        conn = get_db()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT timestamp, channel, value, unit FROM anomaly_alerts WHERE is_anomaly = TRUE ORDER BY timestamp DESC LIMIT 20")
            alerts = cur.fetchall()
            cur.close()
            conn.close()
            
            if not alerts:
                st.info("No anomalies detected yet.")
            else:
                for a in alerts:
                    ts_short = str(a[0])[11:19] if a[0] else ""
                    st.markdown(f'<div class="alert-row"><b>{ts_short}</b> | {a[1]} | <b>{a[2]:.2f}{a[3]}</b></div>', unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Error loading alerts: {str(e)}")

time.sleep(2)
st.rerun()
