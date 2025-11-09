import streamlit as st
import requests
from datetime import datetime

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# ---------------------------
# Helper Functions
# ---------------------------

def fetch_bitvavo_markets():
    """Fetch all EUR markets from Bitvavo."""
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = {m['name']: m['market'] for m in markets if m['quote'] == 'EUR'}
        return eur_markets
    except Exception as e:
        st.error(f"Could not fetch Bitvavo markets: {e}")
        return {}

def fetch_bitvavo_ticker(market):
    """Fetch live price and volume from Bitvavo."""
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{market}/ticker", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {
            'price': float(data['last']),
            'volume': float(data['volume'])
        }
    except:
        return None

def fetch_coingecko_coin(symbol):
    """Resolve CoinGecko ID by symbol and fetch data."""
    try:
        resp = requests.get(f"{COINGECKO_API_URL}/coins/list", timeout=5)
        resp.raise_for_status()
        coins = resp.json()
        coin_id = next((c['id'] for c in coins if c['symbol'].lower() == symbol.lower()), None)
        if not coin_id:
            return None
        data_resp = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", timeout=5)
        data_resp.raise_for_status()
        data = data_resp.json()
        market_data = data.get('market_data', {})
        social_data = data.get('community_data', {})
        return {
            'market_cap': market_data.get('market_cap', {}).get('eur', 0),
            'price_30d_change': market_data.get('price_change_percentage_30d', 0),
            'twitter_followers': social_data.get('twitter_followers', 0),
            'reddit_subscribers': social_data.get('reddit_subscribers', 0)
        }
    except:
        return None

# ---------------------------
# CMEF X Calculations
# ---------------------------

def calculate_k_score(market_cap, liquidity, perf_30d):
    mc_score = min(market_cap / 1e12 * 5, 5)
    liq_score = min(liquidity / 1e9 * 5, 5)
    perf_score = min(max(perf_30d / 10, 0), 5)
    k_score = round((mc_score*0.4 + liq_score*0.3 + perf_score*0.3), 2)
    components = {'Market Cap': mc_score, 'Liquidity': liq_score, '30d Perf': perf_score}
    return k_score, components

def calculate_m_score(dev_activity, community, incentives):
    m_score = round((dev_activity*0.4 + community*0.3 + incentives*0.3), 2)
    components = {'Dev': dev_activity, 'Community': community, 'Incentives': incentives}
    return m_score, components

def calculate_r_score(tech, reg, fin):
    r_score = round((tech*0.4 + reg*0.35 + fin*0.25)/5, 3)
    components = {'Tech': tech, 'Reg': reg, 'Fin': fin}
    return r_score, components

def calculate_ots_rar(k_score, m_score, r_score, alpha):
    ots = round(k_score*alpha + m_score*(1-alpha), 2)
    rar = round(ots*(1 - r_score), 2)
    return ots, rar

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
# Streamlit UI
# ---------------------------

st.set_page_config(page_title="CMEF X — Free Crypto Analysis Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard")

st.sidebar.header("Inputs")
profile = st.sidebar.selectbox("Select investment profile", ["Conservative", "Balanced", "Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

markets = fetch_bitvavo_markets()
if not markets:
    st.stop()

coin_name_to_ticker = markets
selected_coin_name = st.sidebar.selectbox("Select cryptocurrency", list(coin_name_to_ticker.keys()))
market_ticker = coin_name_to_ticker[selected_coin_name]

if st.sidebar.button("Generate CMEF X Report"):

    st.subheader(f"Fetching live data for {selected_coin_name} ({market_ticker})...")
    ticker_data = fetch_bitvavo_ticker(market_ticker)
    if not ticker_data:
        st.warning(f"Could not fetch live data for {selected_coin_name}. Will generate report with placeholders.")
        ticker_data = {'price':0, 'volume':0}

    cg_data = fetch_coingecko_coin(market_ticker.split('-')[0])
    if not cg_data:
        st.info(f"CoinGecko data not available for {selected_coin_name}. Using placeholders.")
        cg_data = {'market_cap':0,'price_30d_change':0,'twitter_followers':0,'reddit_subscribers':0}

    liquidity = ticker_data['volume']
    perf_30d = cg_data.get('price_30d_change',0)
    market_cap = cg_data.get('market_cap',0)

    k_score, k_components = calculate_k_score(market_cap, liquidity, perf_30d)
    m_score, m_components = calculate_m_score(dev_activity=2.5, 
                                             community=(cg_data['twitter_followers']+cg_data['reddit_subscribers'])/1e6,
                                             incentives=2.5)
    r_score, r_components = calculate_r_score(tech=1.0, reg=2.5, fin=4.0)
    ots, rar = calculate_ots_rar(k_score, m_score, r_score, alpha)
    recommendation = portfolio_recommendation(rar, profile)

    st.subheader("📊 CMEF X Scores & Analysis")
    st.markdown(f"**K-Score (Investment Quality):** {k_score}/5  \nDefinition: Current investment quality based on market cap, liquidity, performance.  \nRationale: {k_components}")
    st.markdown(f"**M-Score (Growth Potential):** {m_score}/5  \nDefinition: Growth potential based on dev activity, community, incentives.  \nRationale: {m_components}")
    st.markdown(f"**OTS (Overall Technical Strength):** {ots}/5  \nDefinition: α-weighted combination of K & M.")
    st.markdown(f"**R-Score (Risk):** {r_score} (0..1)  \nComponents: {r_components}")
    st.markdown(f"**RAR (Risk-Adjusted Return):** {rar}/5")
    st.subheader("💼 Portfolio Recommendation")
    st.markdown(f"Suggested action for profile {profile}: {recommendation}")
