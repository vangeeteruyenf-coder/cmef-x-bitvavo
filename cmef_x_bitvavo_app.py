import streamlit as st
import requests
from datetime import datetime

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Map full name to Bitvavo ticker
COINS = {
    "Bitcoin": "BTC-EUR",
    "Ethereum": "ETH-EUR",
    "Cardano": "ADA-EUR",
    "Aave": "AAVE-EUR",
    "Polygon": "MATIC-EUR"
}

# Profile α weighting
ALPHA_DICT = {"Conservative":0.7,"Balanced":0.5,"Growth":0.3}

# ---------------------------
# Fetch Functions
# ---------------------------
def fetch_bitvavo_ticker(ticker):
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{ticker}/ticker", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {"price": float(data.get("last",0)),"volume": float(data.get("volume",0))}
    except Exception as e:
        return None, str(e)

def fetch_coingecko_market_data(coin_name):
    try:
        coins_resp = requests.get(f"{COINGECKO_API_URL}/coins/list", timeout=5)
        coins_resp.raise_for_status()
        coins_list = coins_resp.json()
        coin_id = next((c["id"] for c in coins_list if c["name"].lower()==coin_name.lower()), None)
        if not coin_id:
            return None, "CoinGecko ID not found"
        market_resp = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", timeout=5)
        market_resp.raise_for_status()
        market_data = market_resp.json()
        return market_data, None
    except Exception as e:
        return None, str(e)

# ---------------------------
# Scoring Functions
# ---------------------------
def compute_K_score(market_data, volume):
    try:
        market_cap = market_data.get('market_data',{}).get('market_cap',{}).get('eur',0)/1e12
        perf_30d = abs(market_data.get('market_data',{}).get('price_change_percentage_30d',0))/10
        scores = {
            "Market Cap": min(market_cap,5),
            "Liquidity": min(volume/1e9,5),
            "30d Perf": min(perf_30d,5)
        }
        K = sum(scores.values())/len(scores)
        return K, scores
    except:
        return 0, {"Market Cap":0,"Liquidity":0,"30d Perf":0}

def compute_M_score(market_data):
    try:
        dev = 2.5  # placeholder
        community = min(market_data.get('community_data',{}).get('twitter_followers',0)/1e6,5)
        incentives = 2.5  # placeholder
        scores = {"Dev": dev, "Community": community, "Incentives": incentives}
        M = sum(scores.values())/len(scores)
        return M, scores
    except:
        return 0, {"Dev":0,"Community":0,"Incentives":0}

def compute_R_score():
    scores = {"Technical":0.5,"Regulatory":0.3,"Financial":0.4}
    R = (scores["Technical"]*0.4 + scores["Regulatory"]*0.35 + scores["Financial"]*0.25)/5
    return R, scores

def compute_OTS_RAR(K, M, alpha, R):
    OTS = K*alpha + M*(1-alpha)
    RAR = OTS*(1-R)
    return OTS, RAR

def portfolio_recommendation(RAR, profile):
    if RAR >= 65:
        return {"Conservative":"Core","Balanced":"Core","Growth":"Core"}.get(profile,"Cautious")
    elif RAR >=50:
        return {"Conservative":"Tactical","Balanced":"Core","Growth":"Core"}.get(profile,"Cautious")
    elif RAR >=35:
        return {"Conservative":"Small/Cautious","Balanced":"Tactical","Growth":"Core"}.get(profile,"Cautious")
    elif RAR >=20:
        return {"Conservative":"Avoid","Balanced":"Small/Cautious","Growth":"Tactical"}.get(profile,"Cautious")
    else:
        return {"Conservative":"Avoid","Balanced":"Avoid","Growth":"Small/Cautious"}.get(profile,"Cautious")

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X — Free Crypto Analysis Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard")

coin_name = st.selectbox("Select Cryptocurrency:", list(COINS.keys()))
profile = st.selectbox("Select Investment Profile:", ["Conservative","Balanced","Growth"])
alpha = ALPHA_DICT[profile]

if st.button("Generate CMEF X Report"):
    ticker = COINS[coin_name]
    st.info(f"Fetching live data for {coin_name} ({ticker})...")

    ticker_data, ticker_err = fetch_bitvavo_ticker(ticker)
    market_data, cg_err = fetch_coingecko_market_data(coin_name)

    debug_info = {
        "Bitvavo_Error": ticker_err,
        "CoinGecko_Error": cg_err,
        "Ticker_Data": ticker_data,
        "CoinGecko_Data": market_data
    }

    if not ticker_data or not market_data:
        st.error(f"Could not fetch live data for {coin_name}. Check connection or select another coin.")
        st.expander("🔧 Debug / Raw Data", expanded=True).json(debug_info)
    else:
        price = ticker_data['price']
        volume = ticker_data['volume']

        K, K_components = compute_K_score(market_data, volume)
        M, M_components = compute_M_score(market_data)
        R, R_components = compute_R_score()
        OTS, RAR = compute_OTS_RAR(K*20, M*20, alpha, R)
        recommendation = portfolio_recommendation(RAR, profile)

        # Display CMEF X Report
        st.header(f"📊 CMEF X Report — {coin_name} ({ticker})")
        st.subheader("Live Market Data")
        st.markdown(f"- Current Price (EUR): €{price:,.2f}")
        st.markdown(f"- 24h Volume (EUR): €{volume:,.2f}")
        st.markdown(f"- CoinGecko Market Cap (EUR): €{market_data.get('market_data',{}).get('market_cap',{}).get('eur',0):,.2f}")

        st.subheader("K-Score (Investment Quality)")
        st.markdown(f"- Score: {K:.2f}/5")
        st.markdown("- Definition: Measures current investment quality (market cap, liquidity, recent performance)")
        st.markdown(f"- Components: {K_components}")

        st.subheader("M-Score (Growth Potential)")
        st.markdown(f"- Score: {M:.2f}/5")
        st.markdown("- Definition: Measures long-term growth potential (developer activity, community, incentives)")
        st.markdown(f"- Components: {M_components}")

        st.subheader("OTS & RAR")
        st.markdown(f"- OTS: {OTS:.2f}/100")
        st.markdown(f"- R-Score: {R:.2f}")
        st.markdown(f"- RAR: {RAR:.2f}/100")

        st.subheader("Portfolio Recommendation")
        st.markdown(f"- Suggested action for profile {profile}: {recommendation}")

        st.subheader("Analytical Thesis")
        st.markdown(f"- {coin_name} shows K={K:.2f} and M={M:.2f} indicating quality and growth potential.")
        st.markdown(f"- Risk (R={R:.2f}) reduces effective RAR to {RAR:.2f}. Portfolio action: {recommendation}.")

        st.subheader("Report Generated")
        st.markdown(f"- Profile α weighting: {alpha}")
        st.markdown(f"- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        st.expander("🔧 Debug / Raw Data", expanded=False).json(debug_info)
