import streamlit as st
import requests
import random
from datetime import datetime
import plotly.graph_objects as go

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"

# ---------------------------
# Helper functies
# ---------------------------
@st.cache_data(ttl=300)
def fetch_eur_markets():
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m['market'] for m in markets if m['quote'] == 'EUR']
        return eur_markets
    except Exception as e:
        st.error(f"Kan Bitvavo markets niet ophalen: {e}")
        return []

def fetch_ticker(market):
    try:
        url = f"{BITVAVO_API_URL}/{market}/ticker"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {
            'price': float(data['last']),
            'volume': float(data['volume'])
        }
    except:
        return None

# ---------------------------
# CMEF X Scoreberekening
# ---------------------------
def compute_scores(data, alpha):
    # K-Score (quality)
    price_score = min(max(data['price']/60000,0),1)*5
    volume_score = min(max(data['volume']/1e9,0),1)*5
    K = round(0.6*price_score + 0.4*volume_score,2)

    # M-Score (growth potential)
    active_score = random.uniform(2.5,5)
    tx_score = random.uniform(2.5,5)
    social_score = random.uniform(2.5,5)
    M = round(0.3*active_score + 0.3*tx_score + 0.4*social_score,2)

    # Overall Technical Strength
    OTS = round(K*alpha + M*(1-alpha),2)

    # Risk Score
    R_tech = random.uniform(0.3,0.6)
    R_reg = random.uniform(0.2,0.5)
    R_fin = random.uniform(0.3,0.6)
    R = round(R_tech*0.4 + R_reg*0.35 + R_fin*0.25,2)

    # Risk-adjusted result
    RAR = round(OTS*(1-R),2)

    rationale = {
        'K_Price': price_score,
        'K_Volume': volume_score,
        'M_Active': active_score,
        'M_TX': tx_score,
        'M_Social': social_score,
        'R_Tech': R_tech,
        'R_Reg': R_reg,
        'R_Fin': R_fin
    }

    return {'K':K,'M':M,'OTS':OTS,'R':R,'RAR':RAR,'Rationale':rationale}

# ---------------------------
# Portfolio aanbeveling
# ---------------------------
def portfolio_recommendation(rar_score, profile):
    if rar_score >= 65:
        scale = {'Conservative':'Core','Balanced':'Core','Growth':'Core'}
    elif rar_score >=50:
        scale = {'Conservative':'Tactical','Balanced':'Core','Growth':'Core'}
    elif rar_score >=35:
        scale = {'Conservative':'Small/Cautious','Balanced':'Tactical','Growth':'Core'}
    elif rar_score >=20:
        scale = {'Conservative':'Avoid','Balanced':'Small/Cautious','Growth':'Tactical'}
    else:
        scale = {'Conservative':'Avoid','Balanced':'Avoid','Growth':'Small/Cautious'}
    return scale.get(profile,'Cautious')

# ---------------------------
# Visualisatie functies
# ---------------------------
def display_scores_chart(scores):
    fig = go.Figure(go.Barpolar(
        r=[scores['K'], scores['M'], scores['OTS'], scores['R'], scores['RAR']],
        theta=['K','M','OTS','R','RAR'],
        width=[15]*5,
        marker_color=['blue','orange','green','red','purple'],
        marker_line_color="black",
        marker_line_width=1,
        opacity=0.8
    ))
    fig.update_layout(
        template=None,
        polar = dict(radialaxis=dict(range=[0,5], showticklabels=True, ticks='')),
        showlegend=False,
        height=400
    )
    st.plotly_chart(fig)

def display_kpi_cards(scores, rec):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("K-Score", scores['K'])
    col2.metric("M-Score", scores['M'])
    col3.metric("OTS", scores['OTS'])
    col4.metric("R-Score", scores['R'])
    col5.metric("RAR", f"{scores['RAR']} ({rec})")

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X Crypto Tool", layout="wide")
st.title("CMEF X Crypto Analysis Tool - Bitvavo Edition")

st.write("**Analyse datum & tijd:**", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

# Profiel keuze
profile = st.selectbox("Kies uw beleggingsprofiel", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

# Coin keuze
eur_markets = fetch_eur_markets()
market_input = st.selectbox("Kies cryptocurrency (EUR-market)", eur_markets)

# Analyse knop
if st.button("Analyseer coin"):
    ticker = fetch_ticker(market_input)
    if ticker:
        scores = compute_scores(ticker, alpha)
        rec = portfolio_recommendation(scores['RAR'], profile)
        
        # KPI kaarten
        st.subheader("📊 CMEF X Scores Overview")
        display_kpi_cards(scores, rec)
        
        # Grafiek
        st.subheader("📈 Visual Score Chart")
        display_scores_chart(scores)
        
        # Detail toelichting
        st.subheader("📖 Coin-specifieke toelichting")
        r = scores['Rationale']
        st.markdown(f"- **K-Score**: combinatie prijs ({r['K_Price']:.2f}) en volume ({r['K_Volume']:.2f})")
        st.markdown(f"- **M-Score**: growth indicaties -> actieve wallets ({r['M_Active']:.2f}), transacties ({r['M_TX']:.2f}), social ({r['M_Social']:.2f})")
        st.markdown(f"- **OTS**: Overall Technical Strength = {scores['OTS']:.2f}")
        st.markdown(f"- **R-Score**: Risico = {scores['R']:.2f} (tech {r['R_Tech']:.2f}, reg {r['R_Reg']:.2f}, fin {r['R_Fin']:.2f})")
        st.markdown(f"- **RAR-Score**: Risk-adjusted result = {scores['RAR']:.2f}")
        st.markdown(f"- **Portfolio-aanbeveling**: {rec}")
    else:
        st.error("Kon data niet ophalen van Bitvavo. Controleer internetverbinding of selecteer een andere coin.")
