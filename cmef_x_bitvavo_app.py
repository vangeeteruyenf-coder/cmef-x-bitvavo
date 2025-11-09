import streamlit as st
import requests
import random
from datetime import datetime
import pandas as pd

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
GITHUB_API_URL = "https://api.github.com/repos"

# ---------------------------
# Helper functions
# ---------------------------
@st.cache_data(ttl=300)
def fetch_eur_markets():
    """Get all EUR markets from Bitvavo."""
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m['market'] for m in markets if m['quote'] == 'EUR']
        return eur_markets
    except Exception as e:
        st.error(f"Could not fetch Bitvavo markets: {e}")
        return []

def fetch_ticker(market):
    """Get live price and volume from Bitvavo."""
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

def fetch_historical_prices(market, interval="1d", limit=30):
    """Fetch historical candle data from Bitvavo."""
    try:
        url = f"{BITVAVO_API_URL}/{market}/candles/{interval}?limit={limit}"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
        return df
    except:
        return None

def fetch_github_metrics(repo_full_name):
    """Fetch public GitHub metrics (stars, forks, watchers)."""
    try:
        resp = requests.get(f"{GITHUB_API_URL}/{repo_full_name}", timeout=5)
        if resp.status_code != 200:
            return {'stars':0,'forks':0,'watchers':0,'open_issues':0}
        data = resp.json()
        return {
            'stars': data.get('stargazers_count',0),
            'forks': data.get('forks_count',0),
            'watchers': data.get('subscribers_count',0),
            'open_issues': data.get('open_issues_count',0)
        }
    except:
        return {'stars':0,'forks':0,'watchers':0,'open_issues':0}

# ---------------------------
# CMEF X Score Calculation
# ---------------------------
def compute_scores(data, alpha, github_metrics):
    """Calculate K, M, OTS, R, RAR scores."""
    price_score = min(max(data['price']/60000,0),1)*5
    volume_score = min(max(data['volume']/1e9,0),1)*5
    K = round(0.6*price_score + 0.4*volume_score,2)

    github_score = min((github_metrics['stars']/5000)*5,5)
    social_score = random.uniform(2.5,5)  # placeholder for social/community metrics
    M = round(0.6*github_score + 0.4*social_score,2)

    OTS = round(K*alpha + M*(1-alpha),2)

    R_tech = 0.5  # placeholder for technical risk
    R_reg = 0.3   # placeholder for regulatory risk
    R_fin = min((data['price']/60000),1)*0.5  # price volatility indicator
    R = round(R_tech*0.4 + R_reg*0.35 + R_fin*0.25,2)

    RAR = round(OTS*(1-R),2)

    rationale = {
        'K_Price': price_score,
        'K_Volume': volume_score,
        'M_GitHub': github_score,
        'M_Social': social_score,
        'R_Tech': R_tech,
        'R_Reg': R_reg,
        'R_Fin': R_fin
    }

    return {'K':K,'M':M,'OTS':OTS,'R':R,'RAR':RAR,'Rationale':rationale}

# ---------------------------
# Portfolio recommendation
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
# Visualization
# ---------------------------
def display_progress_bars(scores):
    st.subheader("📊 Score Progress Bars (0-100%)")
    st.text("K-Score")
    st.progress(int(scores['K'] / 5 * 100))
    st.text("M-Score")
    st.progress(int(scores['M'] / 5 * 100))
    st.text("OTS")
    st.progress(int(scores['OTS'] / 5 * 100))
    st.text("R-Score (Risk)")
    st.progress(int(scores['R'] / 5 * 100))
    st.text("RAR-Score")
    st.progress(int(scores['RAR'] / 5 * 100))

def display_kpi_cards(scores, rec, price):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Market Price (€)", f"{price:.2f}")
    col2.metric("K-Score", scores['K'])
    col3.metric("M-Score", scores['M'])
    col4.metric("OTS", scores['OTS'])
    col5.metric("R-Score", scores['R'])
    col6.metric("RAR", f"{scores['RAR']} ({rec})")

def display_price_chart(df):
    st.subheader("📈 Historical Price (Last 30 days)")
    st.line_chart(df.set_index('timestamp')['close'])

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X Free Crypto Tool", layout="wide")
st.title("CMEF X Free Crypto Analysis Tool - Bitvavo Edition")

st.write("**Analysis Date & Time:**", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

# Profile selection
profile = st.selectbox("Select your investment profile", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

# Coin selection
eur_markets = fetch_eur_markets()
market_input = st.selectbox("Select cryptocurrency (EUR market)", eur_markets)

# GitHub repo input (optional)
repo_input = st.text_input("Enter GitHub repo name (e.g., bitcoin/bitcoin)", "bitcoin/bitcoin")

# Analyze button
if st.button("Analyze coin"):
    ticker = fetch_ticker(market_input)
    if ticker:
        github_metrics = fetch_github_metrics(repo_input)
        scores = compute_scores(ticker, alpha, github_metrics)
        rec = portfolio_recommendation(scores['RAR'], profile)
        
        # KPI cards
        st.subheader("📊 CMEF X Scores Overview")
        display_kpi_cards(scores, rec, ticker['price'])
        
        # Progress bars
        display_progress_bars(scores)
        
        # Historical price chart
        price_df = fetch_historical_prices(market_input)
        if price_df is not None:
            display_price_chart(price_df)
        
        # Detail explanation
        st.subheader("📖 Coin-specific explanation")
        r = scores['Rationale']
        st.markdown(f"- **K-Score**: price ({r['K_Price']:.2f}) & volume ({r['K_Volume']:.2f})")
        st.markdown(f"- **M-Score**: GitHub stars ({r['M_GitHub']:.2f}), social indicator ({r['M_Social']:.2f})")
        st.markdown(f"- **OTS**: Overall Technical Strength = {scores['OTS']:.2f}")
        st.markdown(f"- **R-Score**: Risk = {scores['R']:.2f}")
        st.markdown(f"- **RAR-Score**: Risk-adjusted = {scores['RAR']:.2f}")
        st.markdown(f"- **Portfolio Recommendation**: {rec}")
    else:
        st.error("Could not fetch data from Bitvavo. Check internet connection or select another coin.")
