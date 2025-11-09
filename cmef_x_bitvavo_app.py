# cmef_x_crypto_dashboard.py
"""
CMEF X Crypto Analysis Dashboard (Final)
- Free data only: Bitvavo (market), CoinGecko (market & community), GitHub (dev metrics)
- English UI
- Visual dashboard + full textual CMEF X report
- No paid APIs, no hidden fabricated data (defaults are explicit)
"""

import streamlit as st
import requests
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# ---------------------------
# Constants & Endpoints
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
GITHUB_API_URL = "https://api.github.com/repos"

# App config
st.set_page_config(page_title="CMEF X Crypto Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard (Bitvavo + CoinGecko + GitHub)")

# ---------------------------
# Utility / Data functions
# ---------------------------
@st.cache_data(ttl=300)
def fetch_bitvavo_markets():
    """Return list of EUR-markets (eg 'BTC-EUR') from Bitvavo."""
    try:
        r = requests.get(f"{BITVAVO_API_URL}/markets", timeout=10)
        r.raise_for_status()
        markets = r.json()
        eur = [m["market"] for m in markets if m.get("quote") == "EUR"]
        eur_sorted = sorted(eur)
        return eur_sorted
    except Exception as e:
        st.error(f"Failed to fetch Bitvavo markets: {e}")
        return []

def fetch_bitvavo_ticker_24h(market):
    """Fetch ticker/24h data for market (uses ticker/24h endpoint)."""
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
        st.error(f"Failed to fetch Bitvavo ticker for {market}: {e}")
        return None

def fetch_bitvavo_candles(market, interval="1d", limit=30):
    """Fetch candle data (timestamp, open, high, low, close, volume)."""
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
        st.warning(f"Could not fetch historical candles for {market}: {e}")
        return None

