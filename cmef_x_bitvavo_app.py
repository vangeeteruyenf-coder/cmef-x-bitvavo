# cmef_x_bitvavo_app.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

# --- Configuratie ---
BITVAVO_API_URL = "https://api.bitvavo.com/v2"

# --- Helper functies ---
def fetch_bitvavo_assets():
    """Haalt alle beschikbare Bitvavo coins op"""
    try:
        url = f"{BITVAVO_API_URL}/assets"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        # Retouneer alleen symbolen van coins
        return [asset['symbol'] for asset in data]
    except:
        return []

def fetch_bitvavo_price(symbol):
    """Haalt actuele prijs en volume op van een coin"""
    try:
        url = f"{BITVAVO_API_URL}/{symbol}-EUR/ticker"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return {
            'price': float(data['last']),
            'volume': float(data['volume'])
        }
    except:
        return None

def normalize_metric(value, min_val, max_val):
    """Normaliseert een metric naar 0-5 score"""
    norm = (value - min_val) / (max_val - min_val)
    return min(max(norm,0),1) * 5

def calculate_scores(data, alpha):
    """Bereken K/M/OTS/R/RAR-scores"""
    if data is None:
        return 0,0,0,0,0
    K = normalize_metric(data['price'], 0.01, 60000)   # fictieve max prijs
    M = normalize_metric(data['volume'], 0.01, 1e9)    # fictieve max volume
    OTS = K*alpha + M*(1-alpha)
    R = 0.5  # vereenvoudigd risico
    RAR = OTS*(1-R)
    return round(K,2), round(M,2), round(OTS,2), round(R,2), round(RAR,2)

# --- Streamlit UI ---
st.set_page_config(page_title="CMEF X Bitvavo Tool", layout="wide")
st.title("CMEF X Crypto Analysis Tool (Bitvavo)")

# Lijst van coins ophalen
with st.spinner("Ophalen van beschikbare Bitvavo coins..."):
    symbols = fetch_bitvavo_assets()

if not symbols:
    st.error("Kan Bitvavo data niet ophalen. Controleer internetverbinding.")
else:
    st.success(f"{len(symbols)} coins gevonden.")
    coin = st.selectbox("Kies een cryptocurrency (Bitvavo)", symbols)
    profile = st.selectbox("Kies profiel", ["Conservative","Balanced","Growth"])

    # Profiel alpha mapping
    alpha_dict = {"Conservative":0.7, "Balanced":0.6, "Growth":0.5}
    alpha = alpha_dict[profile]

    if st.button("Analyseer Coin"):
        st.info(f"Ophalen van prijs/volume voor {coin}…")
        data = fetch_bitvavo_price(coin)
        time.sleep(0.5)  # korte pauze

        # Scores berekenen
        K, M, OTS, R, RAR = calculate_scores(data, alpha)
        st.success("Analyse klaar!")

        # Tabel tonen
        df_scores = pd.DataFrame({
            'Metric': ['K-Score','M-Score','OTS','R-Score','RAR-Score'],
            'Value': [K, M, OTS, R, RAR]
        })
        st.table(df_scores)

        # Progress bars
        st.subheader("Visualisatie Scores")
        st.write("K-Score:")
        st.progress(min(int(K/5*100),100))
        st.write("M-Score:")
        st.progress(min(int(M/5*100),100))
        st.write("RAR-Score:")
        st.progress(min(int(RAR/5*100),100))

        # CSV-export optie
        if st.button("Exporteer naar CSV"):
            filename = f"{coin}_cmef_x_scores.csv"
            df_scores.to_csv(filename, index=False)
            st.success(f"CSV opgeslagen: {filename}")
