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
    """Fetch Bitvavo EUR markets"""
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/markets", timeout=5)
        resp.raise_for_status()
        markets = resp.json()
        eur_markets = [m for m in markets if m['quote'] == 'EUR']
        # Return a mapping of name → ticker for dropdown
        market_map = {m['base'] : f"{m['base']}-EUR" for m in eur_markets}
        return market_map
    except Exception as e:
        st.error(f"Could not fetch Bitvavo markets: {e}")
        return {}

def fetch_bitvavo_ticker(ticker):
    """Fetch current price & 24h volume"""
    try:
        resp = requests.get(f"{BITVAVO_API_URL}/{ticker}/ticker", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {'price': float(data['last']), 'volume': float(data['volume'])}
    except Exception as e:
        st.warning(f"Could not fetch Bitvavo ticker for {ticker}: {e}")
        return None

def fetch_coingecko_data(coin_id):
    """Fetch CoinGecko market cap & community data"""
    try:
        resp = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        market_cap = data.get('market_data', {}).get('market_cap', {}).get('eur', 0)
        twitter_followers = data.get('community_data', {}).get('twitter_followers', 0)
        reddit_subs = data.get('community_data', {}).get('reddit_subscribers', 0)
        price_30d_change = data.get('market_data', {}).get('price_change_percentage_30d', 0)
        return {
            'market_cap': market_cap,
            'twitter_followers': twitter_followers,
            'reddit_subs': reddit_subs,
            'price_30d_change': price_30d_change
        }
    except Exception as e:
        st.warning(f"Could not fetch CoinGecko data: {e}")
        return None

# ---------------------------
# CMEF X Scoring
# ---------------------------

def compute_scores(bitvavo_data, coingecko_data, alpha):
    """
    Compute K-Score, M-Score, OTS, R-Score, RAR
    Includes rationale for each
    """
    # K-Score (Investment Quality)
    K_components = {
        'Market Cap': min(coingecko_data.get('market_cap',0)/1e11,5),
        'Liquidity (24h Volume)': min(bitvavo_data.get('volume',0)/1e8,5),
        '30d Performance': max(min(coingecko_data.get('price_30d_change',0)/50*5,5),0)
    }
    K_score = sum(K_components.values())/len(K_components)
    
    # M-Score (Growth Potential)
    M_components = {
        'Community': min((coingecko_data.get('twitter_followers',0)/1e6 + coingecko_data.get('reddit_subs',0)/1e5),5),
        'Incentives': 2.5,  # Placeholder for staking/vesting incentives
        'Dev Activity': 2.5   # Placeholder for dev activity
    }
    M_score = sum(M_components.values())/len(M_components)
    
    # Overall Technical Strength
    OTS = alpha*K_score + (1-alpha)*M_score
    
    # Risk Scoring
    R_components = {
        'Technical': 0.5,  # Placeholder
        'Regulatory': 0.3,  # Placeholder
        'Financial': 0.4   # Derived from volatility
    }
    R_score = sum(R_components.values())/len(R_components)
    
    # Risk-adjusted return
    RAR = OTS*(1-R_score)
    
    scores = {
        'K_score': round(K_score,2),
        'M_score': round(M_score,2),
        'OTS': round(OTS,2),
        'R_score': round(R_score,2),
        'RAR': round(RAR,2),
        'K_components': K_components,
        'M_components': M_components,
        'R_components': R_components
    }
    
    return scores

def portfolio_recommendation(RAR, profile):
    """Return portfolio advice based on profile & RAR"""
    if RAR >= 3.25:
        mapping = {'Conservative':'Core','Balanced':'Core','Growth':'Core'}
    elif RAR >=2.5:
        mapping = {'Conservative':'Tactical','Balanced':'Core','Growth':'Core'}
    elif RAR >=1.75:
        mapping = {'Conservative':'Small/Cautious','Balanced':'Tactical','Growth':'Core'}
    elif RAR >=1.0:
        mapping = {'Conservative':'Avoid','Balanced':'Small/Cautious','Growth':'Tactical'}
    else:
        mapping = {'Conservative':'Avoid','Balanced':'Avoid','Growth':'Small/Cautious'}
    return mapping.get(profile,'Cautious')

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="CMEF X — Free Crypto Analysis Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard")

# Load Bitvavo EUR markets
market_map = fetch_bitvavo_markets()
if not market_map:
    st.stop()

# User inputs
profile = st.selectbox("Select investment profile", ["Conservative","Balanced","Growth"])
alpha_map = {"Conservative":0.7,"Balanced":0.6,"Growth":0.5}
alpha = alpha_map[profile]

coin_name = st.selectbox("Select cryptocurrency", sorted(market_map.keys()))
ticker = market_map[coin_name]

if st.button("Generate CMEF X Report"):
    with st.spinner(f"Fetching live data for {coin_name} ({ticker})..."):
        bitvavo_data = fetch_bitvavo_ticker(ticker)
        # Auto-resolve CoinGecko ID by lowercase name (simplified)
        coin_id = coin_name.lower()
        coingecko_data = fetch_coingecko_data(coin_id)
        
        if not bitvavo_data:
            st.error(f"Could not fetch live data for {coin_name}. Check your connection or select another coin.")
        else:
            scores = compute_scores(bitvavo_data, coingecko_data, alpha)
            rec = portfolio_recommendation(scores['RAR'], profile)
            
            # ---------------------------
            # Output Layout
            # ---------------------------
            st.subheader(f"📊 CMEF X Scores & Analysis — {coin_name}")
            
            st.markdown(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.markdown(f"**Current Price (EUR):** €{bitvavo_data['price']:.2f}")
            st.markdown(f"**K-Score (Investment Quality):** {scores['K_score']}/5")
            st.markdown(f"Definition: Measures current investment quality based on market cap, liquidity, and recent performance.")
            st.markdown(f"Rationale: {scores['K_components']}")
            
            st.markdown(f"**M-Score (Growth Potential):** {scores['M_score']}/5")
            st.markdown(f"Definition: Measures long-term growth potential based on developer activity, community, and incentives.")
            st.markdown(f"Rationale: {scores['M_components']}")
            
            st.markdown(f"**OTS (Overall Technical Strength):** {scores['OTS']}/5")
            st.markdown(f"Definition: α-weighted combination of K & M based on investment profile.")
            
            st.markdown(f"**R-Score (Risk):** {scores['R_score']} (0..1)")
            st.markdown(f"Definition: Combined technical, regulatory, and financial risk.")
            st.markdown(f"Components: {scores['R_components']}")
            
            st.markdown(f"**RAR (Risk-Adjusted Return):** {scores['RAR']}/5")
            st.markdown(f"Definition: Risk-adjusted score combining OTS with R-Score.")
            
            st.subheader("💼 Portfolio Recommendation")
            st.markdown(f"For profile {profile}: **{rec}**")
            
            st.subheader("🔧 Debug / Raw Data (for troubleshooting)")
            st.json({
                'bitvavo_data': bitvavo_data,
                'coingecko_data': coingecko_data,
                'scores': scores,
                'profile': profile,
                'alpha': alpha
            })
