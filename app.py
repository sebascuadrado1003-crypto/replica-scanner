import streamlit as st
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(page_title="Replica Scanner Pro", layout="wide")
st.title("🔍 REPLICA SCANNER V3 - VELAS + REPLICAS + DIRECCION")
SYMBOL = st.sidebar.selectbox("Activo", ["GC=F", "EURUSD=X", "BTC-USD", "ES=F"], index=0)
MIN_LEN = st.sidebar.slider("Min largo replica", 5, 50, 10)
MAX_LEN = st.sidebar.slider("Max largo replica", 50, 300, 160)
UMBRAL = st.sidebar.slider("Umbral %", 50, 95, 70)
CURRENT_LEN = st.sidebar.slider("Largo AHORA", 20, 100, 37)

@st.cache_data(ttl=120)
def get_data():
    df = yf.download(SYMBOL, period="2d", interval="5m")
    return df.tail(500).dropna()

data = get_data()
opens = data['Open'].values.flatten()
highs = data['High'].values.flatten()
lows = data['Low'].values.flatten()
closes = data['Close'].values.flatten()

def normalize(x):
    x = np.array(x, dtype=float)
    return (x - np.mean(x)) / (np.std(x)+1e-8)

current = normalize(closes[-CURRENT_LEN:])
replicas = []
for L in range(MIN_LEN, MAX_LEN+1, 10):
    if L < 5: continue
    for i in range(0, len(closes)-L-CURRENT_LEN-20, 15):
        past = closes[i:i+L]
        if len(past) < 5: continue
        x_old = np.linspace(0, 1, len(past))
        x_new = np.linspace(0, 1, CURRENT_LEN)
        past_r = np.interp(x_new, x_old, past)
        corr = np.corrcoef(current, normalize(past_r))[0,1]
        sim = corr*100
        if sim >= UMBRAL and not np.isnan(sim):
            futuro = closes[i+L:i+L+20]
            if len(futuro) > 0:
                dir = "LONG" if float(np.mean(futuro)) > float(closes[i+L-1]) else "SHORT"
                replicas.append((i, i+L, sim, dir))
replicas = sorted(replicas, key=lambda x: x[2], reverse=True)
filtradas = []
for r in replicas:
    if not any(abs(r[0]-f[0]) < 20 for f in filtradas):
        filtradas.append(r)
    if len(filtradas) >= 10: break
longs = sum(1 for f in filtradas if f[3]=="LONG")
shorts = len(filtradas)-longs
direccion = "CALL / LONG" if longs >= shorts else "PUT / SHORT"
color_dir = "#00ff88" if "LONG" in direccion else "#ff4444"
fig, ax = plt.subplots(figsize=(16,6))
fig.patch.set_facecolor('#0a0a0a')
ax.set_facecolor('#0a0a0a')
for i in range(len(closes)):
    c = "#00ff88" if closes[i] >= opens[i] else "#ff4444"
    ax.plot([i,i],[lows[i],highs[i]],color=c,lw=0.7, alpha=0.8)
    body_h = abs(float(closes[i])-float(opens[i]))+0.01
    rect = mpatches.Rectangle((i-0.35, float(min(opens[i],closes[i]))), 0.7, body_h, facecolor=c, edgecolor=c)
    ax.add_patch(rect)
for s,e,sim,d in filtradas:
    ax.axvspan(s,e,color="#a855f7",alpha=0.18)
    ax.text(s, float(highs[s])*1.001, f" {sim:.0f}% {d}", color="#a855f7", fontsize=8, fontweight="bold")
ax.axvspan(len(closes)-CURRENT_LEN, len(closes), color=color_dir, alpha=0.25)
ax.text(len(closes)-CURRENT_LEN, float(highs.max()), f" AHORA 100% - {direccion}", color=color_dir, fontweight="bold", fontsize=11)
ax.tick_params(colors='white')
ax.set_ylim(float(np.min(lows))*0.999, float(np.max(highs))*1.01)
st.pyplot(fig)
st.success(f"ENTRADA: {direccion} | {len(filtradas)} replicas >{UMBRAL}% | {longs} LONG vs {shorts} SHORT")
st.caption("Cajas moradas = donde ya replico | Verde = ahora")
if st.button("Actualizar"):
    st.cache_data.clear()
    st.rerun()
