# cmef_x_bitvavo_full_test.py
import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

BITVAVO_API_URL = "https://api.bitvavo.com/v2"

# ---------------------------
# Helper functies
# ---------------------------
def fetch_eur_markets():
    """Haal alle EUR-markets op van Bitvavo"""
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m['market'] for m in markets if m['quote'] == 'EUR']
        return eur_markets
    except Exception as e:
        st.error(f"Kan Bitvavo markets niet ophalen: {e}")
        return []

def fetch_ticker(market, retries=3):
    """Haalt live prijs en volume op met retry en logging"""
    for attempt in range(1, retries+1):
        try:
            resp = requests.get(f"{BITVAVO_API_URL}/{market}/ticker", timeout=5)
            if resp.status_code != 200:
                st.warning(f"Attempt {attempt} voor {market} mislukte: status {resp.status_code}")
                time.sleep(1)
                continue
            data = resp.json()
            if 'last' not in data or 'volume' not in data:
                st.warning(f"Attempt {attempt} voor {market} bevat geen data: {data}")
                time.sleep(1)
                continue
            return {'price': float(data['last']), 'volume': float(data['volume'])}
        except Exception as e:
            st.warning(f"Attempt {attempt} voor {market} exception: {e}")
            time.sleep(1)
    return None

def normalize(value, min_val, max_val):
    return min(max((value - min_val)/(max_val - min_val),0),1)*5

def compute_scores(data, alpha):
    if not data or data['price']==0:
        return {'K':0,'M':0,'OTS':0,'R':0,'RAR':0}
    K = normalize(data['price'],0.01,60000)
    M = normalize(data['volume'],0.01,1e9)
    OTS = K*alpha + M*(1-alpha)
    R = 0.5
    RAR = OTS*(1-R)
    return {'K':round(K,2),'M':round(M,2),'OTS':round(OTS,2),'R':round(R,2),'RAR':round(RAR,2)}

# ---------------------------
# Testfunctie per coin
# ---------------------------
def test_coin(market):
    st.subheader(f"🔍 Test coin: {market}")
    # 1️⃣ Check market aanwezig
    eur_markets = fetch_eur_markets()
    if market not in eur_markets:
        st.error(f"{market} niet gevonden in EUR-markets!")
        return None
    st.success(f"{market} aanwezig in EUR-markets.")
    
    # 2️⃣ Fetch ticker met retry
    data = fetch_ticker(market)
    if not data:
        st.error(f"⚠️ Kon data niet ophalen voor {market}.")
        return None
    st.success(f"✅ Ticker data opgehaald: {data}")
    return data

# ---------------------------
# Batch analyse met debug
# ---------------------------
def batch_analyze_debug(markets, alpha):
    results=[]
    for market in markets:
        data = test_coin(market)
        if not data:
            continue
        scores = compute_scores(data, alpha)
        results.append({
            'Market':market,
            'Price':data['price'],
            'Volume':data['volume'],
            'K-Score':scores['K'],
            'M-Score':scores['M'],
            'OTS':scores['OTS'],
            'R-Score':scores['R'],
            'RAR-Score':scores['RAR'],
            'AI_Profile':'[AI]',
            'AI_Rationale':'[AI: rationale]',
            'Section_A':'[AI placeholders]',
            'Section_B':'[AI placeholders]',
            'Risk_Analysis':'[AI placeholders]',
            'Portfolio_Recommendation':'[AI placeholders]'
        })
        time.sleep(0.2)
    return pd.DataFrame(results)

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X Bitvavo Full Test", layout="wide")
st.title("CMEF X Crypto Analysis Tool (Bitvavo) - Test Mode")

# Datum & tijd
st.write("**Analyse datum & tijd:**", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

# Profiel selectie
profile = st.selectbox("Kies profiel", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

# Analyse modus
mode = st.radio("Analyse modus", ["Enkele coin","Batch alle coins"])

# Ophalen EUR-markets
eur_markets = fetch_eur_markets()
if not eur_markets:
    st.error("Geen EUR-markets gevonden. Controleer Bitvavo API.")
    st.stop()

if mode=="Enkele coin":
    market = st.selectbox("Kies cryptocurrency (EUR-paar)", eur_markets)
    if st.button("Test & Analyseer Coin"):
        data = test_coin(market)
        if not data:
            st.stop()
        scores = compute_scores(data, alpha)
        st.write("K-Score:",scores['K'],"M-Score:",scores['M'],"OTS:",scores['OTS'],
                 "R-Score:",scores['R'],"RAR-Score:",scores['RAR'])
        st.progress(min(int(scores['RAR']/5*100),100))
else:
    if st.button("Batch test & analyseer alle EUR-coins"):
        df_batch = batch_analyze_debug(eur_markets, alpha)
        if df_batch.empty:
            st.error("Geen resultaten opgehaald.")
        else:
            st.success(f"Batch-analyse klaar! {len(df_batch)} coins geanalyseerd.")
            st.dataframe(df_batch.sort_values('RAR-Score',ascending=False))
            if st.button("Exporteer batch naar CSV"):
                filename="cmef_x_batch_full_test.csv"
                df_batch.to_csv(filename,index=False)
                st.success(f"CSV opgeslagen: {filename}")
