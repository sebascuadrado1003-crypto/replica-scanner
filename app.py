import streamlit as st
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

st.set_page_config(page_title="Replica Scanner AI - Entradas", layout="wide")
st_autorefresh(interval=10000, key="broker_v6")

st.markdown("""
<style>
.entry-call {background:linear-gradient(90deg,#00ff88,#00cc66); color:black; padding:20px; border-radius:15px; text-align:center; font-weight:900; font-size:26px;}
.entry-put {background:linear-gradient(90deg,#ff4444,#cc0000); color:white; padding:20px; border-radius:15px; text-align:center; font-weight:900; font-size:26px;}
.time-box {background:#1a1a1a; border:2px solid #333; border-radius:12px; padding:15px; text-align:center; margin-top:10px;}
</style>
""", unsafe_allow_html=True)

SYMBOL_MAP = {"ORO XAUUSD": "GC=F", "EUR/USD": "EURUSD=X", "BTC": "BTC-USD", "NAS100": "NQ=F"}
TIME_MAP = {"1m": ("1m","1","2 min"), "5m": ("5m","5","10 min"), "15m": ("15m","15","30 min"), "1H": ("60m","60","2 Hrs"), "4H": ("240m","240","8 Hrs")}

activo_label = st.sidebar.selectbox("Activo", list(SYMBOL_MAP.keys()))
temp_label = st.sidebar.selectbox("Temporalidad", list(TIME_MAP.keys()), index=1)
umbral = st.sidebar.slider("Umbral Replica %", 50, 90, 72)

SYMBOL = SYMBOL_MAP[activo_label]
INTERVAL_YF, INTERVAL_TV, EXPIRACION_TXT = TIME_MAP[temp_label]

@st.cache_data(ttl=10)
def get_data(sym, interval):
    period = "5d" if interval in ["1m","5m"] else "30d"
    df = yf.download(sym, period=period, interval=interval, auto_adjust=True)
    return df.dropna().tail(500)

data = get_data(SYMBOL, INTERVAL_YF)
if len(data) < 100:
    st.warning("Cargando velas...")
    st.stop()

opens = data['Open'].values.flatten()
highs = data['High'].values.flatten()
lows = data['Low'].values.flatten()
closes = data['Close'].values.flatten()
times = data.index
precio = float(closes[-1])
hora_actual = datetime.now(pytz.timezone("America/Bogota"))

def normalize(x): return (x - np.mean(x)) / (np.std(x)+1e-8)
CURRENT_LEN = 37
current = normalize(closes[-CURRENT_LEN:])

replicas = []
for L in range(10, 161, 10):
    for i in range(0, len(closes)-L-CURRENT_LEN-10, 12):
        past = closes[i:i+L]
        past_r = np.interp(np.linspace(0,1,CURRENT_LEN), np.linspace(0,1,len(past)), past)
        corr = np.corrcoef(current, normalize(past_r))[0,1]
        if corr*100 >= umbral and not np.isnan(corr):
            futuro = closes[i+L:i+L+8]
            dir = "CALL" if np.mean(futuro) > closes[i+L-1] else "PUT"
            replicas.append((i,i+L,corr*100,dir, times[i]))

replicas = sorted(replicas, key=lambda x: x[2], reverse=True)[:10]
longs = sum(1 for r in replicas if r[3]=="CALL")
shorts = len(replicas)-longs
direccion = "CALL" if longs >= shorts else "PUT"
confianza = float(np.mean([r[2] for r in replicas])) if replicas else 0

# CALCULO HORA ENTRADA
# Entrada: al cierre de vela actual + 5 seg
if INTERVAL_YF == "1m": delta_entrada = timedelta(minutes=1)
elif INTERVAL_YF == "5m": delta_entrada = timedelta(minutes=5)
elif INTERVAL_YF == "15m": delta_entrada = timedelta(minutes=15)
elif INTERVAL_YF == "60m": delta_entrada = timedelta(hours=1)
else: delta_entrada = timedelta(hours=4)

hora_entrada = hora_actual + timedelta(seconds=15) # entra en 15s
hora_cierre_entrada = hora_entrada + delta_entrada
if INTERVAL_YF == "1m": expira = hora_entrada + timedelta(minutes=2)
elif INTERVAL_YF == "5m": expira = hora_entrada + timedelta(minutes=10)
elif INTERVAL_YF == "15m": expira = hora_entrada + timedelta(minutes=30)
elif INTERVAL_YF == "60m": expira = hora_entrada + timedelta(hours=2)
else: expira = hora_entrada + timedelta(hours=8)

st.title(f"🔴 BROKER LIVE {activo_label} {temp_label}")

col1, col2 = st.columns([1, 2.2])

with col1:
    st.markdown(f"<h1 style='margin:0'>{precio:.2f}</h1><small>{hora_actual.strftime('%H:%M:%S')} Bogota</small>", unsafe_allow_html=True)
    
    if direccion == "CALL":
        st.markdown(f'<div class="entry-call">📈 ENTRADA<br>{direccion}<br><span style="font-size:16px">Confianza {confianza:.0f}%</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="entry-put">📉 ENTRADA<br>{direccion}<br><span style="font-size:16px">Confianza {confianza:.0f}%</span></div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="time-box">
    <b>⏰ TIEMPO DE ENTRADA</b><br>
    <span style="font-size:22px; color:#00ff88;">{hora_entrada.strftime('%H:%M:%S')}</span><br>
    <small>Entra al cierre de esta vela</small><br><br>
    <b>⏳ EXPIRACION</b><br>
    <span style="font-size:18px;">{EXPIRACION_TXT}</span><br>
    Cierre: {expira.strftime('%H:%M:%S')}<br><br>
    <b>📊 DATO</b><br>
    {len(replicas)} réplicas | {longs} CALL vs {shorts} PUT<br>
    Tendencia: {"ALCISTA" if closes[-1] > np.mean(closes[-20:]) else "BAJISTA"}
    </div>
    """, unsafe_allow_html=True)

    st.info(f"🤖 IA: Patrón de {CURRENT_LEN} velas en {temp_label} se repitió {len(replicas)} veces. {confianza:.0f}% similar. Dirección más probable {direccion} para las próximas {EXPIRACION_TXT}. Entra en {hora_entrada.strftime('%H:%M')}")

with col2:
    fig = go.Figure(data=[go.Candlestick(x=list(range(len(closes))), open=opens, high=highs, low=lows, close=closes, increasing_line_color='#00ff88', decreasing_line_color='#ff4444')])
    for s,e,sim,d, _ in replicas:
        fig.add_vrect(x0=s, x1=e, fillcolor="rgba(168,85,247,0.2)", line_width=0)
        fig.add_annotation(x=s, y=highs[s], text=f"{sim:.0f}% {d}", showarrow=False, font=dict(color="#a855f7", size=9))
    fig.add_vrect(x0=len(closes)-CURRENT_LEN, x1=len(closes), fillcolor="rgba(0,255,136,0.2)" if direccion=="CALL" else "rgba(255,68,68,0.2)", line_width=0)
    fig.add_annotation(x=len(closes)-CURRENT_LEN, y=highs.max(), text=f"ENTRA {direccion} {hora_entrada.strftime('%H:%M:%S')}", showarrow=False, font=dict(color="#00ff88" if direccion=="CALL" else "#ff4444", size=13))
    fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"Replica Scanner V6 | Entrada calculada cada 10s | Temporalidad {temp_label} | Confianza {confianza:.0f}%")
