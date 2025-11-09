# cmef_x_crypto_dashboard.py
"""
Final CMEF X Crypto Dashboard (matplotlib-free)
- User selects coin (name) and investment profile only.
- Auto-resolves Bitvavo market, CoinGecko id, and canonical GitHub repo (if available).
- Uses free public data: Bitvavo, CoinGecko, GitHub (no paid APIs or keys).
- Produces visual dashboard + full textual CMEF X report.
"""

import streamlit as st
import requests
import math
import pandas as pd
import numpy as np
from datetime import datetime
from urllib.parse import urlparse

# ---------------------------
# Endpoints
# ---------------------------
BITVAVO_API_URL = "https://api.bitvavo.com/v2"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
GITHUB_API_URL = "https://api.github.com/repos"

# ---------------------------
# Streamlit page config
# ---------------------------
st.set_page_config(page_title="CMEF X Crypto Dashboard", layout="wide")
st.title("🪙 CMEF X — Free Crypto Analysis Dashboard (Auto-resolve)")

# ---------------------------
# Helpers: safe fetchers with caching
# ---------------------------
@st.cache_data(ttl=600)
def fetch_bitvavo_markets():
    try:
        r = requests.get(f"{BITVAVO_API_URL}/markets", timeout=10)
        r.raise_for_status()
        markets = r.json()
        # map markets by base symbol -> list of available markets (prefer EUR)
        return markets
    except Exception as e:
        st.warning(f"Bitvavo markets fetch failed: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_bitvavo_ticker_24h(market):
    try:
        r = requests.get(f"{BITVAVO_API_URL}/ticker/24h?market={market}", timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            data = data[0]
        return {"last": float(data.get("last", 0)), "volume": float(data.get("volume", 0)), "high": float(data.get("high",0)), "low": float(data.get("low",0))}
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
        # return None but do not crash
        st.info(f"Could not fetch candles for {market}: {e}")
        return None

@st.cache_data(ttl=3600)
def coingecko_coin_list():
    try:
        r = requests.get(f"{COINGECKO_API_URL}/coins/list", timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"CoinGecko coin list fetch failed: {e}")
        return []

@st.cache_data(ttl=300)
def fetch_coingecko_coin(coin_id):
    if not coin_id:
        return None
    try:
        r = requests.get(f"{COINGECKO_API_URL}/coins/{coin_id}", params={"localization":"false","tickers":"false","market_data":"true","community_data":"true","developer_data":"true","sparkline":"false"}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.info(f"CoinGecko fetch for {coin_id} failed: {e}")
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
        st.info(f"GitHub fetch failed for {repo_full_name}: {e}")
        return None

# ---------------------------
# Utility functions
# ---------------------------
def find_best_bitvavo_market_for_coin(markets_raw, coin_name, symbol_hint=None):
    """
    Given Bitvavo markets JSON and coin name/symbol hint, return a best market string like "BTC-EUR".
    Preference: market quote 'EUR'. Fallback: first market found for base symbol.
    """
    if not markets_raw:
        return None
    # Build mapping base -> list of markets
    mapping = {}
    for m in markets_raw:
        base = m.get("base")
        market_str = m.get("market")
        if not base or not market_str:
            continue
        mapping.setdefault(base.upper(), []).append(m)
    # Try symbol_hint first (e.g. ADA)
    if symbol_hint:
        base = symbol_hint.upper()
        if base in mapping:
            # prefer EUR quote
            for m in mapping[base]:
                if m.get("quote") == "EUR":
                    return m.get("market")
            return mapping[base][0].get("market")
    # If no symbol hint, try to match by coin name to base (e.g. "Cardano" -> ADA)
    # Many coin names include symbol in parentheses in CoinGecko; best effort: look for exact base in mapping keys
    # As fallback, attempt to find by matching market where name appears in market['market'] or id
    # Simplest fallback: pick BTC-EUR if nothing else
    return "BTC-EUR" if "BTC-EUR" in [m.get("market") for m in markets_raw] else next(iter(mapping.values()))[0].get("market")

def resolve_coingecko_id_from_name(coin_list, coin_name):
    if not coin_list:
        return None
    # try exact name match (case-insensitive)
    cn = coin_name.strip().lower()
    exact = [c for c in coin_list if c.get("name","").strip().lower() == cn]
    if exact:
        return exact[0]['id']
    # try symbol match where coin_name might be symbol
    sym = coin_name.strip().lower()
    symmatches = [c for c in coin_list if c.get("symbol","").lower() == sym]
    if len(symmatches) == 1:
        return symmatches[0]['id']
    # try partial name contains
    partial = [c for c in coin_list if cn in c.get("name","").lower()]
    if partial:
        return partial[0]['id']
    # fallback None
    return None

def extract_github_repo_from_coingecko(cg_info):
    """
    Attempt to extract canonical GitHub repo from CoinGecko 'links' -> 'repos_url' fields.
    Returns first reasonable repo string 'owner/repo' or None.
    """
    if not cg_info:
        return None
    try:
        repos = cg_info.get('links', {}).get('repos_url', {}) or {}
        github_urls = []
        # repos_url may have lists under keys like 'github'
        if isinstance(repos, dict):
            for k, v in repos.items():
                if isinstance(v, list):
                    for url in v:
                        if "github.com" in (url or ""):
                            github_urls.append(url)
        elif isinstance(repos, list):
            for url in repos:
                if "github.com" in (url or ""):
                    github_urls.append(url)
        # Also check links -> homepage or source_code
        # Normalize first github url to owner/repo
        for url in github_urls:
            try:
                parsed = urlparse(url)
                path = parsed.path.strip("/")
                # drop possible .git suffix
                if path.endswith(".git"):
                    path = path[:-4]
                parts = path.split("/")
                # want owner/repo
                if len(parts) >= 2:
                    owner_repo = f"{parts[0]}/{parts[1]}"
                    return owner_repo
            except:
                continue
    except:
        pass
    return None

# ---------------------------
# Scoring primitives (transparent)
# ---------------------------
def normalize_log(x, ref):
    if x is None or x <= 0:
        return 0.0
    try:
        return min(1.0, max(0.0, math.log10(x) / math.log10(ref)))
    except:
        return 0.0

def to_score_0_5(value_0_1):
    return round(max(0.0, min(5.0, value_0_1 * 5.0)), 3)

def compute_cmef_scores(market, ticker, candles, cg_info, gh_repo_obj, alpha):
    """
    Compute K, M, R, OTS, RAR with traceable inputs and conservative defaults when missing.
    Returns dict with results and a 'trace' sub-dict.
    """
    trace = {}
    # Basic market inputs (Bitvavo)
    price = ticker.get("last", 0)
    volume = ticker.get("volume", 0)
    trace['bitvavo_price'] = price
    trace['bitvavo_volume'] = volume

    # K-Score proxies
    market_cap_eur = None
    if cg_info and cg_info.get('market_data'):
        market_cap_eur = cg_info['market_data'].get('market_cap', {}).get('eur')
    trace['coingecko_market_cap_eur'] = market_cap_eur

    # A1: market cap proxy (log-normalized)
    A1 = to_score_0_5(normalize_log(market_cap_eur if market_cap_eur else 0.0, ref=1.2e12))
    # A5: liquidity proxy (bitvavo 24h volume relative to 1e9)
    A5 = to_score_0_5(min(1.0, volume / 1e9))
    # A15: historical performance 30d
    pct_30d = None
    if candles is not None and len(candles) >= 2:
        try:
            earliest = candles.iloc[0]['open']
            latest = candles.iloc[-1]['close']
            pct_30d = (latest - earliest) / earliest if earliest != 0 else 0.0
        except:
            pct_30d = None
    trace['30d_pct_change'] = pct_30d
    if pct_30d is not None:
        perf_norm = (pct_30d + 1) / 2  # map -1..+1 -> 0..1
        perf_norm = max(0.0, min(1.0, perf_norm))
        A15 = to_score_0_5(perf_norm)
    else:
        A15 = 2.5  # neutral fallback

    # Combine K (weights: mc 40%, vol 30%, perf 30%)
    K = round(A1*0.4 + A5*0.3 + A15*0.3, 3)
    trace['K_components'] = {"A1_market_cap":A1, "A5_volume":A5, "A15_perf":A15}

    # M-Score proxies
    github_stars = gh_repo_obj.get('stargazers_count') if gh_repo_obj else None
    trace['github_stars'] = github_stars
    B1 = to_score_0_5(min(1.0, (github_stars or 0) / 50000.0))  # 50k stars -> top
    # community data from CoinGecko
    twitter_followers = None
    reddit_subs = None
    if cg_info:
        community = cg_info.get('community_data', {})
        twitter_followers = community.get('twitter_followers')
        reddit_subs = community.get('reddit_subscribers')
    trace['coingecko_twitter_followers'] = twitter_followers
    trace['coingecko_reddit_subscribers'] = reddit_subs
    tw_norm = min(1.0, (twitter_followers or 0) / 5e6)
    rd_norm = min(1.0, (reddit_subs or 0) / 5e6)
    B6 = to_score_0_5((tw_norm + rd_norm) / 2)
    B5 = 2.5  # incentives fallback neutral
    M = round(B1*0.4 + B6*0.4 + B5*0.2, 3)
    trace['M_components'] = {"B1_github":B1, "B6_community":B6, "B5_incentives":B5}

    # R-Score components
    # r_tech: heuristic open_issues / stars
    r_tech = 0.5
    if gh_repo_obj and gh_repo_obj.get('stargazers_count') is not None:
        s = gh_repo_obj.get('stargazers_count', 0)
        issues = gh_repo_obj.get('open_issues_count', 0)
        if s > 0:
            ratio = issues / s
            r_tech = min(0.9, max(0.1, 0.2 + ratio * 1.2))
    trace['r_tech_calc'] = r_tech

    # r_reg: default conservative
    r_reg = 0.3
    trace['r_reg_note'] = "Used conservative default (0.3); integrate news feed for live regulatory signal."

    # r_fin: volatility from candles
    r_fin = 0.4
    if candles is not None and len(candles) >= 2:
        closes = candles['close'].values
        returns = np.diff(closes) / closes[:-1]
        if len(returns) > 0:
            vol = np.std(returns) * math.sqrt(365)
            vol_norm = min(1.0, vol / 3.0)
            r_fin = 0.1 + vol_norm * 0.8
    trace['r_fin_calc'] = r_fin

    R = round(r_tech*0.4 + r_reg*0.35 + r_fin*0.25, 3)

    # OTS (alpha-weighted K/M) and RAR
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
        "trace": trace,
        "market": market
    }

# ---------------------------
# Presentation helpers
# ---------------------------
def pct(score_0_5):
    return int(max(0, min(100, round((score_0_5 / 5.0) * 100))))

def human(n):
    try:
        return f"{n:,.0f}"
    except:
        return str(n)

# ---------------------------
# UI: Inputs (English)
# ---------------------------
st.markdown("### Inputs")
col1, col2 = st.columns([3,2])
with col1:
    # Provide a dropdown of CoinGecko's common names for ease-of-use
    coin_list = coingecko_coin_list()
    # Build a friendly name dropdown (top coins first). If coin_list missing, fallback simple text input.
    if coin_list:
        # sort by popularity: try common coins first (filter by known list)
        common = ["bitcoin","ethereum","cardano","ripple","litecoin","tron","polkadot","dogecoin","chainlink","stellar"]
        names = []
        seen = set()
        for c in coin_list:
            nm = c.get("name")
            if nm and nm not in seen:
                seen.add(nm)
                names.append(nm)
        # Make a shortened dropdown: top 300 names for performance
        names_short = names[:300] if len(names) > 300 else names
        coin_name = st.selectbox("Select cryptocurrency (name)", names_short, index=0)
    else:
        coin_name = st.text_input("Enter cryptocurrency name (e.g. Bitcoin)", value="Bitcoin")
with col2:
    profile = st.selectbox("Select investment profile", ["Conservative","Balanced","Growth"])
st.markdown("---")

# ---------------------------
# Generate report button
# ---------------------------
if st.button("Generate CMEF X Report"):
    st.info("Resolving markets (Bitvavo) and CoinGecko / GitHub — please wait...")
    # Resolve coin id
    cg_list = coingecko_coin_list()
    coin_id = resolve_coingecko_id_from_name(cg_list, coin_name) if cg_list else None
    cg_info = fetch_coingecko_coin(coin_id) if coin_id else None

    # Try to resolve symbol hint for Bitvavo market
    symbol_hint = None
    if cg_info:
        # cg_info usually contains symbol
        symbol_hint = cg_info.get('symbol')
    else:
        # try to extract symbol from coin_list fallback
        for c in cg_list or []:
            if c.get('name','').lower() == coin_name.lower():
                symbol_hint = c.get('symbol')
                break

    # Find best Bitvavo market
    bit_markets = fetch_bitvavo_markets()
    best_market = find_best_bitvavo_market_for_coin(bit_markets, coin_name, symbol_hint=symbol_hint)
    ticker = fetch_bitvavo_ticker_24h(best_market) if best_market else None
    candles = fetch_bitvavo_candles(best_market) if best_market else None

    # Get canonical GitHub repo (if CoinGecko provides)
    gh_repo_string = extract_github_repo_from_coingecko(cg_info) if cg_info else None
    gh_obj = fetch_github_repo(gh_repo_string) if gh_repo_string else None

    alpha_map = {"Conservative":0.7, "Balanced":0.6, "Growth":0.5}
    alpha = alpha_map.get(profile, 0.6)

    if not ticker or ticker.get("last",0) <= 0:
        st.error("❌ Could not fetch market price from Bitvavo. Please check your connection or try again.")
    else:
        # compute scores
        results = compute_cmef_scores(best_market, ticker, candles, cg_info, gh_obj, alpha)

        # Top KPIs
        st.subheader("Live market & CMEF X summary")
        c1,c2,c3,c4,c5,c6 = st.columns([2,1,1,1,1,1])
        c1.metric("Market (Bitvavo)", best_market)
        c1.metric("Current Price (EUR)", f"€{results['price']:,.4f}")
        c2.metric("K-Score", f"{results['K']:.3f}/5")
        c3.metric("M-Score", f"{results['M']:.3f}/5")
        c4.metric("OTS", f"{results['OTS']:.3f}/5")
        c5.metric("R-Score", f"{results['R']:.3f} (0..1)")
        c6.metric("RAR", f"{results['RAR']:.3f}/5")

        # Visual summary (progress bars + bar chart)
        st.markdown("### Visual summary")
        p1,p2,p3,p4,p5 = st.columns(5)
        p1.progress(pct(results['K'])); p1.caption("K-Score")
        p2.progress(pct(results['M'])); p2.caption("M-Score")
        p3.progress(pct(results['OTS'])); p3.caption("OTS")
        # convert R to 0..5 for visual bar where higher means worse risk
        p4.progress(pct(results['R']*5)); p4.caption("R-Score (risk)")
        p5.progress(pct(results['RAR'])); p5.caption("RAR (risk-adjusted)")

        st.markdown("#### Score bar chart")
        score_df = pd.DataFrame({
            "metric":["K","M","OTS","R_scaled(0-5)","RAR"],
            "value":[results['K'], results['M'], results['OTS'], results['R']*5, results['RAR']]
        }).set_index("metric")
        st.bar_chart(score_df)

        # Price history
        st.subheader("Price history (last 30 days)")
        if candles is not None:
            chart_df = candles.set_index('timestamp')[['close']]
            st.line_chart(chart_df)
            # compute volatility
            closes = candles['close'].values
            if len(closes) >= 2:
                returns = np.diff(closes) / closes[:-1]
                vol_30d = np.std(returns) * math.sqrt(365)
                st.write(f"Approx. annualized volatility (derived): **{vol_30d:.2%}**")
        else:
            st.info("No historical candle data available for this market (Bitvavo endpoint may not support candles for some markets).")

        # Full textual CMEF X report
        st.subheader("Full CMEF X Report (structured)")
        md = []
        md.append(f"### CMEF X Report — {best_market}")
        md.append(f"**Selected coin name:** {coin_name}")
        md.append(f"**CoinGecko id (auto-resolved):** {coin_id if coin_id else 'not resolved'}")
        md.append(f"**GitHub repo (auto-extracted):** {gh_repo_string if gh_repo_string else 'not found via CoinGecko'}")
        md.append(f"**Profile:** {profile} (α quality = {alpha})")
        md.append(f"**Generated:** {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
        md.append("---")
        md.append("#### 1) Market Overview")
        md.append(f"- **Price (EUR):** €{results['price']:,.4f} (Bitvavo ticker/24h)")
        md.append(f"- **24h Volume:** {human(results['volume'])} (Bitvavo ticker/24h)")
        if results['trace'].get('coingecko_market_cap_eur'):
            md.append(f"- **Market cap (EUR):** €{results['trace']['coingecko_market_cap_eur']:,.0f} (CoinGecko)")
        else:
            md.append("- **Market cap (EUR):** not available (CoinGecko id not resolved or data missing).")

        md.append("")
        md.append("#### 2) K-Score — Current Investment Quality (components)")
        kcomp = results['trace'].get('K_components', {})
        md.append(f"- Market cap proxy: **{kcomp.get('A1_market_cap', 'n/a')}/5**")
        md.append(f"- Liquidity (24h volume) proxy: **{kcomp.get('A5_volume', 'n/a')}/5**")
        md.append(f"- Recent performance (30d) proxy: **{kcomp.get('A15_perf', 'n/a')}/5**")
        md.append(f"**K-Score combined:** **{results['K']:.3f}/5**")

        md.append("")
        md.append("#### 3) M-Score — Growth Potential (components)")
        mcomp = results['trace'].get('M_components', {})
        md.append(f"- GitHub stars proxy: **{mcomp.get('B1_github', 'n/a')}/5** (stars: {results['trace'].get('github_stars', 'n/a')})")
        md.append(f"- Community proxy (Twitter/Reddit): **{mcomp.get('B6_community', 'n/a')}/5**")
        md.append(f"- Incentives proxy (staking/vesting): **{mcomp.get('B5_incentives', 'n/a')}/5**")
        md.append(f"**M-Score combined:** **{results['M']:.3f}/5**")

        md.append("")
        md.append("#### 4) Risk Analysis (R-Score) — components")
        md.append(f"- Technical risk (issues/stars heuristic): **{results['trace'].get('r_tech_calc','n/a'):.3f}**")
        md.append(f"- Regulatory risk (explicit default): **{results['trace'].get('r_reg_note')}**")
        md.append(f"- Financial/Volatility risk (derived): **{results['trace'].get('r_fin_calc','n/a'):.3f}**")
        md.append(f"**R-Score (combined 0..1):** **{results['R']:.3f}**")

        md.append("")
        md.append("#### 5) Combined & Risk-adjusted")
        md.append(f"- **OTS (alpha-weighted K/M):** **{results['OTS']:.3f}/5**")
        md.append(f"- **RAR (risk-adjusted):** **{results['RAR']:.3f}/5**")

        # portfolio recommendation mapping (explicit)
        if results['RAR'] >= 65:
            rec = "Core"
        elif results['RAR'] >= 50:
            rec = "Tactical / Core"
        elif results['RAR'] >= 35:
            rec = "Small / Cautious"
        elif results['RAR'] >= 20:
            rec = "Speculative / Small"
        else:
            rec = "Avoid"

        md.append("")
        md.append("#### 6) Portfolio Recommendation")
        md.append(f"- **Suggested action for profile {profile}: {rec}**")

        md.append("")
        md.append("#### 7) Sources & Transparency")
        md.append("- Bitvavo API: ticker/24h & candles (when available) for live price & volume.")
        md.append("- CoinGecko API: market & community data (auto-resolved ID when possible).")
        md.append("- GitHub public API: repo stars / forks / open issues (if canonical repo found).")
        md.append("- Explicit defaults shown where public data is not available (no hidden fabrication).")
        md.append("")
        md.append("---")
        md.append("**Raw trace (for auditing)**")
        md.append(f"- bitvavo_market: {best_market}")
        md.append(f"- coin_gecko_id: {coin_id if coin_id else 'None'}")
        md.append(f"- github_repo: {gh_repo_string if gh_repo_string else 'None'}")
        md.append(f"- trace object: {results['trace']}")
        st.markdown("\n".join(md))

        # JSON trace for programmatic auditing (expandable)
        st.subheader("Raw traceable metrics (JSON)")
        st.json({
            "market": best_market,
            "price": results['price'],
            "volume": results['volume'],
            "coin_gecko_id": coin_id,
            "coingecko_available": bool(cg_info),
            "github_repo": gh_repo_string,
            "github_data_available": bool(gh_obj),
            "scores": {"K":results['K'], "M":results['M'], "OTS":results['OTS'], "R":results['R'], "RAR":results['RAR']},
            "trace": results['trace'],
            "generated_at": datetime.now().isoformat()
        })

# End of file
