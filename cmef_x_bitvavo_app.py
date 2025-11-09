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
        eur_markets = {m['market'].split('-')[0].upper(): m['market'] for m in markets if m['quote']=='EUR'}
        return eur_markets
    except Exception as e:
        st.error(f"Could not fetch Bitvavo markets: {e}")
        return {}

def fetch_bitvavo_ticker(market):
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{market}/ticker", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {'price': float(data['last']), 'volume': float(data['volume'])}
    except Exception as e:
        st.warning(f"Could not fetch Bitvavo ticker for {market}: {e}")
        return None

def fetch_coingecko_data(coin_id):
    try:
        resp = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        market_cap = data.get('market_data', {}).get('market_cap', {}).get('eur', 0)
        twitter_followers = data.get('community_data', {}).get('twitter_followers', 0)
        reddit_subs = data.get('community_data', {}).get('reddit_subscribers', 0)
        return {'market_cap': market_cap, 'twitter_followers': twitter_followers, 'reddit_subs': reddit_subs}
    except:
        return {'market_cap': 0, 'twitter_followers': 0, 'reddit_subs': 0}

# ---------------------------
# CMEF X scoring
# ---------------------------
def compute_cmef_scores(ticker_data, cg_data, alpha):
    # K-Score components
    market_cap_score = min(cg_data['market_cap'] / 1e12, 5)
    liquidity_score = min(ticker_data['volume'] / 1e8, 5)
    k_score = round((market_cap_score*0.5 + liquidity_score*0.5),2)
    
    # M-Score components
    community_score = min((cg_data['twitter_followers'] + cg_data['reddit_subs'])/1e6,5)
    incentives_score = 2.5  # Placeholder for staking/incentives
    m_score = round((community_score*0.5 + incentives_score*0.5),2)
    
    # Overall Technical Strength
    ots = round(k_score*alpha + m_score*(1-alpha),2)
    
    # Risk
    r_tech = 0.5
    r_reg = 0.3
    r_fin = 0.4
    r_score = round(r_tech*0.4 + r_reg*0.35 + r_fin*0.25,2)
    
    # Risk-adjusted
    rar = round(ots*(1-r_score),2)
    
    details = {
        'K': k_score,
        'M': m_score,
        'OTS': ots,
        'R': r_score,
        'RAR': rar,
        'components': {
            'market_cap': market_cap_score,
            'liquidity': liquidity_score,
            'community': community_score,
            'incentives': incentives_score,
            'r_tech': r_tech,
            'r_reg': r_reg,
            'r_fin': r_fin
        }
    }
    
    return details

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
st.write("Analyze any cryptocurrency with CMEF X risk-adjusted scoring and portfolio recommendations.")

# Load Bitvavo markets
bitvavo_markets = fetch_bitvavo_markets()
coin_names = sorted(bitvavo_markets.keys())

# User Inputs
profile = st.selectbox("Select Investment Profile", ["Conservative","Balanced","Growth"])
alpha_dict = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_dict[profile]

coin_name = st.selectbox("Select Cryptocurrency", coin_names)

if st.button("Generate CMEF X Report"):
    st.info(f"Fetching live data for {coin_name} ({bitvavo_markets[coin_name]})...")
    
    # Fetch Bitvavo ticker
    ticker_data = fetch_bitvavo_ticker(bitvavo_markets[coin_name])
    if not ticker_data:
        st.error(f"Could not fetch live data for {coin_name}. Check your connection or select another coin.")
    else:
        # Fetch CoinGecko ID & data
        cg_resp = requests.get(f"{COINGECKO_API_URL}/coins/list").json()
        coin_id = next((c['id'] for c in cg_resp if c['symbol'].upper()==coin_name.upper()), None)
        if coin_id:
            cg_data = fetch_coingecko_data(coin_id)
        else:
            cg_data = {'market_cap': 0, 'twitter_followers':0, 'reddit_subs':0}
        
        # Compute CMEF X
        scores = compute_cmef_scores(ticker_data, cg_data, alpha)
        
        # Portfolio recommendation
        rec = portfolio_recommendation(scores['RAR'], profile)
        
        # Display live market
        st.subheader("📊 Live Market Data")
        st.markdown(f"**Ticker:** {bitvavo_markets[coin_name]}")
        st.markdown(f"**Current Price (EUR):** €{ticker_data['price']:.2f}")
        st.markdown(f"**24h Volume:** €{ticker_data['volume']:.2f}")
        st.markdown(f"**Market Cap (CoinGecko):** €{cg_data['market_cap']:.2f}")
        
        # Display CMEF X Scores
        st.subheader("🪙 CMEF X Scores & Analysis")
        st.progress(min(scores['K']/5,1))
        st.markdown(f"**K-Score (Investment Quality):** {scores['K']}/5")
        st.markdown(f"- Definition: Measures current investment quality based on market cap and liquidity.")
        st.markdown(f"- Rationale for {coin_name}: Market Cap={scores['components']['market_cap']:.2f}, Liquidity={scores['components']['liquidity']:.2f}")
        
        st.progress(min(scores['M']/5,1))
        st.markdown(f"**M-Score (Growth Potential):** {scores['M']}/5")
        st.markdown(f"- Definition: Measures growth potential based on community & incentives.")
        st.markdown(f"- Rationale for {coin_name}: Community={scores['components']['community']:.2f}, Incentives={scores['components']['incentives']:.2f}")
        
        st.progress(min(scores['OTS']/5,1))
        st.markdown(f"**OTS (Overall Technical Strength):** {scores['OTS']}/5")
        st.markdown(f"- α-weighted combination of K and M according to profile {profile}")
        
        st.progress(min(scores['R'],1))
        st.markdown(f"**R-Score (Risk):** {scores['R']} (0..1)")
        st.markdown(f"- Components: Tech={scores['components']['r_tech']}, Reg={scores['components']['r_reg']}, Fin={scores['components']['r_fin']}")
        
        st.progress(min(scores['RAR']/5,1))
        st.markdown(f"**RAR (Risk-Adjusted Return):** {scores['RAR']}/5")
        
        st.subheader("💼 Portfolio Recommendation")
        st.markdown(f"Suggested action for profile {profile}: **{rec}**")
        
        # Full structured report
        st.subheader("📖 Full CMEF X Structured Report")
        st.json({
            "Coin": coin_name,
            "Profile": profile,
            "Generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "K-Score": scores['K'],
            "M-Score": scores['M'],
            "OTS": scores['OTS'],
            "R-Score": scores['R'],
            "RAR": scores['RAR'],
            "Components": scores['components'],
            "Bitvavo_Ticker": bitvavo_markets[coin_name],
            "CoinGecko_ID": coin_id
        })
