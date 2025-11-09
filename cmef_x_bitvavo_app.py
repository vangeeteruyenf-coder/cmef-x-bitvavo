import streamlit as st
import requests
from datetime import datetime
import pandas as pd

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Predefined crypto mapping for CoinGecko IDs
COIN_SYMBOL_TO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "ADA": "cardano",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LTC": "litecoin",
    "LINK": "chainlink"
}

# Investment profile alpha values
PROFILE_ALPHA = {
    "Conservative": 0.7,
    "Balanced": 0.6,
    "Growth": 0.5
}

# ---------------------------
# Helper functions
# ---------------------------
def fetch_bitvavo_ticker(symbol):
    """Fetch live price & volume from Bitvavo"""
    market = f"{symbol}-EUR"
    url = f"{BITVAVO_API_URL}/ticker/24h?market={market}"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {
            "price": float(data.get("last", 0)),
            "volume": float(data.get("volume", 0))
        }
    except Exception:
        return None

def fetch_coingecko_data(symbol):
    """Fetch CoinGecko market data"""
    coin_id = COIN_SYMBOL_TO_ID.get(symbol.upper())
    if not coin_id:
        return None
    url = f"{COINGECKO_API_URL}/coins/{coin_id}?localization=false&market_data=true"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        market_data = data.get("market_data", {})
        community_data = data.get("community_data", {})
        return {
            "market_cap": market_data.get("market_cap", {}).get("eur", 0),
            "price_30d_change": market_data.get("price_change_percentage_30d", 0),
            "community_score": (
                (community_data.get("twitter_followers",0)/1e6)*0.5 +
                (community_data.get("reddit_subscribers",0)/1e5)*0.5
            )
        }
    except Exception:
        return None

# ---------------------------
# CMEF X Score computation
# ---------------------------
def compute_cmef_scores(ticker_data, coingecko_data, profile):
    alpha = PROFILE_ALPHA.get(profile, 0.6)

    # K-Score: Investment Quality
    market_cap_score = min(coingecko_data["market_cap"]/1e10,5) if coingecko_data else 0
    liquidity_score = min(ticker_data["volume"]/1e6,5) if ticker_data else 0
    perf_score = min(max(coingecko_data.get("price_30d_change",0)/10,0),5) if coingecko_data else 0
    K = round((market_cap_score + liquidity_score + perf_score)/3,2)

    # M-Score: Growth Potential
    dev_score = 2.5  # placeholder if no GitHub
    community_score = coingecko_data["community_score"] if coingecko_data else 0
    incentives_score = 2.5
    M = round((dev_score + community_score + incentives_score)/3,2)

    # OTS: alpha-weighted K/M
    OTS = round(K*alpha + M*(1-alpha),2)

    # R-Score
    R_tech = 0.5
    R_reg = 0.3
    R_fin = 0.4
    R = round(R_tech*0.4 + R_reg*0.35 + R_fin*0.25,2)

    # RAR: risk-adjusted
    RAR = round(OTS*(1-R),2)

    return {
        "K": K,
        "M": M,
        "OTS": OTS,
        "R": R,
        "RAR": RAR,
        "K_components": (market_cap_score, liquidity_score, perf_score),
        "M_components": (dev_score, community_score, incentives_score),
        "R_components": (R_tech, R_reg, R_fin)
    }

# ---------------------------
# Portfolio recommendation
# ---------------------------
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

# User inputs
profile = st.selectbox("Select investment profile", ["Conservative","Balanced","Growth"])
crypto_symbol = st.selectbox("Select cryptocurrency", list(COIN_SYMBOL_TO_ID.keys()))

if st.button("Generate CMEF X Report"):
    # Fetch live data
    ticker_data = fetch_bitvavo_ticker(crypto_symbol)
    coingecko_data = fetch_coingecko_data(crypto_symbol)

    debug_messages = []
    if ticker_data is None:
        debug_messages.append("Could not fetch Bitvavo ticker; using CoinGecko only if available.")
    if coingecko_data is None:
        debug_messages.append("Could not fetch CoinGecko data; some metrics may be defaulted.")

    # Check if we have at least one source
    if ticker_data is None and coingecko_data is None:
        st.error("Could not fetch live data. Check connection or select another coin.")
    else:
        # Compute scores
        scores = compute_cmef_scores(ticker_data, coingecko_data, profile)

        # Display live price / volume
        price_str = f"€{ticker_data['price']:.2f}" if ticker_data else "N/A"
        volume_str = f"€{ticker_data['volume']:.2f}" if ticker_data else "N/A"
        market_cap_str = f"€{coingecko_data['market_cap']:.2f}" if coingecko_data else "N/A"

        st.subheader("📊 Live Market Data")
        st.markdown(f"**Market:** {crypto_symbol}-EUR")
        st.markdown(f"**Current Price (EUR):** {price_str}")
        st.markdown(f"**24h Volume (EUR):** {volume_str}")
        st.markdown(f"**Market Cap (EUR):** {market_cap_str}")

        # Display CMEF X scores
        st.subheader("📈 CMEF X Scores")
        st.progress(scores["K"]/5)
        st.text(f"K-Score (Investment Quality): {scores['K']}/5")
        st.progress(scores["M"]/5)
        st.text(f"M-Score (Growth Potential): {scores['M']}/5")
        st.progress(scores["OTS"]/5)
        st.text(f"OTS (Overall Technical Strength): {scores['OTS']}/5")
        st.progress(scores["R"]/1)
        st.text(f"R-Score (Risk): {scores['R']}")
        st.progress(scores["RAR"]/5)
        st.text(f"RAR (Risk-adjusted): {scores['RAR']}/5")

        # Portfolio recommendation
        rec = portfolio_recommendation(scores["RAR"], profile)
        st.subheader("💼 Portfolio Recommendation")
        st.markdown(f"Suggested action for profile **{profile}**: **{rec}**")

        # Optional debug messages
        if debug_messages:
            with st.expander("🔧 Debug / Raw Data (for troubleshooting)"):
                for msg in debug_messages:
                    st.warning(msg)
                st.json({
                    "ticker_data": ticker_data,
                    "coingecko_data": coingecko_data,
                    "scores": scores
                })

        st.subheader("📖 CMEF X Report Generated")
        st.markdown(f"- Coin: {crypto_symbol}")
        st.markdown(f"- Profile: {profile} (α = {PROFILE_ALPHA[profile]})")
        st.markdown(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
