import streamlit as st
import requests
from datetime import datetime

# ---------------------------
# Config
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# ---------------------------
# Helper functions
# ---------------------------
def fetch_bitvavo_markets():
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m['market'] for m in markets if m['quote'] == 'EUR']
        return eur_markets
    except:
        return []

def fetch_ticker(market):
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{market}/ticker", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {'last': float(data['last']), 'volume': float(data['volume'])}
    except:
        return None

def fetch_coingecko_data(symbol):
    try:
        resp = requests.get(f"{COINGECKO_API_URL}/coins/{symbol.lower()}", timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        market_cap = data.get('market_data', {}).get('market_cap', {}).get('eur', 0) or 0
        price_30d_change = data.get('market_data', {}).get('price_change_percentage_30d', 0) or 0
        twitter_followers = data.get('community_data', {}).get('twitter_followers', 0) or 0
        reddit_subs = data.get('community_data', {}).get('reddit_subscribers', 0) or 0
        return {
            'market_cap': market_cap,
            'price_30d_change': price_30d_change,
            'twitter_followers': twitter_followers,
            'reddit_subs': reddit_subs
        }
    except:
        return {'market_cap':0,'price_30d_change':0,'twitter_followers':0,'reddit_subs':0}

# ---------------------------
# CMEF X computation
# ---------------------------
def compute_cmef_x(price, volume_eur, cg_data, alpha):
    # K-Score: Investment Quality
    A1_market_cap = min(cg_data['market_cap'] / 1e10, 5)  # proxy scaling
    A5_volume = min(volume_eur / 1e9, 5)
    A15_perf = min(max((cg_data['price_30d_change'] + 50)/20, 0), 5)  # rough scaling -50..50%
    K = round((A1_market_cap + A5_volume + A15_perf)/3, 2)

    # M-Score: Growth Potential
    B1_github = 0  # no GitHub input in this version
    B6_community = min((cg_data['twitter_followers']/1e6 + cg_data['reddit_subs']/1e5), 5)
    B5_incentives = 2.5  # default placeholder
    M = round((B1_github + B6_community + B5_incentives)/3, 2)

    # OTS
    OTS = round(K*alpha + M*(1-alpha),2)

    # R-Score
    R_tech = 0.5  # placeholder
    R_reg = 0.3
    R_fin = 0.4
    R = round(R_tech*0.4 + R_reg*0.35 + R_fin*0.25,2)

    # RAR
    RAR = round(OTS*(1-R),2)

    # Rationale
    rationale = {
        'A1_market_cap': A1_market_cap,
        'A5_volume': A5_volume,
        'A15_perf': A15_perf,
        'B1_github': B1_github,
        'B6_community': B6_community,
        'B5_incentives': B5_incentives,
        'R_tech': R_tech,
        'R_reg': R_reg,
        'R_fin': R_fin
    }

    return K, M, OTS, R, RAR, rationale

def portfolio_recommendation(rar_score, profile):
    if rar_score >= 65:
        return "Core"
    elif rar_score >=50:
        return "Tactical"
    elif rar_score >=35:
        return "Small / Cautious"
    else:
        return "Avoid"

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X Crypto Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard (Auto-resolve)")

# Inputs
crypto_selection = st.selectbox("Select cryptocurrency:", ["Bitcoin BTC", "Ethereum ETH", "Aave AAVE", "Cardano ADA"])
profile = st.selectbox("Select investment profile:", ["Conservative", "Balanced", "Growth"])
alpha_dict = {"Conservative":0.7, "Balanced":0.6, "Growth":0.5}
alpha = alpha_dict[profile]

# Resolve symbol & Bitvavo market
symbol = crypto_selection.split()[1]  # e.g., "BTC" from "Bitcoin BTC"
market = f"{symbol}-EUR"

st.info("Fetching data from Bitvavo & CoinGecko... please wait.")

ticker = fetch_ticker(market)
cg_data = fetch_coingecko_data(symbol)

if ticker is None:
    st.error(f"Could not fetch Bitvavo ticker for {market}.")
else:
    price = ticker['last']
    volume_eur = ticker['volume'] * price
    K, M, OTS, R, RAR, rationale = compute_cmef_x(price, volume_eur, cg_data, alpha)
    rec = portfolio_recommendation(RAR, profile)

    # Live Market & Scores
    st.subheader("Live Market & CMEF X Summary")
    st.metric("Market (Bitvavo)", market)
    st.metric("Current Price (EUR)", f"€{price:,.2f}")
    st.metric("K-Score", f"{K}/5")
    st.metric("M-Score", f"{M}/5")
    st.metric("OTS", f"{OTS}/5")
    st.metric("R-Score (risk)", f"{R} (0..1)")
    st.metric("RAR (risk-adjusted)", f"{RAR}/5")

    # Score bars
    st.subheader("Score Visual Summary")
    st.progress(min(K/5,1))
    st.text("K-Score")
    st.progress(min(M/5,1))
    st.text("M-Score")
    st.progress(min(OTS/5,1))
    st.text("OTS")
    st.progress(min(R/1,1))
    st.text("R-Score")
    st.progress(min(RAR/5,1))
    st.text("RAR (risk-adjusted)")

    # Full CMEF X Report
    st.subheader("Full CMEF X Report")
    st.markdown(f"""
**Coin:** {crypto_selection}  
**Profile:** {profile} (α = {alpha})  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  

**Market Overview**  
- Price (EUR): €{price:,.2f}  
- 24h Volume (EUR): €{volume_eur:,.2f}  
- Market cap (CoinGecko): €{cg_data['market_cap']:,.2f}  

**K-Score (Investment Quality)**  
- Market cap proxy: {rationale['A1_market_cap']}/5  
- Liquidity proxy: {rationale['A5_volume']}/5  
- 30d performance proxy: {rationale['A15_perf']}/5  
- **Combined K-Score:** {K}/5  

**M-Score (Growth Potential)**  
- GitHub stars proxy: {rationale['B1_github']}/5  
- Community proxy (Twitter + Reddit): {rationale['B6_community']}/5  
- Incentives proxy: {rationale['B5_incentives']}/5  
- **Combined M-Score:** {M}/5  

**Risk Analysis (R-Score)**  
- Technical risk: {rationale['R_tech']}  
- Regulatory risk: {rationale['R_reg']}  
- Financial/Volatility risk: {rationale['R_fin']}  
- **Combined R-Score:** {R}  

**Combined & Risk-adjusted**  
- OTS (alpha-weighted): {OTS}/5  
- RAR (risk-adjusted): {RAR}/5  

**Portfolio Recommendation:** {rec}
""")
