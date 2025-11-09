import streamlit as st
import requests
from datetime import datetime

# ---------------------------
# Configuration
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
        eur_markets = {m['market']: m['base'] for m in markets if m['quote']=='EUR'}
        return eur_markets
    except Exception as e:
        st.error(f"Could not fetch Bitvavo markets: {e}")
        return {}

def fetch_bitvavo_ticker(market):
    """Fetch live price and volume from Bitvavo for a market."""
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
    except Exception as e:
        st.warning(f"Bitvavo ticker fetch error for {market}: {e}")
        return None

def fetch_coingecko_coin(coin_id):
    """Fetch CoinGecko data for a coin."""
    try:
        url = f"{COINGECKO_API_URL}/coins/{coin_id}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        market_data = data.get('market_data', {})
        social_data = data.get('community_data', {})
        return {
            'market_cap': market_data.get('market_cap', {}).get('eur', 0),
            'circulating_supply': market_data.get('circulating_supply', 0),
            'price_30d_change': market_data.get('price_change_percentage_30d', 0),
            'twitter_followers': social_data.get('twitter_followers', 0),
            'reddit_subscribers': social_data.get('reddit_subscribers', 0),
        }
    except Exception as e:
        st.warning(f"CoinGecko fetch error for {coin_id}: {e}")
        return None

# ---------------------------
# CMEF X Calculations
# ---------------------------

def calculate_k_score(market_cap, liquidity, perf_30d):
    """Compute simplified K-Score"""
    # Normalize scores 0-5
    mc_score = min(market_cap/1e12 * 5, 5)
    liq_score = min(liquidity/1e9 * 5, 5)
    perf_score = min(max(perf_30d/10, 0), 5)
    k_score = round((mc_score*0.4 + liq_score*0.3 + perf_score*0.3), 2)
    components = {'Market Cap': mc_score, 'Liquidity': liq_score, '30d Perf': perf_score}
    return k_score, components

def calculate_m_score(dev_activity, community, incentives):
    """Compute simplified M-Score"""
    m_score = round((dev_activity*0.4 + community*0.3 + incentives*0.3), 2)
    components = {'Dev': dev_activity, 'Community': community, 'Incentives': incentives}
    return m_score, components

def calculate_r_score(tech, reg, fin):
    """Compute R-Score 0-1"""
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

# Sidebar inputs
st.sidebar.header("Inputs")
profile = st.sidebar.selectbox("Select investment profile", ["Conservative", "Balanced", "Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

# Fetch markets and create selection
markets = fetch_bitvavo_markets()
if not markets:
    st.stop()

coin_name_to_ticker = {v:k for k,v in markets.items()}  # Name -> Market
selected_coin_name = st.sidebar.selectbox("Select cryptocurrency", list(coin_name_to_ticker.keys()))
market_ticker = coin_name_to_ticker[selected_coin_name]

# Generate button
if st.sidebar.button("Generate CMEF X Report"):

    st.subheader(f"Fetching live data for {selected_coin_name} ({market_ticker})...")
    ticker_data = fetch_bitvavo_ticker(market_ticker)
    if not ticker_data:
        st.error(f"Could not fetch live data for {selected_coin_name}. Check your connection or select another coin.")
        st.stop()
    
    # Resolve CoinGecko ID (simple match)
    cg_resp = requests.get(f"{COINGECKO_API_URL}/coins/list")
    cg_list = cg_resp.json()
    coin_id = next((c['id'] for c in cg_list if c['symbol'].lower()==market_ticker.split('-')[0].lower()), None)
    cg_data = fetch_coingecko_coin(coin_id) if coin_id else None
    
    st.subheader("📊 Live Market Data")
    st.markdown(f"**Price (EUR):** €{ticker_data['price']:.2f}")
    st.markdown(f"**24h Volume:** {ticker_data['volume']:.2f}")
    if cg_data:
        st.markdown(f"**Market Cap:** €{cg_data['market_cap']:.2f}")
        perf_30d = cg_data['price_30d_change'] or 0
    else:
        st.markdown("**Market Cap:** N/A")
        perf_30d = 0

    liquidity = ticker_data['volume']

    # Compute scores
    k_score, k_components = calculate_k_score(cg_data['market_cap'] if cg_data else 0, liquidity, perf_30d)
    m_score, m_components = calculate_m_score(dev_activity=2.5,  # placeholder
                                             community=(cg_data['twitter_followers'] + cg_data['reddit_subscribers'])/1e6 if cg_data else 0,
                                             incentives=2.5)
    r_score, r_components = calculate_r_score(tech=1.0, reg=2.5, fin=4.0)
    ots, rar = calculate_ots_rar(k_score, m_score, r_score, alpha)
    recommendation = portfolio_recommendation(rar, profile)

    st.subheader("📊 CMEF X Scores & Analysis")
    st.markdown(f"**K-Score (Investment Quality):** {k_score}/5")
    st.markdown(f"Definition: Measures the current investment quality based on market cap, liquidity, and recent performance.")
    st.markdown(f"Rationale for {selected_coin_name}: {k_components}")

    st.markdown(f"**M-Score (Growth Potential):** {m_score}/5")
    st.markdown(f"Definition: Measures long-term growth potential based on developer activity, community strength, and incentives.")
    st.markdown(f"Rationale for {selected_coin_name}: {m_components}")

    st.markdown(f"**OTS (Overall Technical Strength):** {ots}/5")
    st.markdown(f"Definition: α-weighted combination of K-Score and M-Score based on investment profile.")

    st.markdown(f"**R-Score (Risk):** {r_score} (0..1)")
    st.markdown(f"Definition: Measures combined technical, regulatory, and financial risk.")
    st.markdown(f"Components: {r_components}")

    st.markdown(f"**RAR (Risk-Adjusted Return):** {rar}/5")
    st.markdown(f"Definition: Risk-adjusted score, combines OTS with R-Score to adjust for potential risk.")

    st.subheader("💼 Portfolio Recommendation")
    st.markdown(f"Suggested action for profile {profile}: {recommendation}")

    st.subheader("📖 Full CMEF X Structured Report")
    st.markdown(f"- Coin: {selected_coin_name}")
    st.markdown(f"- Market Ticker: {market_ticker}")
    st.markdown(f"- Profile: {profile} (α = {alpha})")
    st.markdown(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown(f"- K-Score: {k_score}/5 | Components: {k_components}")
    st.markdown(f"- M-Score: {m_score}/5 | Components: {m_components}")
    st.markdown(f"- OTS: {ots}/5")
    st.markdown(f"- R-Score: {r_score} | Components: {r_components}")
    st.markdown(f"- RAR: {rar}/5")
    st.markdown(f"- Portfolio Recommendation: {recommendation}")

    st.subheader("🔧 Debug / Raw Data (hidden unless issues occur)")
    st.info({
        'Bitvavo Ticker Data': ticker_data,
        'CoinGecko Data': cg_data,
        'CoinGecko ID': coin_id
    })
