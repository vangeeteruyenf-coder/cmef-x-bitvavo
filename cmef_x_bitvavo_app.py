import streamlit as st
import requests
from datetime import datetime
import pandas as pd

# ---------------------------
# Config / Mapping
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Cryptocurrency mapping: full name -> symbol -> CoinGecko ID
CRYPTO_MAP = {
    "Bitcoin": {"symbol": "BTC", "coingecko_id": "bitcoin"},
    "Ethereum": {"symbol": "ETH", "coingecko_id": "ethereum"},
    "Cardano": {"symbol": "ADA", "coingecko_id": "cardano"},
    "Binance Coin": {"symbol": "BNB", "coingecko_id": "binancecoin"},
    "Solana": {"symbol": "SOL", "coingecko_id": "solana"},
    "Ripple": {"symbol": "XRP", "coingecko_id": "ripple"},
    "Dogecoin": {"symbol": "DOGE", "coingecko_id": "dogecoin"},
    "Polkadot": {"symbol": "DOT", "coingecko_id": "polkadot"},
    "Litecoin": {"symbol": "LTC", "coingecko_id": "litecoin"},
    "Chainlink": {"symbol": "LINK", "coingecko_id": "chainlink"}
}

# Investment profile alpha values
PROFILE_ALPHA = {"Conservative": 0.7, "Balanced": 0.6, "Growth": 0.5}

# ---------------------------
# Helper functions
# ---------------------------
def fetch_bitvavo_ticker(symbol):
    market = f"{symbol}-EUR"
    url = f"{BITVAVO_API_URL}/ticker/24h?market={market}"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {"price": float(data.get("last", 0)), "volume": float(data.get("volume",0))}
    except Exception:
        return None

def fetch_coingecko_data(coin_id):
    url = f"{COINGECKO_API_URL}/coins/{coin_id}?localization=false&market_data=true&community_data=true"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        market_data = data.get("market_data", {})
        community_data = data.get("community_data", {})
        return {
            "market_cap": market_data.get("market_cap", {}).get("eur", 0),
            "price_30d_change": market_data.get("price_change_percentage_30d", 0),
            "community_score": ((community_data.get("twitter_followers",0)/1e6)*0.5 + (community_data.get("reddit_subscribers",0)/1e5)*0.5)
        }
    except Exception:
        return None

def compute_cmef_scores(ticker_data, coingecko_data, profile):
    alpha = PROFILE_ALPHA.get(profile, 0.6)
    
    # K-Score (Investment Quality)
    market_cap_score = min(coingecko_data["market_cap"]/1e10,5) if coingecko_data else 0
    liquidity_score = min(ticker_data["volume"]/1e6,5) if ticker_data else 0
    perf_score = min(max(coingecko_data.get("price_30d_change",0)/10,0),5) if coingecko_data else 0
    K = round((market_cap_score + liquidity_score + perf_score)/3,2)
    
    # M-Score (Growth Potential)
    dev_score = 2.5  # placeholder; can be extended with GitHub
    community_score = coingecko_data["community_score"] if coingecko_data else 0
    incentives_score = 2.5
    M = round((dev_score + community_score + incentives_score)/3,2)
    
    # OTS: α-weighted K/M
    OTS = round(K*alpha + M*(1-alpha),2)
    
    # R-Score: Risk
    R_tech = 0.5
    R_reg = 0.3
    R_fin = 0.4
    R = round(R_tech*0.4 + R_reg*0.35 + R_fin*0.25,2)
    
    # RAR: Risk-adjusted
    RAR = round(OTS*(1-R),2)
    
    return {
        "K": K, "M": M, "OTS": OTS, "R": R, "RAR": RAR,
        "K_components": {"Market Cap": market_cap_score, "Liquidity": liquidity_score, "30d Perf": perf_score},
        "M_components": {"Dev": dev_score, "Community": community_score, "Incentives": incentives_score},
        "R_components": {"Tech": R_tech, "Reg": R_reg, "Fin": R_fin}
    }

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

# User Inputs
profile = st.selectbox("Select investment profile", list(PROFILE_ALPHA.keys()))
crypto_name = st.selectbox("Select cryptocurrency (full name)", list(CRYPTO_MAP.keys()))
crypto_symbol = CRYPTO_MAP[crypto_name]["symbol"]
coin_id = CRYPTO_MAP[crypto_name]["coingecko_id"]