@st.cache_data(ttl=3600)
def coingecko_find_coin_id_by_symbol(symbol, name_hint=None):
    """Find CoinGecko coin id by symbol (best-effort). Returns id or None."""
    try:
        r = requests.get(f"{COINGECKO_API_URL}/coins/list", timeout=10)
        r.raise_for_status()
        coins = r.json()
        symbol = symbol.lower()
        matches = [c for c in coins if c.get("symbol","").lower() == symbol]
        if len(matches) == 1:
            return matches[0]["id"]
        # if multiple matches, try name hint match
        if name_hint:
            for c in matches:
                if name_hint.lower() in c.get("name","").lower():
                    return c["id"]
        # otherwise return first match if exists
        if matches:
            return matches[0]["id"]
        return None
    except Exception as e:
        st.warning(f"Could not fetch CoinGecko coin list: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_coingecko_coin(coin_id):
    """Fetch coin details from CoinGecko including market_data & community_data."""
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
    """Fetch public GitHub repo metadata (stars, forks, issues)."""
    try:
        r = requests.get(f"{GITHUB_API_URL}/{repo_full_name}", timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        st.warning(f"GitHub fetch error for {repo_full_name}: {e}")
        return None

# ---------------------------
# Scoring Helpers (explicit & traceable)
# ---------------------------
def normalize_log(x, ref):
    """Normalize x using log10 scale against reference ref. Return 0..1."""
    if x <= 0:
        return 0.0
    # scale: log10(x) / log10(ref), clipped
    try:
        return min(1.0, max(0.0, math.log10(x) / math.log10(ref)))
    except:
        return 0.0

def score_0_5_from_0_1(x):
    """Convert 0..1 range to 0..5."""
    return round(x * 5, 3)

def compute_cmef_scores(market, ticker24, candles_df, coingeo, github_repo, alpha):
    """
    Compute K, M, R, OTS, RAR.
    All intermediate inputs are recorded and returned in 'sources' for traceability.
    """
    sources = {}
    # Live price & volume (Bitvavo)
    price = ticker24["last"]
    volume = ticker24["volume"]
    sources['bitvavo_price'] = price
    sources['bitvavo_volume'] = volume

    # K-Score components (proxies using available public data)
    # A1 Use case & Moat -> proxy by market cap (CoinGecko) using log scale
    market_cap = None
    if coingeo and coingeo.get('market_data'):
        market_cap = coingeo['market_data'].get('market_cap',{}).get('eur')
    sources['coingecko_market_cap_eur'] = market_cap

    # Normalize market cap: reference top market cap ~ 1.2e12 EUR (approx BTC 2024-2025)
    mc_norm = normalize_log(market_cap if market_cap else 0.0, ref=1.2e12)
    A1 = score_0_5_from_0_1(mc_norm)

    # A5 Market & Liquidity -> use Bitvavo 24h volume relative to 1e9 EUR top reference
    vol_norm = min(1.0, volume / 1e9)  # 1e9 -> 100% liquidity
    A5 = score_0_5_from_0_1(vol_norm)

    # A15 Historical Performance -> use recent 30-day price change
    pct_30d = None
    if candles_df is not None and not candles_df.empty:
        try:
            latest = candles_df.iloc[-1]['close']
            earliest = candles_df.iloc[0]['open']
            pct_30d = (latest - earliest) / earliest if earliest != 0 else 0.0
        except:
            pct_30d = None
    sources['30d_pct_change'] = pct_30d
    if pct_30d is not None:
        # normalize: +100% => max, -100% => 0
        perf_norm = (pct_30d + 1) / 2  # maps -1..+1 -> 0..1
        perf_norm = max(0.0, min(1.0, perf_norm))
        A15 = score_0_5_from_0_1(perf_norm)
    else:
        A15 = 2.5  # neutral default if no history

    # Combine K proxies into K-score (weights simplified to price/market/liquidity/perf)
    # Use: market cap (40%), volume (30%), price performance (30%)
    K_components = {"A1_market_cap":A1, "A5_volume":A5, "A15_perf":A15}
    K = round(A1*0.4 + A5*0.3 + A15*0.3, 3)

    # M-Score (growth potential)
    # B1 Innovation & Disruptive Power -> proxy via GitHub stars (if repo provided)
    github_stars = github_repo.get('stargazers_count') if github_repo else None
    sources['github_stars'] = github_stars
    # normalize stars: 0..50000 -> 0..1 (50000 -> 1.0)
    stars_norm = min(1.0, (github_stars or 0) / 50000.0)
    B1 = score_0_5_from_0_1(stars_norm)

    # B6 Viral Network Effect & B10 Branding & Sentiment -> use CoinGecko community data if present
    twitter_followers = None
    reddit_subs = None
    if coingeo:
        community = coingeo.get('community_data', {})
        twitter_followers = community.get('twitter_followers')
        reddit_subs = community.get('reddit_subscribers')
    sources['coingecko_twitter_followers'] = twitter_followers
    sources['coingecko_reddit_subscribers'] = reddit_subs

    # Normalize twitter & reddit to 0..1 using reference
    tw_norm = min(1.0, (twitter_followers or 0) / 5e6)  # 5 million -> top
    rd_norm = min(1.0, (reddit_subs or 0) / 5e6)
    B6 = score_0_5_from_0_1((tw_norm + rd_norm) / 2)

    # B5 Long-term incentives: tokenomics - use CoinGecko 'staking' or developer data not always available -> fallback neutral
    B5 = 2.5

    # Combine M score: weights B1 (40%), B6 (40%), B5 (20%)
    M_components = {"B1_github":B1, "B6_community":B6, "B5_incentives":B5}
    M = round(B1*0.4 + B6*0.4 + B5*0.2, 3)

    # R-Score (risk components)
    # R_tech: proxy by open_issues to stars ratio (more open issues per star -> higher technical risk)
    r_tech = 0.5  # default
    if github_repo and github_repo.get('stargazers_count') is not None:
        stars = github_repo.get('stargazers_count', 0)
        open_issues = github_repo.get('open_issues_count', 0)
        if stars > 0:
            issues_per_star = open_issues / stars
            # map issues_per_star 0..0.5 -> risk 0.2..0.8
            r_tech = min(0.9, max(0.1, 0.2 + issues_per_star * 1.2))
    sources['r_tech_calc'] = r_tech

    # R_reg: regulatory risk - we cannot fetch global legal news reliably without paid news API.
    # Therefore we use a conservative default and expose it clearly in report.
    r_reg = 0.3  # default (lower means less regulatory concern)
    sources['r_reg_note'] = "Regulatory risk uses conservative default (0.3) — public news checks recommended."

    # R_fin: volatility risk -> use 30-day volatility (std dev of daily returns)
    r_fin = 0.4  # default
    if candles_df is not None and len(candles_df) >= 2:
        closes = candles_df['close'].values
        returns = np.diff(closes) / closes[:-1]
        vol = np.std(returns) * math.sqrt(365)  # annualized approx
        # Map vol to 0..1 where vol 0 => 0, vol 3 (~300%) => 1
        vol_norm = min(1.0, vol / 3.0)
        # higher vol -> higher risk; map to 0.1..0.9
        r_fin = 0.1 + vol_norm * 0.8
    sources['r_fin_calc'] = r_fin
    # Combine R
    R = round(r_tech*0.4 + r_reg*0.35 + r_fin*0.25, 3)

    # OTS & RAR
    OTS = round(K * 1.0, 3)  # K already on 0..5 scale; note: original OTS mixes K and M by alpha; we'll compute OTS as weighted
    # To follow original: OTS_final = K*alpha + M*(1-alpha)
    OTS_final = round(K * alpha + M * (1 - alpha), 3)
    RAR = round(OTS_final * (1 - R), 3)

    # Prepare detailed source info to display in report
    details = {
        "sources": sources,
        "K_components": K_components,
        "M_components": M_components,
        "r_tech": r_tech,
        "r_reg": r_reg,
        "r_fin": r_fin,
    }

    results = {
        "price": price,
        "volume": volume,
        "K": K,
        "M": M,
        "OTS_raw": OTS,
        "OTS": OTS_final,
        "R": R,
        "RAR": RAR,
        "details": details
    }
    return results

# ---------------------------
# Presentation Helpers
# ---------------------------
def score_to_pct(score_0_5):
    """Convert 0..5 score to 0..100% for progress bars"""
    return int(max(0, min(100, round((score_0_5 / 5.0) * 100))))

def colored_box(text, color_bg="#ffffff", color_text="#000000"):
    """Return HTML for colored box (used sparingly)."""
    return f"<div style='background:{color_bg}; padding:10px; border-radius:8px; color:{color_text};'>{text}</div>"

def plot_radar(scores_dict):
    """Plot simple radar using matplotlib (K,M,OTS,R,RAR)."""
    labels = list(scores_dict.keys())
    values = [scores_dict[k] for k in labels]
    # convert 0..5 to 0..1
    vals = [v/5.0 for v in values]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    vals += vals[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(5,5), subplot_kw=dict(polar=True))
    ax.plot(angles, vals, 'o-', linewidth=2)
    ax.fill(angles, vals, alpha=0.25)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels)
    ax.set_ylim(0,1)
    return fig

# ---------------------------
# ----- UI: Inputs -----
# ---------------------------
st.markdown("### Inputs")
col1, col2, col3 = st.columns([3,2,2])
with col1:
    profile = st.selectbox("Select investment profile", ["Conservative","Balanced","Growth"])
with col2:
    markets = fetch_bitvavo_markets()
    if markets:
        market_choice = st.selectbox("Select crypto (Bitvavo EUR market)", markets)
    else:
        market_choice = st.text_input("Enter market (e.g. BTC-EUR)", value="BTC-EUR")
with col3:
    cg_override = st.text_input("CoinGecko ID (optional)", value="")
    repo_input = st.text_input("GitHub repo (optional, e.g. bitcoin/bitcoin)", value="bitcoin/bitcoin")

alpha_map = {"Conservative":0.7, "Balanced":0.6, "Growth":0.5}
alpha = alpha_map.get(profile, 0.6)

st.markdown("---")

# ---------------------------
# ----- Fetch Data -----
# ---------------------------
if st.button("Generate CMEF X Report"):
    st.info("Fetching data — this may take a few seconds...")
    # Bitvavo ticker
    ticker = fetch_bitvavo_ticker_24h(market_choice)
    candles = fetch_bitvavo_candles(market_choice, interval="1d", limit=31)  # 31 to compute 30-day change
    # Map market base (BTC-EUR -> BTC) to coin symbol
    base_symbol = market_choice.split("-")[0].lower()

    # CoinGecko id
    if cg_override.strip():
        coin_id = cg_override.strip()
    else:
        coin_id = coingecko_find_coin_id_by_symbol(base_symbol)
    coingeo = fetch_coingecko_coin(coin_id) if coin_id else None

    # GitHub repo
    github_repo = fetch_github_repo(repo_input) if repo_input.strip() else None

    if not ticker or ticker.get("last",0) <= 0:
        st.error("Could not fetch market data from Bitvavo. Please check selection or connection.")
    else:
        # compute scores
        scores = compute_cmef_scores(market_choice, ticker, candles, coingeo, github_repo, alpha)

        # Top KPI row
        st.subheader("Live market & CMEF X summary")
        kcol1, kcol2, kcol3, kcol4, kcol5, kcol6 = st.columns([2,1,1,1,1,1])
        kcol1.metric("Market (Bitvavo)", market_choice)
        kcol1.metric("Current Price (EUR)", f"€{scores['price']:,.2f}")
        kcol2.metric("K-Score", f"{scores['K']:.2f}/5")
        kcol3.metric("M-Score", f"{scores['M']:.2f}/5")
        kcol4.metric("OTS", f"{scores['OTS']:.2f}/5")
        kcol5.metric("R-Score", f"{scores['R']:.2f}/1")  # R expressed 0..1
        kcol6.metric("RAR-Score", f"{scores['RAR']:.2f}/5")

        # Progress bars (visual)
        st.subheader("Score progress")
        pcol1, pcol2, pcol3, pcol4, pcol5 = st.columns(5)
        pcol1.progress(score_to_pct(scores['K']))
        pcol1.caption("K-Score")
        pcol2.progress(score_to_pct(scores['M']))
        pcol2.caption("M-Score")
        pcol3.progress(score_to_pct(scores['OTS']))
        pcol3.caption("OTS")
        # convert R (0..1) to 0..5 scale visually (higher risk -> higher red bar)
        r_vis = scores['R'] * 5
        pcol4.progress(score_to_pct(r_vis))
        pcol4.caption("R-Score (risk)")
        pcol5.progress(score_to_pct(scores['RAR']))
        pcol5.caption("RAR (risk-adjusted)")

        # Historical price chart + volatility
        st.subheader("Price history & volatility")
        if candles is not None:
            price_df = candles.copy()
            price_df = price_df.set_index('timestamp')
            st.line_chart(price_df['close'])
            # compute 30-day volatility (std dev of daily returns)
            closes = price_df['close'].values
            if len(closes) >= 2:
                returns = np.diff(closes)/closes[:-1]
                vol_30d = np.std(returns) * np.sqrt(365)  # approx annualized
                st.write(f"30-day approximate annualized volatility (derived): {vol_30d:.2%}")
        else:
            st.write("No historical candle data available for this market.")

        # Radar chart
        st.subheader("Visual score profile")
        radar_scores = {"K":scores['K'], "M":scores['M'], "OTS":scores['OTS'], "R":scores['R']*5, "RAR":scores['RAR']}
        fig = plot_radar(radar_scores)
        st.pyplot(fig)

        # Full textual CMEF X report (well-structured)
        st.subheader("Full CMEF X Report")
        # Build report content with traceability notes
        report_md = []
        report_md.append(f"### CMEF X Report — {market_choice}")
        report_md.append(f"**Profile:** {profile} — α (quality) = {alpha}")
        report_md.append(f"**Generated:** {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
        report_md.append("---")
        report_md.append("#### Market Overview")
        report_md.append(f"- **Price (EUR)**: €{scores['price']:,.2f} (Bitvavo ticker/24h).")
        report_md.append(f"- **24h Volume**: {scores['volume']:,.0f} (Bitvavo ticker/24h).")
        if scores['details']['sources'].get('coingecko_market_cap_eur'):
            report_md.append(f"- **Market cap (EUR)**: €{scores['details']['sources']['coingecko_market_cap_eur']:,.0f} (CoinGecko).")
        else:
            report_md.append("- **Market cap (EUR)**: not available from CoinGecko for this asset (optional CoinGecko id needed).")

        report_md.append("")
        report_md.append("#### K-Score (Current Investment Quality) — components")
        report_md.append(f"- Market cap proxy score: **{scores['details']['K_components']['A1_market_cap']:.2f}/5**")
        report_md.append(f"- Liquidity (volume) proxy score: **{scores['details']['K_components']['A5_volume']:.2f}/5**")
        report_md.append(f"- Recent performance (30d) proxy score: **{scores['details']['K_components']['A15_perf']:.2f}/5**")
        report_md.append(f"**K-Score (combined)**: **{scores['K']:.2f}/5**")

        report_md.append("")
        report_md.append("#### M-Score (Megalith / Growth Potential) — components")
        report_md.append(f"- GitHub stars proxy: **{scores['details']['M_components']['B1_github']:.2f}/5**")
        report_md.append(f"- Community proxy (Twitter/Reddit): **{scores['details']['M_components']['B6_community']:.2f}/5**")
        report_md.append(f"- Long-term incentives proxy (tokenomics / staking): **{scores['details']['M_components']['B5_incentives']:.2f}/5**")
        report_md.append(f"**M-Score (combined)**: **{scores['M']:.2f}/5**")

        report_md.append("")
        report_md.append("#### Risk Analysis (R-Score) — components")
        report_md.append(f"- Technical risk (issues/star ratio): **{scores['details']['r_tech']:.2f}**")
        report_md.append(f"- Regulatory risk: **{scores['details']['r_reg']:.2f}** (conservative default; check news for jurisdictional/regulatory events).")
        report_md.append(f"- Financial/Volatility risk (derived from price history): **{scores['details']['r_fin']:.2f}**")
        report_md.append(f"**R-Score (combined)**: **{scores['R']:.3f}** (0 = no risk, 1 = high risk)")

        report_md.append("")
        report_md.append("#### Combined & Risk-adjusted")
        report_md.append(f"- **OTS (alpha-weighted K/M)**: **{scores['OTS']:.2f}/5** (K*α + M*(1-α))")
        report_md.append(f"- **RAR (risk-adjusted)**: **{scores['RAR']:.2f}/5** (OTS × (1 − R))")

        # Portfolio recommendation logic
        rec = ""
        if scores['RAR'] >= 65:
            rec = "Core"
        elif scores['RAR'] >= 50:
            rec = "Tactical / Core"
        elif scores['RAR'] >= 35:
            rec = "Small / Cautious"
        elif scores['RAR'] >= 20:
            rec = "Speculative / Avoid for Conservative"
        else:
            rec = "Avoid / Very speculative"

        report_md.append("")
        report_md.append("#### Portfolio Recommendation")
        report_md.append(f"- **Suggested action for profile {profile}: {rec}**")
        report_md.append("")
        report_md.append("#### Transparency & Sources")
        report_md.append("- Bitvavo API (ticker/24h, candles) — live price & volume.")
        report_md.append("- CoinGecko API — market & community data (when coin id matched).")
        report_md.append("- GitHub public API — repository stars, forks and issues (if repo provided).")
        report_md.append("- Any default assumptions are explicitly listed (regulatory default, long-term incentives default).")
        report_md.append("")
        report_md.append("---")
        report_md.append("**Notes & next steps**")
        report_md.append("- To improve M & R scores, optionally provide a CoinGecko coin id and/or the canonical GitHub repo.")
        report_md.append("- For regulatory intelligence, integrate a news / legal feed (not required, optional).")

        st.markdown("\n".join(report_md))

        # Footer: show traceable values and exact timestamps
        st.subheader("Raw traceable metrics (for audit)")
        st.json({
            "bitvavo": {
                "market": market_choice,
                "price": scores['price'],
                "volume": scores['volume']
            },
            "coingecko_id": coin_id if 'coin_id' in locals() else None,
            "coingecko_metrics_available": bool(coingeo),
            "github_repo_provided": repo_input,
            "github_repo_data_present": bool(github_repo),
            "score_details": scores['details'],
            "generated_at": datetime.now().isoformat()
        })
