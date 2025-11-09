import streamlit as st
import requests
from datetime import datetime
import pandas as pd

# ---------------------------
# Configuration
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Supported coins mapping: full name -> Bitvavo ticker
COINS = {
    "Bitcoin": "BTC-EUR",
    "Ethereum": "ETH-EUR",
    "Cardano": "ADA-EUR",
    "Aave": "AAVE-EUR",
    "Polygon": "MATIC-EUR"
}

# ---------------------------
# Helper functions
# ---------------------------
def fetch_bitvavo_ticker(ticker):
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{ticker}/ticker", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {
            "price": float(data["last"]),
            "volume": float(data["volume"])
        }
    except:
        return None

def fetch_coingecko_data(coin_name):
    # Resolve coin ID automatically
    try:
        resp = requests.get(f"{COINGECKO_API_URL}/coins/list", timeout=5)
        coins_list = resp.json()
        coin_id = None
        for c in coins_list:
            if c['name'].lower() == coin_name.lower():
                coin_id = c['id']
                break
        if not coin_id:
            return None, None

        market_resp = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", timeout=5)
        market_data = market_resp.json()
        return coin_id, market_data
    except:
        return None, None

def compute_K_score(market_data, price, volume):
    # Simplified weighted scoring for demonstration
    scores = {
        "Market Cap": min(market_data.get('market_data', {}).get('market_cap', {}).get('eur',0)/1e12,5),
        "Liquidity": min(volume/1e9,5),
        "30d Perf": min(abs(market_data.get('market_data', {}).get('price_change_percentage_30d',0))/10,5)
    }
    K = sum([v for v in scores.values()])/len(scores)
    return K, scores

def compute_M_score(market_data):
    # Placeholder scores (community, developer activity, incentives)
    scores = {
        "Dev": 2.5,
        "Community": min((market_data.get('community_data', {}).get('twitter_followers',0))/1e6,5),
        "Incentives": 2.5
    }
    M = sum([v for v in scores.values()])/len(scores)
    return M, scores

def compute_R_score():
    scores = {
        "Technical": 0.5,
        "Regulatory": 0.3,
        "Financial": 0.4
    }
    R = sum([scores['Technical']*0.4, scores['Regulatory']*0.35, scores['Financial']*0.25])
    R /= 5
    return R, scores

def compute_OTS_RAR(K, M, alpha, R):
    OTS = K*alpha + M*(1-alpha)
    RAR = OTS*(1-R)
    return OTS, RAR

def portfolio_recommendation(RAR, profile):
    if RAR >= 65:
        scale = {"Conservative":"Core","Balanced":"Core","Growth":"Core"}
    elif RAR >=50:
        scale = {"Conservative":"Tactical","Balanced":"Core","Growth":"Core"}
    elif RAR >=35:
        scale = {"Conservative":"Small/Cautious","Balanced":"Tactical","Growth":"Core"}
    elif RAR >=20:
        scale = {"Conservative":"Avoid","Balanced":"Small/Cautious","Growth":"Tactical"}
    else:
        scale = {"Conservative":"Avoid","Balanced":"Avoid","Growth":"Small/Cautious"}
    return scale.get(profile,"Cautious")

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X — Free Crypto Analysis Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard")

# Step 1: User Inputs
coin_name = st.selectbox("Select Cryptocurrency:", list(COINS.keys()))
profile = st.selectbox("Select Investment Profile:", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.5,"Growth":0.3}
alpha = alpha_dict[profile]

if st.button("Generate CMEF X Report"):
    ticker = COINS[coin_name]
    st.info(f"Fetching live market data for {coin_name} ({ticker})...")

    # Fetch live data
    ticker_data = fetch_bitvavo_ticker(ticker)
    coin_id, market_data = fetch_coingecko_data(coin_name)

    if not ticker_data or not market_data:
        st.error(f"Could not fetch live data for {coin_name}. Check your connection or select another coin.")
    else:
        price = ticker_data['price']
        volume = ticker_data['volume']

        # Compute scores
        K, K_components = compute_K_score(market_data, price, volume)
        M, M_components = compute_M_score(market_data)
        R, R_components = compute_R_score()
        OTS, RAR = compute_OTS_RAR(K*20, M*20, alpha, R)  # scale K/M to % for OTS/RAR

        # Portfolio recommendation
        recommendation = portfolio_recommendation(RAR, profile)

        # ---------------------------
        # Display Report
        # ---------------------------
        st.header(f"📊 CMEF X Scores & Analysis — {coin_name}")
        st.subheader("Live Market Data")
        st.markdown(f"- **Ticker:** {ticker}")
        st.markdown(f"- **Current Price (EUR):** €{price:,.2f}")
        st.markdown(f"- **24h Volume (EUR):** €{volume:,.2f}")
        st.markdown(f"- **CoinGecko Market Cap (EUR):** €{market_data.get('market_data', {}).get('market_cap', {}).get('eur',0):,.2f}")

        st.subheader("K-Score (Investment Quality)")
        st.markdown(f"- **Score:** {K:.2f}/5")
        st.markdown("- **Definition:** Measures the current investment quality based on market cap, liquidity, and recent performance.")
        st.markdown(f"- **Components & rationale:** {K_components}")

        st.subheader("M-Score (Growth Potential)")
        st.markdown(f"- **Score:** {M:.2f}/5")
        st.markdown("- **Definition:** Measures long-term growth potential based on developer activity, community strength, and incentives.")
        st.markdown(f"- **Components & rationale:** {M_components}")

        st.subheader("OTS & RAR")
        st.markdown(f"- **OTS (Overall Technical Strength):** {OTS:.2f}/100")
        st.markdown(f"- **R-Score (Risk):** {R:.2f} (0..1)")
        st.markdown(f"- **RAR (Risk-Adjusted Return):** {RAR:.2f}/100")

        st.subheader("Portfolio Recommendation")
        st.markdown(f"- Suggested action for profile {profile}: {recommendation}")

        st.subheader("Analytical Thesis")
        st.markdown(f"- Bitcoin shows strong K (~{K:.2f}) and M (~{M:.2f}) indicating solid quality and potential.")
        st.markdown(f"- Risk factor R={R:.2f} reduces effective RAR to {RAR:.2f}. Caution advised for profile {profile}.")

        st.subheader("Report Generated")
        st.markdown(f"- **Profile α weighting:** {alpha}")
        st.markdown(f"- **Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        st.expander("🔧 Debug / Raw Data", expanded=False)
        st.json({
            "Bitvavo Ticker Data": ticker_data,
            "CoinGecko Market Data": {k: market_data.get(k, None) for k in ["market_data","community_data"]},
            "K Components": K_components,
            "M Components": M_components,
            "R Components": R_components
        })