if st.button("Generate CMEF X Report"):
    # Fetch live data
    ticker_data = fetch_bitvavo_ticker(crypto_symbol)
    coingecko_data = fetch_coingecko_data(coin_id)

    debug_messages = []
    if ticker_data is None:
        debug_messages.append("Could not fetch Bitvavo ticker; using CoinGecko only if available.")
    if coingecko_data is None:
        debug_messages.append("Could not fetch CoinGecko data; some metrics may be defaulted.")

    if ticker_data is None and coingecko_data is None:
        st.error("Could not fetch live data. Check your connection or select another coin.")
    else:
        # Compute scores
        scores = compute_cmef_scores(ticker_data, coingecko_data, profile)
        
        # Live Market Overview
        st.subheader("📊 Live Market Data")
        st.markdown(f"**Market:** {crypto_symbol}-EUR")
        st.markdown(f"**Current Price (EUR):** €{ticker_data['price']:.2f}" if ticker_data else "**Current Price:** N/A")
        st.markdown(f"**24h Volume (EUR):** €{ticker_data['volume']:.2f}" if ticker_data else "**24h Volume:** N/A")
        st.markdown(f"**Market Cap (EUR):** €{coingecko_data['market_cap']:.2f}" if coingecko_data else "**Market Cap:** N/A")
        
        # CMEF X Scores with Explanations
        st.subheader("📈 CMEF X Scores & Analysis")
        for key in ["K","M","OTS","R","RAR"]:
            value = scores[key]
            st.progress(min(value/5,1) if key!="R" else min(value/1,1))
            if key == "K":
                st.markdown(f"**K-Score (Investment Quality): {value}/5**")
                st.markdown("Definition: Measures the current investment quality based on market cap, liquidity, and recent performance.")
                st.markdown(f"Rationale for {crypto_name}: Market Cap={scores['K_components']['Market Cap']:.2f}, Liquidity={scores['K_components']['Liquidity']:.2f}, 30d Performance={scores['K_components']['30d Perf']:.2f}")
            elif key == "M":
                st.markdown(f"**M-Score (Growth Potential): {value}/5**")
                st.markdown("Definition: Measures long-term growth potential based on developer activity, community strength, and incentives.")
                st.markdown(f"Rationale for {crypto_name}: Dev={scores['M_components']['Dev']:.2f}, Community={scores['M_components']['Community']:.2f}, Incentives={scores['M_components']['Incentives']:.2f}")
            elif key == "OTS":
                st.markdown(f"**OTS (Overall Technical Strength): {value}/5**")
                st.markdown("Definition: α-weighted combination of K-Score and M-Score based on investment profile.")
            elif key == "R":
                st.markdown(f"**R-Score (Risk): {value} (0..1)**")
                st.markdown("Definition: Measures combined technical, regulatory, and financial risk.")
                st.markdown(f"Components: Tech={scores['R_components']['Tech']}, Reg={scores['R_components']['Reg']}, Fin={scores['R_components']['Fin']}")
            elif key == "RAR":
                st.markdown(f"**RAR (Risk-Adjusted Return): {value}/5**")
                st.markdown("Definition: Risk-adjusted score, combines OTS with R-Score to adjust for potential risk.")

        # Portfolio Recommendation
        rec = portfolio_recommendation(scores["RAR"], profile)
        st.subheader("💼 Portfolio Recommendation")
        st.markdown(f"Suggested action for profile **{profile}**: **{rec}**")

        # Full CMEF X Report
        st.subheader("📖 Full CMEF X Report")
        st.markdown(f"- Coin: {crypto_name} ({crypto_symbol})")
        st.markdown(f"- Profile: {profile} (α = {PROFILE_ALPHA[profile]})")
        st.markdown(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"- K-Score: {scores['K']}/5 | Components: {scores['K_components']}")
        st.markdown(f"- M-Score: {scores['M']}/5 | Components: {scores['M_components']}")
        st.markdown(f"- OTS: {scores['OTS']}/5")
        st.markdown(f"- R-Score: {scores['R']} | Components: {scores['R_components']}")
        st.markdown(f"- RAR: {scores['RAR']}/5")
        
        # Debug messages (if any)
        if debug_messages:
            with st.expander("🔧 Debug / Raw Data"):
                for msg in debug_messages:
                    st.warning(msg)
                st.json({
                    "ticker_data": ticker_data,
                    "coingecko_data": coingecko_data,
                    "scores": scores
                })
