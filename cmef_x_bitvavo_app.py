# cmef_x_bitvavo_app.py
import streamlit as st
import pandas as pd
import requests
import time

BITVAVO_API_URL = "https://api.bitvavo.com/v2"

# --- Helper functies ---
def fetch_bitvavo_eur_pairs():
    """Haal alle beschikbare EUR-markten op"""
    try:
        url = f"{BITVAVO_API_URL}/markets"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        eur_pairs = [m['market'] for m in data if m['quote'] == 'EUR']
        return eur_pairs
    except Exception as e:
        st.error(f"Fout bij ophalen markets: {e}")
        return []

def fetch_bitvavo_price(market):
    """Haalt actuele prijs en volume op van een market"""
    try:
        url = f"{BITVAVO_API_URL}/{market}/ticker"
        response = requests.get(url)
        if response.status_code != 200:
            return None
        data = response.json()
        return {
            'price': float(data.get('last', 0)),
            'volume': float(data.get('volume', 0))
        }
    except Exception as e:
        st.error(f"Fout bij ophalen price voor {market}: {e}")
        return None

def normalize_metric(value, min_val, max_val):
    """Normaliseert een metric naar 0-5 score"""
    norm = (value - min_val) / (max_val - min_val)
    return min(max(norm,0),1) * 5

def calculate_scores(data, alpha):
    """Bereken K/M/OTS/R/RAR-scores"""
    if data is None:
        return 0,0,0,0,0
    K = normalize_metric(data['price'], 0.01, 60000)   # max fictieve prijs
    M = normalize_metric(data['volume'], 0.01, 1e9)    # max fictief volume
    OTS = K*alpha + M*(1-alpha)
    R = 0.5  # vereenvoudigd risico
    RAR = OTS*(1-R)
    return round(K,2), round(M,2), round(OTS,2), round(R,2), round(RAR,2)

# --- Streamlit UI ---
st.set_page_config(page_title="CMEF X Bitvavo Tool", layout="wide")
st.title("CMEF X Crypto Analysis Tool (Bitvavo)")

# --- Ophalen EUR-markets ---
with st.spinner("Ophalen van beschikbare EUR-markten..."):
    eur_pairs = fetch_bitvavo_eur_pairs()
    if not eur_pairs:
        st.error("Geen EUR-markten gevonden. Controleer Bitvavo API.")
        st.stop()

# Dropdown met exact market
market = st.selectbox("Kies een cryptocurrency (EUR-paar)", eur_pairs)

profile = st.selectbox("Kies profiel", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7, "Balanced":0.6, "Growth":0.5}
alpha = alpha_dict[profile]

# --- Analyse knop ---
if st.button("Analyseer Coin"):
    st.info(f"Ophalen van prijs/volume voor {market}…")
    data = fetch_bitvavo_price(market)
    time.sleep(0.5)  # API-limiet pauze

    # --- Debug / foutlocatie ---
    if data is None:
        st.error(f"⚠️ Data kon niet worden opgehaald voor {market}. Mogelijke oorzaken:")
        st.write("- Coin heeft geen EUR-paar (controleer Bitvavo)")
        st.write("- API-limiet bereikt")
        st.write("- Tijdelijke netwerkfout of fout in API response")
        st.stop()

    if data['price'] == 0:
        st.error(f"⚠️ Prijs is 0 voor {market}. Data mogelijk incompleet.")
        st.write("Raw API-response:", data)
        st.stop()

    # Debug info tonen
    st.write("✅ Raw data:", data)

    # --- Scores berekenen ---
    try:
        K, M, OTS, R, RAR = calculate_scores(data, alpha)
    except Exception as e:
        st.error(f"Fout bij berekenen scores: {e}")
        st.stop()

    st.success("Analyse klaar!")

    # --- Tabel ---
    df_scores = pd.DataFrame({
        'Metric': ['K-Score','M-Score','OTS','R-Score','RAR-Score'],
        'Value': [K, M, OTS, R, RAR]
    })
    st.table(df_scores)

    # --- Visualisatie ---
    st.subheader("Visualisatie Scores")
    st.write("K-Score:")
    st.progress(min(int(K/5*100),100))
    st.write("M-Score:")
    st.progress(min(int(M/5*100),100))
    st.write("RAR-Score:")
    st.progress(min(int(RAR/5*100),100))

    # --- CSV-export ---
    if st.button("Exporteer naar CSV"):
        filename = f"{market.replace('-','_')}_cmef_x_scores.csv"
        df_scores.to_csv(filename, index=False)
        st.success(f"CSV opgeslagen: {filename}")
