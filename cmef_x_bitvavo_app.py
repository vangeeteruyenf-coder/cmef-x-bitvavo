# cmef_x_bitvavo_full.py
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
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets")
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m['market'] for m in markets if m['quote']=='EUR']
        return eur_markets
    except Exception as e:
        st.error(f"Kan Bitvavo markets niet ophalen: {e}")
        return []

def fetch_ticker(market):
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{market}/ticker")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {'price': float(data.get('last',0)), 'volume': float(data.get('volume',0))}
    except Exception as e:
        st.error(f"Fout bij ophalen ticker {market}: {e}")
        return None

def normalize(value, min_val, max_val):
    return min(max((value - min_val)/(max_val - min_val),0),1)*5

def compute_scores(data, alpha):
    if not data or data['price']==0:
        return {'K':0,'M':0,'OTS':0,'R':0,'RAR':0}
    K = normalize(data['price'],0.01,60000)
    M = normalize(data['volume'],0.01,1e9)
    OTS = K*alpha + M*(1-alpha)
    R = 0.5  # vereenvoudigd risico
    RAR = OTS*(1-R)
    return {'K':round(K,2),'M':round(M,2),'OTS':round(OTS,2),'R':round(R,2),'RAR':round(RAR,2)}

def batch_analyze(markets, alpha):
    results=[]
    for market in markets:
        data=fetch_ticker(market)
        if not data:
            st.warning(f"⚠️ Kon data niet ophalen voor {market}")
            continue
        scores=compute_scores(data, alpha)
        results.append({
            'Market':market,
            'Price':data['price'],
            'Volume':data['volume'],
            'K-Score':scores['K'],
            'M-Score':scores['M'],
            'OTS':scores['OTS'],
            'R-Score':scores['R'],
            'RAR-Score':scores['RAR'],
            # CMEF X AI placeholders:
            'AI_Profile':'[AI]',
            'AI_Rationale':'[AI: rationale]',
            'K-Criteria':'[AI]',
            'M-Criteria':'[AI]',
            'Risk_Criteria':'[AI]'
        })
        time.sleep(0.2)
    return pd.DataFrame(results)

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X Bitvavo Full Tool", layout="wide")
st.title("CMEF X Crypto Analysis Tool (Bitvavo)")

# Datum & tijd
st.write("**Analyse datum & tijd:**", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

# Profiel selectie
profile=st.selectbox("Kies profiel", ["Conservative","Balanced","Growth"])
alpha_dict={"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha=alpha_dict[profile]

# EUR-markets ophalen
with st.spinner("Ophalen van EUR-markets..."):
    eur_markets=fetch_eur_markets()
    if not eur_markets:
        st.error("Geen EUR-markets gevonden. Controleer Bitvavo API.")
        st.stop()

# Analyse modus
mode=st.radio("Analyse modus", ["Enkele coin","Batch alle coins"])

if mode=="Enkele coin":
    market=st.selectbox("Kies een cryptocurrency (EUR-paar)",eur_markets)
    if st.button("Analyseer Coin"):
        data=fetch_ticker(market)
        if not data or data['price']==0:
            st.error(f"⚠️ Kon data niet ophalen voor {market}. Raw data: {data}")
            st.stop()
        st.write("✅ Raw data:",data)
        scores=compute_scores(data,alpha)
        st.success("Analyse klaar!")

        # CMEF X placeholders
        st.subheader("CMEF X AI-Ready Crypto Analysis")
        st.write(f"Profile: {profile} | α={alpha}")
        st.write("K-Score:",scores['K'],"M-Score:",scores['M'],"OTS:",scores['OTS'],
                 "R-Score:",scores['R'],"RAR-Score:",scores['RAR'])
        st.write("Section A & B: [AI placeholders for detailed criteria]")
        st.write("Risk Analysis: [AI placeholders]")
        st.write("Portfolio Recommendation: [AI placeholders]")

        # Visualisatie
        st.subheader("Visualisatie Scores")
        for metric in ['K','M','RAR']:
            st.write(f"{metric}-Score:")
            st.progress(min(int(scores[metric]/5*100),100))

        # CSV-export
        if st.button("Exporteer naar CSV"):
            df=pd.DataFrame([scores])
            df.index=[market]
            filename=f"{market.replace('-','_')}_cmef_x_full.csv"
            df.to_csv(filename)
            st.success(f"CSV opgeslagen: {filename}")

else: # Batch modus
    if st.button("Batch analyseer alle EUR-coins"):
        with st.spinner("Batch-analyse gestart... kan enkele seconden duren"):
            df_batch=batch_analyze(eur_markets,alpha)
        if df_batch.empty:
            st.error("Geen resultaten opgehaald.")
        else:
            st.success(f"Batch-analyse klaar! {len(df_batch)} coins geanalyseerd.")
            st.dataframe(df_batch.sort_values('RAR-Score',ascending=False))
            # CSV-export
            if st.button("Exporteer batch naar CSV"):
                filename="cmef_x_batch_full.csv"
                df_batch.to_csv(filename,index=False)
                st.success(f"CSV opgeslagen: {filename}")
