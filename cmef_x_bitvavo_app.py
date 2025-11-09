# cmef_x_crypto_dashboard.py
"""
CMEF X Crypto Analysis Dashboard - Final (matplotlib-free)
Free data only: Bitvavo (market), CoinGecko (market & community), GitHub (dev metrics)
English UI, attractive visuals using native Streamlit components
"""

import streamlit as st
import requests
import math
import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------
# ENDPOINTS & CONFIG
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
GITHUB_API_URL = "https://api.github.com/repos"

st.set_page_config(page_title="CMEF X Crypto Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard (Bitvavo + CoinGecko + GitHub)")

# ---------------------------
# CACHEABLE DATA FETCHERS
# ---------------------------
@st.cache_data(ttl=300)
def fetch_bitvavo_markets():
    try:
        r = requests.get(f"{BITVAVO_API_URL}/markets", timeout=10)
        r.raise_for_status()
        markets = r.json()
        eur_markets = sorted([m["market"] for m in markets if m.get("quote") == "EUR"])
        return eur_markets
    except Exception as e:
        st.error(f"Failed to fetch Bitvavo markets: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_bitvavo_ticker_24h(market):
    try:
        r = requests.get(f"{BITVAVO_API_URL}/ticker/24h?market={market}", timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            data = data[0]
        return {
            "last": float(data.get("last", 0)),
            "volume": float(data.get("volume", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0))
        }
    except Exception as e:
        st.warning(f"Could not fetch Bitvavo ticker for {market}: {e}")
        return None

@st.cache_data(ttl=600)
def fetch_bitvavo_candles(market, interval="1d", limit=31):
    try:
        r = requests.get(f"{BITVAVO_API_URL}/{market}/candles/{interval}?limit={limit}", timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
        return df
    except Exception as e:
        st.warning(f"Could not fetch candles for {market}: {e}")
        return None

@st.cache_data(ttl=3600)
def coingecko_find_coin_id(symbol, name_hint=None):
    try:
        r = requests.get(f"{COINGECKO_API_URL}/coins/list", timeout=10)
        r.raise_for_status()
        coins = r.json()
        symbol = symbol.lower()
        matches = [c for c in coins if c.get("symbol","").lower() == symbol]
        if len(matches) == 1:
            return matches[0]["id"]
        if name_hint:
            for c in matches:
                if name_hint.lower() in c.get("name","").lower():
                    return c["id"]
        if matches:
            return matches[0]["id"]
        return None
    except Exception as e:
        st.warning(f"CoinGecko coin list error: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_coingecko_coin(coin_id):
    if not coin_id:
        return None
    try:
        r = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", params={"localization":"false","tickers":"false","market_data":"true","community_data":"true","developer_data":"false","sparkline":"false"}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"CoinGecko fetch error for {coin_id}: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_github_repo(repo_full_name):
    if not repo_full_name or "/" not in repo_full_name:
        return None
    try:
        r = requests.get(f"{GITHUB_API_URL}/{repo_full_name}", timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        st.warning(f"GitHub fetch error: {e}")
        return None

# ---------------------------
# SCORING HELPERS
# ---------------------------
def normalize_log(x, ref):
    if x is None or x <= 0:
        return 0.0
    try:
        return min(1.0, max(0.0, math.log10(x) / math.log10(ref)))
    except:
        return 0.0

def to_0_5(x):
    return round(max(0.0, min(5.0, x * 5.0)), 3)

# ---------------------------
# CMEF X CALC
# ---------------------------
def compute_cmef(market, ticker24, candles_df, cg_data, github_data, alpha):
    details = {}
    # Live price & volume
    price = ticker24["last"]
    volume = ticker24["volume"]
    details['bitvavo_price'] = price
    details['bitvavo_volume'] = volume

    # K-Score proxies
    market_cap = None
    if cg_data and cg_data.get('market_data'):
        market_cap = cg_data['market_data'].get('market_cap', {}).get('eur')
    details['coingecko_market_cap_eur'] = market_cap

    # A1 (use case / moat) -> proxy by market cap (log scale)
    A1 = to_0_5(normalize_log(market_cap if market_cap else 0, ref=1.2e12))  # 1.2T EUR reference scale

    # A5 (market & liquidity) -> volume relative to 1e9 EUR
    vol_norm = min(1.0, volume / 1e9)
    A5 = to_0_5(vol_norm)

    # A15 recent performance (30d)
    pct_30d = None
    if candles_df is not None and not candles_df.empty:
        try:
            earliest = candles_df.iloc[0]['open']
            latest = candles_df.iloc[-1]['close']
            pct_30d = (latest - earliest) / earliest if earliest != 0 else 0.0
        except:
            pct_30d = None
    details['30d_pct_change'] = pct_30d
    if pct_30d is not None:
        # map -100%..+100% into 0..1
        perf_norm = (pct_30d + 1) / 2
        perf_norm = max(0.0, min(1.0, perf_norm))
        A15 = to_0_5(perf_norm)
    else:
        A15 = 2.5

    # Combine K: weights market cap 40%, volume 30%, perf 30%
    K = round(A1*0.4 + A5*0.3 + A15*0.3, 3)
    details['K_components'] = {"A1_market_cap":A1, "A5_volume":A5, "A15_perf":A15}

    # M-Score proxies
    stars = github_data.get('stargazers_count') if github_data else None
    details['github_stars'] = stars
    B1 = to_0_5(min(1.0, (stars or 0) / 50000.0))  # 50k stars -> top
    # community via CoinGecko
    twitter = cg_data.get('community_data',{}).get('twitter_followers') if cg_data else None
    reddit = cg_data.get('community_data',{}).get('reddit_subscribers') if cg_data else None
    details['coingecko_twitter_followers'] = twitter
    details['coingecko_reddit_subscribers'] = reddit
    tw_norm = min(1.0, (twitter or 0) / 5e6)
    rd_norm = min(1.0, (reddit or 0) / 5e6)
    B6 = to_0_5((tw_norm + rd_norm) / 2)
    B5 = 2.5  # incentives fallback neutral
    M = round(B1*0.4 + B6*0.4 + B5*0.2, 3)
    details['M_components'] = {"B1_github":B1, "B6_community":B6, "B5_incentives":B5}

    # R-Score components
    # r_tech: open_issues / stars heuristic
    r_tech = 0.5
    if github_data and github_data.get('stargazers_count') is not None:
        s = github_data.get('stargazers_count', 0)
        issues = github_data.get('open_issues_count', 0)
        if s > 0:
            ratio = issues / s
            r_tech = min(0.9, max(0.1, 0.2 + ratio * 1.2))
    details['r_tech_calc'] = r_tech

    # r_reg fallback default (transparent)
    r_reg = 0.3
    details['r_reg_note'] = "Regulatory risk uses conservative default (0.3). Optionally check news feeds."

    # r_fin volatility
    r_fin = 0.4
    if candles_df is not None and len(candles_df) >= 2:
        closes = candles_df['close'].values
        returns = np.diff(closes) / closes[:-1]
        vol = np.std(returns) * math.sqrt(365) if len(returns) > 0 else 0.0
        vol_norm = min(1.0, vol / 3.0)
        r_fin = 0.1 + vol_norm * 0.8
    details['r_fin_calc'] = r_fin

    R = round(r_tech*0.4 + r_reg*0.35 + r_fin*0.25, 3)

    # OTS as alpha-weighted K/M
    OTS = round(K * alpha + M * (1 - alpha), 3)
    RAR = round(OTS * (1 - R), 3)

    return {
        "price": price,
        "volume": volume,
        "K": K,
        "M": M,
        "OTS": OTS,
        "R": R,
        "RAR": RAR,
        "details": details
    }

# ---------------------------
# PRESENTATION HELPERS
# ---------------------------
def pct(score_0_5):
    return int(max(0, min(100, round((score_0_5/5.0)*100))))

def human_big(n):
    try:
        return f"{n:,.0f}"
    except:
        return str(n)

# ---------------------------
# UI: Inputs (English)
# ---------------------------
st.markdown("### Inputs")
col1, col2, col3 = st.columns([3,2,2])
with col1:
    profile = st.selectbox("Select investment profile", ["Conservative","Balanced","Growth"])
with col2:
    markets = fetch_bitvavo_markets()
    market_choice = st.selectbox("Select crypto (Bitvavo EUR market)", markets if markets else ["BTC-EUR"])
with col3:
    cg_override = st.text_input("CoinGecko ID (optional)", value="")
    repo_input = st.text_input("GitHub repo (optional, e.g. bitcoin/bitcoin)", value="bitcoin/bitcoin")
alpha_map = {"Conservative":0.7, "Balanced":0.6, "Growth":0.5}
alpha = alpha_map.get(profile, 0.6)
st.markdown("---")

# ---------------------------
# RUN ANALYSIS
# ---------------------------
if st.button("Generate CMEF X Report"):
    st.info("Fetching data (Bitvavo / CoinGecko / GitHub)... please wait.")
    ticker = fetch_bitvavo_ticker_24h(market_choice)
    candles = fetch_bitvavo_candles(market_choice, interval="1d", limit=31)
    base_symbol = market_choice.split("-")[0].lower()

    # CoinGecko id resolution
    coin_id = cg_override.strip() or coingecko_find_coin_id(base_symbol)
    cg_data = fetch_coingecko_coin(coin_id) if coin_id else None
    github_data = fetch_github_repo(repo_input) if repo_input.strip() else None

    if not ticker or ticker.get("last",0) <= 0:
        st.error("❌ Could not fetch Bitvavo market data. Check connection or select another market.")
    else:
        scores = compute_cmef(market_choice, ticker, candles, cg_data, github_data, alpha)

        # Top KPIs
        st.subheader("Live market & CMEF X summary")
        a1,a2,a3,a4,a5,a6 = st.columns([2,1,1,1,1,1])
        a1.metric("Market (Bitvavo)", market_choice)
        a1.metric("Current Price (EUR)", f"€{scores['price']:,.2f}")
        a2.metric("K-Score", f"{scores['K']:.2f}/5")
        a3.metric("M-Score", f"{scores['M']:.2f}/5")
        a4.metric("OTS", f"{scores['OTS']:.2f}/5")
        a5.metric("R-Score", f"{scores['R']:.3f} (0..1)")
        a6.metric("RAR", f"{scores['RAR']:.2f}/5")

        st.markdown("### Visual summary")
        # Progress bars row
        pb1,pb2,pb3,pb4,pb5 = st.columns(5)
        pb1.progress(pct(scores['K'])); pb1.caption("K-Score")
        pb2.progress(pct(scores['M'])); pb2.caption("M-Score")
        pb3.progress(pct(scores['OTS'])); pb3.caption("OTS")
        # convert R to 0..5 (visual)
        r_visual = scores['R'] * 5
        pb4.progress(pct(r_visual)); pb4.caption("R-Score (risk)")
        pb5.progress(pct(scores['RAR'])); pb5.caption("RAR (risk-adjusted)")

        # Price chart
        st.subheader("Price history (last 30 days)")
        if candles is not None:
            chart_df = candles.set_index('timestamp')[['close']]
            st.line_chart(chart_df)
            # volatility
            closes = candles['close'].values
            if len(closes) >= 2:
                returns = np.diff(closes) / closes[:-1]
                vol_30d = np.std(returns) * np.sqrt(365)
                st.write(f"Approx. annualized volatility (derived): **{vol_30d:.2%}**")
        else:
            st.write("No historical candle data available.")

        # Bar chart summary of scores (native)
        st.subheader("Score breakdown")
        score_df = pd.DataFrame({
            "metric":["K","M","OTS","R_scaled(0-5)","RAR"],
            "value":[scores['K'], scores['M'], scores['OTS'], scores['R']*5, scores['RAR']]
        }).set_index("metric")
        st.bar_chart(score_df)

        # Full textual CMEF X report
        st.subheader("Full CMEF X Report (structured)")
        md = []
        md.append(f"### CMEF X Report — {market_choice}")
        md.append(f"**Profile:** {profile} (α quality = {alpha})")
        md.append(f"**Generated:** {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
        md.append("---")
        md.append("#### 1) Market Overview")
        md.append(f"- **Price (EUR):** €{scores['price']:,.2f} (Bitvavo ticker/24h)")
        md.append(f"- **24h Volume:** {human_big(scores['volume'])} (Bitvavo ticker/24h)")
        if scores['details'].get('sources',{}).get('coingecko_market_cap_eur') is not None:
            md.append(f"- **Market cap (EUR):** €{scores['details']['sources']['coingecko_market_cap_eur']:,.0f} (CoinGecko)")
        else:
            md.append("- **Market cap (EUR):** not available via CoinGecko lookup")

        md.append("")
        md.append("#### 2) Current Investment Quality — K-Score")
        md.append(f"- Market cap proxy: **{scores['details']['K_components']['A1_market_cap']:.2f}/5**")
        md.append(f"- Liquidity (24h volume) proxy: **{scores['details']['K_components']['A5_volume']:.2f}/5**")
        md.append(f"- 30d performance proxy: **{scores['details']['K_components']['A15_perf']:.2f}/5**")
        md.append(f"**K-Score combined:** **{scores['K']:.2f}/5**")

        md.append("")
        md.append("#### 3) Megalith (Growth) Potential — M-Score")
        md.append(f"- GitHub stars proxy: **{scores['details']['M_components']['B1_github']:.2f}/5**")
        md.append(f"- Community proxy (Twitter/Reddit): **{scores['details']['M_components']['B6_community']:.2f}/5**")
        md.append(f"- Incentives proxy (staking/vesting): **{scores['details']['M_components']['B5_incentives']:.2f}/5**")
        md.append(f"**M-Score combined:** **{scores['M']:.2f}/5**")

        md.append("")
        md.append("#### 4) Risk Analysis (R-Score)")
        md.append(f"- Technical risk (issues/stars heuristic): **{scores['details']['r_tech']:.3f}**")
        md.append(f"- Regulatory risk (default): **{scores['details']['r_reg_note']}**")
        md.append(f"- Financial/volatility risk (derived): **{scores['details']['r_fin_calc']:.3f}**")
        md.append(f"**R-Score (combined 0..1):** **{scores['R']:.3f}**")

        md.append("")
        md.append("#### 5) Combined & Risk-adjusted")
        md.append(f"- **OTS (alpha-weighted K/M):** **{scores['OTS']:.3f}/5**")
        md.append(f"- **RAR (risk-adjusted):** **{scores['RAR']:.3f}/5**")

        # Portfolio recommendation mapping
        if scores['RAR'] >= 65:
            rec = "Core"
        elif scores['RAR'] >= 50:
            rec = "Tactical / Core"
        elif scores['RAR'] >= 35:
            rec = "Small / Cautious"
        elif scores['RAR'] >= 20:
            rec = "Speculative / Small"
        else:
            rec = "Avoid"

        md.append("")
        md.append("#### 6) Portfolio Recommendation")
        md.append(f"- **Suggested action for profile {profile}: {rec}**")
        md.append("")
        md.append("#### 7) Sources & Transparency")
        md.append("- Bitvavo API: ticker/24h & candles (live price & volume).")
        md.append("- CoinGecko API: market & community data (if coin id matched).")
        md.append("- GitHub public API: repo stars / forks / open issues (if repo provided).")
        md.append("- Defaults (explicit): regulatory risk default=0.3; some incentives default neutral.")
        md.append("")
        md.append("---")
        md.append("**Audit data (raw)** - use for traceability; consider providing exact CoinGecko id or canonical GitHub repo for improved accuracy.")
        st.markdown("\n".join(md))

        # Raw JSON trace for auditing transparency
        st.subheader("Raw traceable metrics (audit)")
        trace = {
            "bitvavo": {"market": market_choice, "price": scores['price'], "volume": scores['volume']},
            "coin_gecko_id": coin_id if 'coin_id' in locals() else None,
            "coingecko_available": bool(cg_data),
            "github_repo": repo_input if repo_input.strip() else None,
            "github_data_present": bool(github_data),
            "score_details": scores['details'],
            "generated_at": datetime.now().isoformat()
        }
        st.json(trace)
