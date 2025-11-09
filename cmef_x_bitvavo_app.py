# cmef_x_complete_app.py
import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import random
import plotly.express as px

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
# CMEF X Scoring
# ---------------------------
def compute_scores(data, alpha, price_max, volume_max):
    price_score = min(max(data['price']/price_max,0),1)*5
    volume_score = min(max(data['volume']/volume_max,0),1)*5
    github_score = random.uniform(2,5)
    K = round((price_score*0.4 + github_score*0.6),2)
    
    cg_metrics = fetch_coingecko_metrics(data['coin_id'])
    active_score = min(cg_metrics['active_addresses']/1e6,5)
    tx_score = min(cg_metrics['tx_count']/1e6,5)
    social_score = random.uniform(2.5,5)
    M = round((active_score*0.3 + tx_score*0.3 + social_score*0.4),2)
    
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
# Batch analyse
# ---------------------------
def batch_analyze(markets, alpha, profile):
    results=[]
    price_max=0
    volume_max=0
    tickers={}
    
    for market in markets:
        ticker = fetch_ticker(market)
        if ticker:
            tickers[market] = ticker
            price_max = max(price_max, ticker['price'])
            volume_max = max(volume_max, ticker['volume'])
        time.sleep(0.05)
    
    for market, ticker in tickers.items():
        coin_id = market.split('-')[0].lower()
        ticker['coin_id'] = coin_id
        scores = compute_scores(ticker, alpha, price_max, volume_max)
        rec = portfolio_recommendation(scores['RAR'], profile)
        results.append({
            'Market':market,
            'Price':ticker['price'],
            'Volume':ticker['volume'],
            'K-Score':scores['K'],
            'M-Score':scores['M'],
            'OTS':scores['OTS'],
            'R-Score':scores['R'],
            'RAR-Score':scores['RAR'],
            'Portfolio':rec,
            'AI_Rationale':scores['Rationale']
        })
    return pd.DataFrame(results)

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X Complete App", layout="wide")
st.title("CMEF X Crypto Analysis Tool - 100% Complete")
st.write("Analyse datum & tijd:", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

profile = st.selectbox("Kies profiel", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

mode = st.radio("Analyse modus", ["Enkele coin","Batch alle coins"])
eur_markets = fetch_eur_markets()
if not eur_markets:
    st.stop()

if mode=="Enkele coin":
    market = st.selectbox("Kies cryptocurrency (EUR-paar)", eur_markets)
    if st.button("Analyseer Coin"):
        ticker = fetch_ticker(market)
        if ticker:
            ticker['coin_id'] = market.split('-')[0].lower()
            scores = compute_scores(ticker, alpha, price_max=60000, volume_max=1e9)
            rec = portfolio_recommendation(scores['RAR'], profile)
            st.write("K-Score:",scores['K'],"M-Score:",scores['M'],"OTS:",scores['OTS'],
                     "R-Score:",scores['R'],"RAR-Score:",scores['RAR'],"Portfolio:",rec)
            st.json(scores['Rationale'])
        else:
            st.error("Kon data niet ophalen.")
else:
    if st.button("Batch analyse alle coins"):
        df_batch = batch_analyze(eur_markets, alpha, profile)
        st.dataframe(df_batch.sort_values('RAR-Score',ascending=False))
        st.download_button("Exporteer naar CSV",
                           df_batch.sort_values('RAR-Score',ascending=False).to_csv(index=False).encode('utf-8'),
                           "cmef_x_batch.csv","text/csv")
        fig = px.bar(df_batch.sort_values('RAR-Score',ascending=False).head(20),
                     x='Market', y='RAR-Score', color='RAR-Score', title="Top 20 RAR-Score Coins")
        st.plotly_chart(fig, use_container_width=True)
