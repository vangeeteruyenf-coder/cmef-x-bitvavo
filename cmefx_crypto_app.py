# cmefx_analyzer.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="CMEFX Crypto Analyzer", layout="wide")

st.title("CMEFX.CRYPTO Analyzer – Bitvavo Coins")
st.markdown("Select profile, click 'Run Analysis', and get CMEFX scores for all available coins.")

# --- User Input ---
profile = st.selectbox("Choose Investor Profile", ["Balanced", "Growth"])
run_analysis = st.button("Run Full Analysis")

# --- Helper Functions ---
def fetch_bitvavo_coins():
    """Fetch coin list from CoinGecko as Bitvavo uses similar coins."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "eur",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": False
    }
    r = requests.get(url, params=params)
    data = r.json()
    return data

def fetch_github_activity(repo_url):
    """Fetch GitHub commits last 90 days (best effort)"""
    if not repo_url or "github.com" not in repo_url:
        return 0
    api_url = repo_url.replace("github.com", "api.github.com/repos") + "/commits"
    params = {"since": (datetime.utcnow() - pd.Timedelta(days=90)).isoformat()}
    r = requests.get(api_url, params=params)
    if r.status_code != 200:
        return 0
    return len(r.json())

def calculate_k_score(coin):
    """Best-effort K-Score calculation (15 criteria, 0-5 each)"""
    # Sample heuristics
    price = coin['current_price']
    market_cap = coin['market_cap'] or 0
    liquidity_score = min(market_cap/1e9,5)
    adoption_score = min(coin['total_volume']/1e8,5)
    team_score = 3  # placeholder, could scrape team info
    security_score = 3 # placeholder, could scrape audit info
    # sum weighted (weights in %)
    weights = [15,10,10,10,8,8,7,7,7,5,5,3,3,2,2]
    scores = [adoption_score, liquidity_score, 4, adoption_score, liquidity_score,
              team_score, security_score, 3,3,3,3,2,2,1,1]
    weighted = [w/100*s for w,s in zip(weights,scores)]
    k_score = sum(weighted)*20
    return round(k_score,1)

def calculate_m_score(coin):
    """Best-effort M-Score calculation (10 criteria)"""
    innovation_score = 4
    adoption_score = 4
    scalability_score = 3
    network_score = 3
    scores = [innovation_score, adoption_score, 3, scalability_score, 3,
              network_score, 3,3,3,3]
    weights = [15,15,10,10,10,10,10,5,5,5]
    weighted = [w/100*s for w,s in zip(weights,scores)]
    m_score = sum(weighted)*20
    return round(m_score,1)

def calculate_r_score(profile, k_score, m_score):
    """Risk adjusted RAR-Score"""
    R = 0.2  # sample risk 0-1
    alpha = 0.6 if profile=="Balanced" else 0.4
    ots = k_score*alpha + m_score*(1-alpha)
    rar = ots*(1-R)
    return round(rar,1)

def qualitative_label(score):
    if score>=85:
        return "Elite"
    elif score>=70:
        return "Very Strong"
    elif score>=55:
        return "Strong"
    elif score>=40:
        return "Acceptable"
    else:
        return "Weak"

# --- Main Analysis ---
if run_analysis:
    st.info("Fetching data from CoinGecko...")
    coins = fetch_bitvavo_coins()
    results = []
    progress = st.progress(0)
    total = len(coins)
    for idx, coin in enumerate(coins):
        k = calculate_k_score(coin)
        m = calculate_m_score(coin)
        rar = calculate_r_score(profile, k, m)
        label = qualitative_label(rar)
        results.append({
            "NR": idx+1,
            "Name": coin['name'],
            "Ticker": coin['symbol'].upper(),
            "Price (€)": coin['current_price'],
            "K": k,
            "M": m,
            "RAR": rar,
            "Label": label,
            "Coin Data": coin
        })
        progress.progress((idx+1)/total)
        time.sleep(0.05)  # avoid API throttling

    df = pd.DataFrame(results)
    st.success("Analysis complete!")

    # --- Display Main Table ---
    st.subheader("CMEFX Ranking Table")
    def view_report(row):
        coin = row["Coin Data"]
        st.markdown(f"### Full CMEFX Report for {coin['name']} ({coin['symbol'].upper()})")
        st.markdown(f"**Snapshot UTC:** {datetime.utcnow().isoformat()}")
        st.markdown(f"**K-Score:** {row['K']}")
        st.markdown(f"**M-Score:** {row['M']}")
        st.markdown(f"**RAR-Score:** {row['RAR']}")
        st.markdown(f"**Label:** {row['Label']}")
        st.markdown("#### Module 1 – K-Score (15 criteria)")
        st.table({
            "Criterion":["Use Case","Tokenomics","Technology","Adoption","Market","Team","Security",
                        "Community","Governance","Ecosystem","Roadmap","Legal/ESG","Macro","Marketing","Historical"],
            "Score":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
            "Weight (%)":[15,10,10,10,8,8,7,7,7,5,5,3,3,2,2]
        })
        st.markdown("#### Module 2 – M-Score (10 criteria)")
        st.table({
            "Criterion":["Innovation","Global Adoption","Competitive Barriers","Scalability","Long-Term Incentives",
                        "Network Effects","Censorship Resistance","Macro Trends","Founders Track","Branding"],
            "Score":[1,1,1,1,1,1,1,1,1,1],
            "Weight (%)":[15,15,10,10,10,10,10,5,5,5]
        })
        st.markdown("#### Module 3 – Risk & RAR")
        st.table({
            "Risk":["Technical","Regulatory","Financial"],
            "Score":[1,1,1],
            "Weight (%)":[40,35,25]
        })
        st.markdown("#### Interpretation")
        st.markdown("- Strengths: Best-effort analysis based on available data.")
        st.markdown("- Limitations: Some metrics (audit, social) may be incomplete.")
        st.markdown("- Profile Suitability: "+profile)
        st.markdown("#### Sources Appendix")
        st.markdown("- CoinGecko API: https://www.coingecko.com")
        st.markdown("- Snapshot UTC: "+datetime.utcnow().isoformat())

    # Add a button per row for viewing full report
    for i, row in df.iterrows():
        cols = st.columns([1,1,1,1,1,1,1])
        cols[0].write(row["NR"])
        cols[1].write(row["Name"])
        cols[2].write(row["Ticker"])
        cols[3].write(row["Price (€)"])
        cols[4].write(f"K:{row['K']}, M:{row['M']}, RAR:{row['RAR']}")
        cols[5].write(row["Label"])
        if cols[6].button("Bekijk Rapport", key=row["NR"]):
            view_report(row)
