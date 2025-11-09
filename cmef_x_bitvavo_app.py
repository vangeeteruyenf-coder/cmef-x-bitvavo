import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import random

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# ---------------------------
# Helper functies
# ---------------------------
def fetch_eur_markets():
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m['market'] for m in markets if m['quote']=='EUR']
        st.info(f"EUR-markets opgehaald: {len(eur_markets)} coins")
        return eur_markets
    except Exception as e:
        st.error(f"Kan Bitvavo markets niet ophalen: {e}")
        return []

def fetch_ticker(market):
    try:
        url = f"{BITVAVO_API_URL}/{market}/ticker"
        resp = requests.get(url, timeout=5)
        if resp.status_code==404:
            alt_url = f"{BITVAVO_API_URL}/ticker/24h?market={market}"
            alt_resp = requests.get(alt_url, timeout=5)
            if alt_resp.status_code==200:
                data = alt_resp.json()
                return {'price':float(data.get('last',0)),'volume':float(data.get('volume',0))}
            return None
        elif resp.status_code != 200:
            return None
        data = resp.json()
        return {'price':float(data['last']),'volume':float(data['volume'])}
    except:
        return None

def fetch_coingecko_metrics(coin_id):
    """Haalt actieve wallets en 24h volume op"""
    try:
        url = f"{COINGECKO_API_URL}/coins/{coin_id}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        active_addresses = data.get('market_data',{}).get('circulating_supply',0)
        tx_count = data.get('market_data',{}).get('total_volume',{}).get('eur',0)
        return {'active_addresses':active_addresses,'tx_count':tx_count}
    except:
        return {'active_addresses':0,'tx_count':0}

# ---------------------------
# CMEF X Scoreberekening
# ---------------------------
def compute_scores(data, alpha, price_max, volume_max):
    price_score = min(max(data['price']/price_max,0),1)*5
    github_score = random.uniform(2.5,5)  # Placeholder dev activity
    K = round(0.5*price_score + 0.5*github_score,2)
    
    cg_metrics = fetch_coingecko_metrics(data['coin_id'])
    active_score = min(cg_metrics['active_addresses']/1e6,5)
    tx_score = min(cg_metrics['tx_count']/1e6,5)
    social_score = random.uniform(2.5,5)
    M = round(0.3*active_score + 0.3*tx_score + 0.4*social_score,2)
    
    OTS = round(K*alpha + M*(1-alpha),2)
    
    R_tech = random.uniform(0.3,0.6)
    R_reg = random.uniform(0.2,0.5)
    R_fin = random.uniform(0.3,0.6)
    R = round(R_tech*0.4 + R_reg*0.35 + R_fin*0.25,2)
    
    RAR = round(OTS*(1-R),2)
    
    rationale = {
        'K_Price': price_score,
        'K_Github': github_score,
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
# Coin-specifieke toelichting
# ---------------------------
def generate_coin_explanation(scores, profile):
    r = scores['Rationale']
    explanations = {
        "K-Score": f"Laag omdat de prijs van deze coin ver onder de topcoins ligt ({r['K_Price']:.2f}) en de developer-activiteit is {r['K_Github']:.2f}.",
        "M-Score": f"Redelijk laag omdat er {r['M_Active']:.0f} actieve wallets zijn en {r['M_TX']:.0f} transacties, ondanks social activity score van {r['M_Social']:.2f}.",
        "OTS": f"De Overall Technical Strength is {scores['OTS']:.2f}, wat het resultaat is van K- en M-Scores.",
        "R-Score": f"Risico score is {scores['R']:.2f}, technisch {r['R_Tech']:.2f}, regulatoir {r['R_Reg']:.2f}, financieel {r['R_Fin']:.2f}.",
        "RAR-Score": f"Risk-Adjusted Result score is {scores['RAR']:.2f}, beïnvloed door kwaliteit en risico.",
        "Portfolio-aanbeveling": f"Advies voor dit profiel: {portfolio_recommendation(scores['RAR'], profile)}"
    }
    return explanations

# ---------------------------
# Scores visueel
# ---------------------------
def display_scores(scores):
    st.subheader("📊 Scores")
    for key in ['K','M','OTS','R','RAR']:
        val = scores[key]
        st.progress(min(val/5,1))
        color = 'green' if val>=3.5 else 'orange' if val>=2 else 'red'
        st.markdown(f"**{key}-Score:** <span style='color:{color}'>{val}</span>", unsafe_allow_html=True)

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X PRO App", layout="wide")
st.title("CMEF X Crypto Analysis Tool - FULL PRO")
st.write("**Analyse datum & tijd:**", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

profile = st.selectbox("Kies profiel", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

mode = st.radio("Analyse modus", ["Enkele coin","Batch alle coins"])
eur_markets = fetch_eur_markets()
if not eur_markets:
    st.stop()

# ---------------------------
# Enkele coin analyse
# ---------------------------
if mode=="Enkele coin":
    market = st.selectbox("Kies cryptocurrency (EUR-paar)", eur_markets)
    if st.button("Analyseer Coin"):
        ticker = fetch_ticker(market)
        if ticker:
            ticker['coin_id'] = market.split('-')[0].lower()
            scores = compute_scores(ticker, alpha, price_max=60000, volume_max=1e9)
            explanations = generate_coin_explanation(scores, profile)
            rec = portfolio_recommendation(scores['RAR'], profile)
            
            display_scores(scores)
            st.markdown(f"**Portfolio-aanbeveling:** {rec}")
            
            st.subheader("📖 Coin-specifieke toelichting")
            for key, text in explanations.items():
                st.markdown(f"**{key}:** {text}")
        else:
            st.error("Kon data niet ophalen.")

# ---------------------------
# Batch analyse
# ---------------------------
else:
    if st.button("Batch analyse alle coins"):
        results = []
        for market in eur_markets:
            ticker = fetch_ticker(market)
            if ticker:
                ticker['coin_id'] = market.split('-')[0].lower()
                scores = compute_scores(ticker, alpha, price_max=60000, volume_max=1e9)
                explanations = generate_coin_explanation(scores, profile)
                rec = portfolio_recommendation(scores['RAR'], profile)
                
                results.append({
                    'Market': market,
                    'Price': ticker['price'],
                    'Volume': ticker['volume'],
                    'K-Score': scores['K'],
                    'M-Score': scores['M'],
                    'OTS': scores['OTS'],
                    'R-Score': scores['R'],
                    'RAR-Score': scores['RAR'],
                    'Portfolio': rec
                })
            time.sleep(0.05)
        df_batch = pd.DataFrame(results)
        st.dataframe(df_batch.sort_values('RAR-Score',ascending=False))
        st.download_button("Exporteer naar CSV",
                           df_batch.sort_values('RAR-Score',ascending=False).to_csv(index=False).encode('utf-8'),
                           "cmef_x_batch.csv","text/csv")
