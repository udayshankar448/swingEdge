#!/usr/bin/env python3
"""
SwingEdge EOD Scanner — Stage 3
================================
Scans 500 NSE stocks after market close.
Applies full scoring framework (Minervini + CANSLIM + Van Tharp).
Outputs data.json → push to GitHub → dashboard shows real data.

Usage:
    python3 scanner.py              # Run full scan
    python3 scanner.py --test       # Test with 10 stocks only
    python3 scanner.py --push       # Scan + auto git push to GitHub

Schedule (Mac):
    Runs automatically at 4:30 PM via launchd (see setup_schedule.sh)

Requirements:
    pip3 install yfinance pandas numpy requests
"""

import json
import os
import sys
import time
import subprocess
import argparse
import logging
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import numpy as np

# ─── Optional yfinance import ────────────────────────────────────────────────
try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    print("⚠  yfinance not found. Run: pip3 install yfinance pandas numpy requests")
    sys.exit(1)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scanner.log', mode='a')
    ]
)
log = logging.getLogger('SwingEdge')

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    'capital':          3_000_000,   # ₹30 Lakhs — change to your capital
    'risk_pct':         0.02,        # 2% risk per trade
    'max_pos_pct':      0.20,        # Max 20% of capital per position
    'min_score':        65,          # Minimum composite score to appear in output
    'min_rr':           2.0,         # Minimum Risk:Reward ratio
    'atr_multiplier':   2.0,         # ATR multiplier for stop loss
    'output_file':      'data.json', # Output file (goes in swingEdge folder)
    'data_period':      '1y',        # Historical data period
    'scan_delay':       0.5,         # Seconds between API calls (be polite)
}

# ═══════════════════════════════════════════════════════════════════════════════
# NSE STOCK UNIVERSE — 250 stocks across all tiers
# Format: TICKER.NS (Yahoo Finance NSE format)
# ═══════════════════════════════════════════════════════════════════════════════

NIFTY50 = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'BHARTIARTL.NS', 'ICICIBANK.NS',
    'INFOSYS.NS', 'SBIN.NS', 'HINDUNILVR.NS', 'ITC.NS', 'LT.NS',
    'KOTAKBANK.NS', 'HCLTECH.NS', 'BAJFINANCE.NS', 'MARUTI.NS', 'AXISBANK.NS',
    'ASIANPAINT.NS', 'TITAN.NS', 'SUNPHARMA.NS', 'ULTRACEMCO.NS', 'NESTLEIND.NS',
    'WIPRO.NS', 'TATAMOTORS.NS', 'NTPC.NS', 'POWERGRID.NS', 'TECHM.NS',
    'ONGC.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'COALINDIA.NS', 'ADANIENT.NS',
    'ADANIPORTS.NS', 'BAJAJFINSV.NS', 'DRREDDY.NS', 'CIPLA.NS', 'EICHERMOT.NS',
    'HINDALCO.NS', 'BPCL.NS', 'DIVISLAB.NS', 'GRASIM.NS', 'APOLLOHOSP.NS',
    'TATACONSUM.NS', 'BRITANNIA.NS', 'HEROMOTOCO.NS', 'SHRIRAMFIN.NS', 'BAJAJ-AUTO.NS',
    'M&M.NS', 'INDUSINDBK.NS', 'SBILIFE.NS', 'HDFCLIFE.NS', 'LTIM.NS',
]

MIDCAP150 = [
    'PERSISTENT.NS', 'MPHASIS.NS', 'COFORGE.NS', 'LTTS.NS', 'KPITTECH.NS',
    'SONACOMS.NS', 'MOTHERSON.NS', 'MINDAIND.NS', 'TATAELXSI.NS', 'POLYCAB.NS',
    'DIXON.NS', 'AMBER.NS', 'KAYNES.NS', 'WAAREE.NS', 'PREMIER.NS',
    'HAL.NS', 'BEL.NS', 'BEML.NS', 'MAZDOCK.NS', 'GRSE.NS',
    'MTAR.NS', 'DATAPATT.NS', 'ZENTEC.NS', 'PARAS.NS', 'DCXSYS.NS',
    'RVNL.NS', 'IRFC.NS', 'IRCON.NS', 'RITES.NS', 'TITAGARH.NS',
    'NCC.NS', 'PNCINFRA.NS', 'DILIPBLD.NS', 'ASHOKA.NS', 'KEC.NS',
    'KALPATPOWR.NS', 'TECHNOE.NS', 'ADANIGREEN.NS', 'TATAPOWER.NS', 'SUZLON.NS',
    'INOXWIND.NS', 'BOROSIL.NS', 'E2ETECH.NS', 'NETWEB.NS', 'RAILTEL.NS',
    'HFCL.NS', 'STLTECH.NS', 'TATACHEM.NS', 'DEEPAKNTR.NS', 'AARTIIND.NS',
    'LAURUS.NS', 'GLAND.NS', 'MANKIND.NS', 'ALKEM.NS', 'SUVEN.NS',
    'CAMS.NS', 'CDSL.NS', 'MCX.NS', 'BSE.NS', 'IEX.NS',
    'APLAPOLLO.NS', 'JINDALSAW.NS', 'RATNAMANI.NS', 'WELSPUNLIV.NS', 'SAFARI.NS',
    'VGUARD.NS', 'HAVELLS.NS', 'CROMPTON.NS', 'VOLTAS.NS', 'BLUESTAR.NS',
    'OBEROIRLTY.NS', 'BRIGADE.NS', 'PRESTIGE.NS', 'GODREJPROP.NS', 'PHOENIXLTD.NS',
    'AUROPHARMA.NS', 'TORNTPHARM.NS', 'PFIZER.NS', 'ABBINDIA.NS', 'SANOFI.NS',
    'BANKINDIA.NS', 'CANBK.NS', 'PNB.NS', 'UNIONBANK.NS', 'UCOBANK.NS',
    'MFSL.NS', 'CHOLAFIN.NS', 'MUTHOOTFIN.NS', 'MANAPPURAM.NS', 'M&MFIN.NS',
    'PAGEIND.NS', 'RELAXO.NS', 'BATAINDIA.NS', 'VMART.NS', 'DMART.NS',
    'AMBUJACEM.NS', 'ACC.NS', 'RAMCOCEM.NS', 'JKCEMENT.NS', 'HEIDELBERG.NS',
]

SMALLCAP250 = [
    'IDEAFORGE.NS', 'SYRMA.NS', 'AVALON.NS', 'SGTECH.NS', 'WABAG.NS',
    'IONEXCHNG.NS', 'IDFCFIRSTB.NS', 'RBLBANK.NS', 'AUBANK.NS', 'EQUITASBNK.NS',
    'NUVOCO.NS', 'SAPPHIRE.NS', 'GOKALDAS.NS', 'KITEX.NS', 'ARVIND.NS',
    'GPIL.NS', 'JINDALPOLY.NS', 'SHYAMSTL.NS', 'WELCORP.NS', 'NMDC.NS',
    'HBLENGINE.NS', 'EXIDEIND.NS', 'AMARAJABAT.NS', 'GREENKO.NS', 'RENEW.NS',
    'FIEMIND.NS', 'LUMAX.NS', 'SUPRAJIT.NS', 'ENDURANCE.NS', 'CRAFTSMAN.NS',
    'ASTRAL.NS', 'SUPREMEIND.NS', 'PRINCEPIPE.NS', 'NILKAMAL.NS', 'UFLEX.NS',
    'ZYDUSLIFE.NS', 'NATCOPHARM.NS', 'SOLARA.NS', 'AARTI.NS', 'SHILPAMED.NS',
    'KRBL.NS', 'AVANTIFEED.NS', 'BAJAJCON.NS', 'EMAMILTD.NS', 'MARICO.NS',
    'ZENSAR.NS', 'NIITLTD.NS', 'MASTEK.NS', 'HEXAWARE.NS', 'CYIENT.NS',
]

# Full universe
ALL_STOCKS = list(dict.fromkeys(NIFTY50 + MIDCAP150 + SMALLCAP250))

# ═══════════════════════════════════════════════════════════════════════════════
# MACRO DATA (manual update weekly — or we automate in Stage 5)
# ═══════════════════════════════════════════════════════════════════════════════

MACRO_DATA = {
    'rbi_repo_rate':    5.25,
    'rbi_stance':       'neutral',      # 'easing' / 'neutral' / 'tightening'
    'india_vix':        18.4,
    'cpi':              4.6,
    'gdp_growth':       6.9,
    'fii_10day_cr':     -8240,          # ₹ Cr — negative = selling
    'dii_10day_cr':     12400,          # ₹ Cr
    'usdinr':           90.42,
    'brent_crude':      91.4,
    'nifty_vs_200sma':  4.8,            # % above (+) or below (-) 200 SMA
    'last_updated':     str(date.today()),
}

# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

SECTOR_MAP = {
    # Defence
    'HAL.NS':'Defence', 'BEL.NS':'Defence', 'BEML.NS':'Defence',
    'MAZDOCK.NS':'Defence', 'GRSE.NS':'Defence', 'MTAR.NS':'Defence',
    'DATAPATT.NS':'Defence', 'ZENTEC.NS':'Defence',
    # IT
    'TCS.NS':'IT', 'INFOSYS.NS':'IT', 'WIPRO.NS':'IT', 'HCLTECH.NS':'IT',
    'TECHM.NS':'IT', 'LTIM.NS':'IT', 'PERSISTENT.NS':'IT', 'MPHASIS.NS':'IT',
    'COFORGE.NS':'IT', 'LTTS.NS':'IT', 'KPITTECH.NS':'IT', 'TATAELXSI.NS':'IT',
    'ZENSAR.NS':'IT', 'NIITLTD.NS':'IT', 'MASTEK.NS':'IT', 'CYIENT.NS':'IT',
    # Pharma
    'SUNPHARMA.NS':'Pharma', 'DRREDDY.NS':'Pharma', 'CIPLA.NS':'Pharma',
    'DIVISLAB.NS':'Pharma', 'APOLLOHOSP.NS':'Pharma', 'LAURUS.NS':'Pharma',
    'GLAND.NS':'Pharma', 'MANKIND.NS':'Pharma', 'ALKEM.NS':'Pharma',
    'AUROPHARMA.NS':'Pharma', 'TORNTPHARM.NS':'Pharma', 'NATCOPHARM.NS':'Pharma',
    # Banking
    'HDFCBANK.NS':'Banking', 'ICICIBANK.NS':'Banking', 'SBIN.NS':'Banking',
    'KOTAKBANK.NS':'Banking', 'AXISBANK.NS':'Banking', 'INDUSINDBK.NS':'Banking',
    'BANKINDIA.NS':'PSU Bank', 'CANBK.NS':'PSU Bank', 'PNB.NS':'PSU Bank',
    # NBFC
    'BAJFINANCE.NS':'NBFC', 'BAJAJFINSV.NS':'NBFC', 'CHOLAFIN.NS':'NBFC',
    'MUTHOOTFIN.NS':'NBFC', 'MANAPPURAM.NS':'NBFC', 'M&MFIN.NS':'NBFC',
    # Auto
    'MARUTI.NS':'Auto', 'TATAMOTORS.NS':'Auto', 'M&M.NS':'Auto',
    'HEROMOTOCO.NS':'Auto', 'BAJAJ-AUTO.NS':'Auto', 'EICHERMOT.NS':'Auto',
    'SONACOMS.NS':'Auto', 'MOTHERSON.NS':'Auto',
    # Energy / Renewable
    'NTPC.NS':'Energy', 'POWERGRID.NS':'Energy', 'ONGC.NS':'Energy',
    'BPCL.NS':'Energy', 'COALINDIA.NS':'Energy',
    'ADANIGREEN.NS':'Renewable', 'TATAPOWER.NS':'Renewable',
    'SUZLON.NS':'Renewable', 'INOXWIND.NS':'Renewable', 'WAAREE.NS':'Renewable',
    # Infra
    'LT.NS':'Infra', 'ADANIENT.NS':'Infra', 'ADANIPORTS.NS':'Infra',
    'NCC.NS':'Infra', 'KEC.NS':'Infra', 'KALPATPOWR.NS':'Infra',
    'RVNL.NS':'Infra', 'IRFC.NS':'Infra', 'TITAGARH.NS':'Infra',
    # Electronics / Semi
    'DIXON.NS':'Electronics', 'AMBER.NS':'Electronics', 'KAYNES.NS':'Electronics',
    'SYRMA.NS':'Electronics', 'POLYCAB.NS':'Electronics',
    # EV
    'KPITTECH.NS':'EV', 'SONACOMS.NS':'EV',
    # FMCG
    'HINDUNILVR.NS':'FMCG', 'ITC.NS':'FMCG', 'NESTLEIND.NS':'FMCG',
    'BRITANNIA.NS':'FMCG', 'TATACONSUM.NS':'FMCG', 'MARICO.NS':'FMCG',
    # Metals
    'JSWSTEEL.NS':'Metals', 'TATASTEEL.NS':'Metals', 'HINDALCO.NS':'Metals',
    'COALINDIA.NS':'Metals', 'NMDC.NS':'Metals',
    # Cement
    'ULTRACEMCO.NS':'Cement', 'AMBUJACEM.NS':'Cement', 'ACC.NS':'Cement',
    # Capital Goods
    'SIEMENS.NS':'Capital Goods', 'ABB.NS':'Capital Goods', 'HAVELLS.NS':'Capital Goods',
    'VOLTAS.NS':'Capital Goods', 'BLUESTAR.NS':'Capital Goods',
}

# Theme classification
THEME_MAP = {
    'Defence':      'defence',
    'IT':           'ai',
    'Pharma':       'pharma',
    'Renewable':    'renew',
    'Electronics':  'semi',
    'EV':           'ev',
    'Infra':        'infra',
}

# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def sma(series, period):
    return series.rolling(window=period).mean()

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period-1, min_periods=period).mean()

def adx(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Zero out where the other is larger
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0
    atr14 = tr.ewm(com=period-1, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(com=period-1, min_periods=period).mean() / atr14.replace(0, 1e-10)
    minus_di = 100 * minus_dm.ewm(com=period-1, min_periods=period).mean() / atr14.replace(0, 1e-10)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10))
    return dx.ewm(com=period-1, min_periods=period).mean()

def supertrend(high, low, close, period=10, multiplier=3.0):
    atr14 = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr14
    lower_band = hl2 - multiplier * atr14
    supertrend_val = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)
    for i in range(1, len(close)):
        if close.iloc[i] > upper_band.iloc[i-1]:
            direction.iloc[i] = 1   # Bullish
        elif close.iloc[i] < lower_band.iloc[i-1]:
            direction.iloc[i] = -1  # Bearish
        else:
            direction.iloc[i] = direction.iloc[i-1]
    return direction

# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE — Technical
# ═══════════════════════════════════════════════════════════════════════════════

def score_technical(df):
    """
    Full technical scoring based on our framework.
    Returns score (0-100) and breakdown dict.
    """
    if df is None or len(df) < 220:
        return 0, {}

    close = df['Close']
    high  = df['High']
    low   = df['Low']
    vol   = df['Volume']

    # ── Moving averages ──────────────────────────────────────────────────────
    sma50  = sma(close, 50)
    sma150 = sma(close, 150)
    sma200 = sma(close, 200)
    ema20  = ema(close, 20)

    price    = close.iloc[-1]
    s50      = sma50.iloc[-1]
    s150     = sma150.iloc[-1]
    s200     = sma200.iloc[-1]
    s200_4w  = sma200.iloc[-21]  # 4 weeks ago

    # 52-week high/low
    w52_high = high.rolling(252).max().iloc[-1]
    w52_low  = low.rolling(252).min().iloc[-1]

    # ── MINERVINI TREND TEMPLATE (40 pts) ────────────────────────────────────
    template = {
        'price_above_50':    price > s50,
        'price_above_150':   price > s150,
        'price_above_200':   price > s200,
        'sma50_above_150':   s50 > s150,
        'sma150_above_200':  s150 > s200,
        'sma200_trending_up': s200 > s200_4w,
        'within_25_of_52wh': price >= w52_high * 0.75,
        'above_30_from_52wl': price >= w52_low * 1.30,
    }
    template_passes  = sum(template.values())
    template_score   = template_passes * 5  # max 40 pts

    # Stage 2 gate — must pass at least 6/8
    if template_passes < 6:
        return 0, {'stage': 'Stage 1/3/4', 'template_passes': template_passes}

    # ── RSI (15 pts) ─────────────────────────────────────────────────────────
    rsi_val = rsi(close, 14).iloc[-1]
    if 50 <= rsi_val <= 65:    rsi_score = 15
    elif 45 <= rsi_val < 50:   rsi_score = 12
    elif 65 < rsi_val <= 72:   rsi_score = 10
    elif 40 <= rsi_val < 45:   rsi_score = 8
    elif rsi_val > 72:         rsi_score = 4
    else:                      rsi_score = 2

    # ── MACD (15 pts) ────────────────────────────────────────────────────────
    macd_line, signal_line, histogram = macd(close)
    macd_val  = macd_line.iloc[-1]
    sig_val   = signal_line.iloc[-1]
    hist_curr = histogram.iloc[-1]
    hist_prev = histogram.iloc[-2]

    # Recent crossover = last 5 days
    recent_cross = any(
        histogram.iloc[-i] > 0 and histogram.iloc[-(i+1)] <= 0
        for i in range(1, 6) if len(histogram) > i+1
    )
    if recent_cross:                              macd_score = 15
    elif macd_val > sig_val and hist_curr > hist_prev:  macd_score = 12
    elif macd_val > sig_val:                      macd_score = 8
    elif hist_curr > hist_prev:                   macd_score = 5  # turning up
    else:                                         macd_score = 0

    # ── ADX (10 pts) ─────────────────────────────────────────────────────────
    adx_val = adx(high, low, close, 14).iloc[-1]
    if adx_val > 35:    adx_score = 10
    elif adx_val > 25:  adx_score = 8
    elif adx_val > 20:  adx_score = 5
    else:               adx_score = 2

    # ── Supertrend (10 pts) ──────────────────────────────────────────────────
    st = supertrend(high, low, close)
    st_score = 10 if st.iloc[-1] == 1 else 0
    st_signal = 'Bullish' if st.iloc[-1] == 1 else 'Bearish'

    # ── Volume (15 pts) ──────────────────────────────────────────────────────
    avg_vol_20 = vol.rolling(20).mean().iloc[-1]
    today_vol  = vol.iloc[-1]
    vol_ratio  = today_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
    # VCP: volume drying up (good for base building)
    last5_vol  = vol.iloc[-5:].mean()
    vol_dryup  = last5_vol < avg_vol_20 * 0.8

    if vol_ratio > 2.0:       vol_score = 15
    elif vol_ratio > 1.5:     vol_score = 12
    elif vol_ratio > 1.0:     vol_score = 8
    elif vol_dryup:           vol_score = 10  # VCP contraction
    else:                     vol_score = 4

    # ── EMA Structure (10 pts) ───────────────────────────────────────────────
    e20 = ema20.iloc[-1]
    if price > e20 > s50 > s200:   ema_score = 10
    elif price > s50 > s200:       ema_score = 7
    elif price > s200:             ema_score = 4
    else:                          ema_score = 0

    # ── Pattern Bonus (up to 25 pts) ─────────────────────────────────────────
    pattern_score = 0
    pattern_name  = 'None'

    # VCP detection: price range contracting over last 6 weeks
    if len(close) >= 30:
        ranges = []
        for w in range(3):
            start = -(w+1)*10
            end   = -w*10 if w > 0 else len(close)
            seg   = close.iloc[start:end] if end != len(close) else close.iloc[start:]
            if len(seg) > 0:
                ranges.append((seg.max() - seg.min()) / seg.mean())
        if len(ranges) == 3 and ranges[0] < ranges[1] < ranges[2]:
            if vol_dryup:
                pattern_score = 18
                pattern_name  = 'VCP'
            else:
                pattern_score = 10
                pattern_name  = 'Contraction'

    # Pullback to 20 EMA
    if pattern_name == 'None':
        prev5_prices = close.iloc[-6:-1]
        prev5_ema    = ema20.iloc[-6:-1]
        touched_ema  = any(abs(p - e) / e < 0.02 for p, e in zip(prev5_prices, prev5_ema))
        bouncing     = close.iloc[-1] > close.iloc[-3] and rsi_val > 45
        if touched_ema and bouncing:
            pattern_score = 8
            pattern_name  = 'EMA Pullback'

    # Near 52w high breakout
    if pattern_name == 'None' and price >= w52_high * 0.97:
        pattern_score = 10
        pattern_name  = 'Near 52w High'

    # ── Total Technical Score ─────────────────────────────────────────────────
    raw = template_score + rsi_score + macd_score + adx_score + st_score + vol_score + ema_score + pattern_score
    max_raw = 40 + 15 + 15 + 10 + 10 + 15 + 10 + 25  # 140
    tech_score = min(100, round(raw / max_raw * 100))

    # ── ATR for position sizing ───────────────────────────────────────────────
    atr_val = atr(high, low, close, 14).iloc[-1]

    return tech_score, {
        'stage':            'Stage 2' if template_passes >= 6 else f'Stage X ({template_passes}/8)',
        'template_passes':  template_passes,
        'template_details': template,
        'rsi':              round(rsi_val, 1),
        'rsi_score':        rsi_score,
        'macd_signal':      'Bullish Cross' if recent_cross else ('Above Signal' if macd_val > sig_val else 'Below Signal'),
        'macd_score':       macd_score,
        'adx':              round(adx_val, 1),
        'adx_score':        adx_score,
        'supertrend':       st_signal,
        'st_score':         st_score,
        'volume_ratio':     round(vol_ratio, 2),
        'vol_score':        vol_score,
        'ema_structure':    'Fully Stacked' if price > e20 > s50 > s200 else ('Stacked' if price > s50 > s200 else 'Partial'),
        'ema_score':        ema_score,
        'pattern':          pattern_name,
        'pattern_score':    pattern_score,
        'price':            round(price, 2),
        'sma50':            round(s50, 2),
        'sma150':           round(s150, 2),
        'sma200':           round(s200, 2),
        'w52_high':         round(w52_high, 2),
        'w52_low':          round(w52_low, 2),
        'atr':              round(atr_val, 2),
        'tech_score':       tech_score,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE — Fundamental
# Uses whatever is available from yfinance info dict
# ═══════════════════════════════════════════════════════════════════════════════

def score_fundamental(info):
    """
    Fundamental scoring from yfinance .info dictionary.
    Returns score (0-100) and breakdown dict.
    """
    if not info:
        return 50, {}  # Neutral if no data

    score = 0
    details = {}

    # ── P/E Ratio (proxy for valuation) ──────────────────────────────────────
    pe = info.get('trailingPE') or info.get('forwardPE') or 0
    details['pe'] = round(pe, 1) if pe else 'N/A'

    # ── ROE (Return on Equity) ────────────────────────────────────────────────
    roe = (info.get('returnOnEquity') or 0) * 100
    details['roe'] = round(roe, 1)
    if roe > 25:    score += 15
    elif roe > 20:  score += 12
    elif roe > 15:  score += 8
    elif roe > 10:  score += 4
    else:           score += 0

    # ── Revenue Growth ────────────────────────────────────────────────────────
    rev_growth = (info.get('revenueGrowth') or 0) * 100
    details['rev_growth'] = round(rev_growth, 1)
    if rev_growth > 25:    score += 15
    elif rev_growth > 20:  score += 12
    elif rev_growth > 15:  score += 8
    elif rev_growth > 10:  score += 5
    elif rev_growth > 0:   score += 2
    else:                  score += 0

    # ── Earnings Growth ───────────────────────────────────────────────────────
    earn_growth = (info.get('earningsGrowth') or info.get('earningsQuarterlyGrowth') or 0) * 100
    details['earn_growth'] = round(earn_growth, 1)
    if earn_growth > 30:   score += 15
    elif earn_growth > 20: score += 12
    elif earn_growth > 15: score += 8
    elif earn_growth > 5:  score += 4
    else:                  score += 0

    # ── Debt / Equity ─────────────────────────────────────────────────────────
    de = info.get('debtToEquity') or 0
    de = de / 100 if de > 10 else de  # yfinance sometimes returns as percentage
    details['debt_equity'] = round(de, 2)
    if de < 0.25:    score += 15
    elif de < 0.5:   score += 12
    elif de < 1.0:   score += 8
    elif de < 2.0:   score += 4
    else:            score += 0

    # ── Profit Margins ────────────────────────────────────────────────────────
    margin = (info.get('profitMargins') or 0) * 100
    details['pat_margin'] = round(margin, 1)
    if margin > 20:    score += 10
    elif margin > 12:  score += 8
    elif margin > 7:   score += 5
    elif margin > 0:   score += 2
    else:              score += 0

    # ── Promoter / Insider Holding (% shares held by insiders) ───────────────
    held = (info.get('heldPercentInsiders') or 0) * 100
    details['promoter_holding'] = round(held, 1)
    if held > 60:    score += 15
    elif held > 50:  score += 12
    elif held > 40:  score += 8
    elif held > 30:  score += 4
    else:            score += 2

    # ── Institutional holding (FII+DII proxy) ────────────────────────────────
    inst = (info.get('heldPercentInstitutions') or 0) * 100
    details['inst_holding'] = round(inst, 1)
    if inst > 40:    score += 15
    elif inst > 25:  score += 12
    elif inst > 15:  score += 8
    else:            score += 4

    # ── Market Cap tier bonus ─────────────────────────────────────────────────
    mcap = info.get('marketCap') or 0
    mcap_cr = mcap / 1e7  # Convert to Crores
    details['market_cap_cr'] = round(mcap_cr, 0)
    if mcap_cr > 100000:     details['cap_tier'] = 'Large Cap'
    elif mcap_cr > 20000:    details['cap_tier'] = 'Midcap'
    elif mcap_cr > 5000:     details['cap_tier'] = 'Smallcap'
    else:                    details['cap_tier'] = 'Micro'

    # Normalize to 100
    max_possible = 15 + 15 + 15 + 15 + 10 + 15 + 15  # 100
    fund_score = min(100, round(score / max_possible * 100))
    details['fund_score'] = fund_score

    return fund_score, details


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE — Momentum
# ═══════════════════════════════════════════════════════════════════════════════

def score_momentum(df, nifty_df):
    """
    Momentum scoring: RS vs Nifty, 1-month momentum, 52w high proximity.
    Returns score (0-100) and breakdown dict.
    """
    if df is None or len(df) < 63:
        return 50, {}

    close       = df['Close']
    price       = close.iloc[-1]
    price_1m    = close.iloc[-21] if len(close) >= 21 else close.iloc[0]
    price_3m    = close.iloc[-63] if len(close) >= 63 else close.iloc[0]
    high        = df['High']
    w52_high    = high.rolling(252).max().iloc[-1]

    mom_1m = (price - price_1m) / price_1m * 100
    mom_3m = (price - price_3m) / price_3m * 100

    score = 0
    details = {}

    # ── RS vs Nifty 3 months (30 pts) ────────────────────────────────────────
    if nifty_df is not None and len(nifty_df) >= 63:
        n_close  = nifty_df['Close']
        n_price  = n_close.iloc[-1]
        n_3m     = n_close.iloc[-63]
        nifty_3m = (n_price - n_3m) / n_3m * 100
        rs_vs_nifty = mom_3m - nifty_3m
        details['rs_vs_nifty'] = round(rs_vs_nifty, 1)
        details['nifty_3m']    = round(nifty_3m, 1)
        if rs_vs_nifty > 10:    score += 30
        elif rs_vs_nifty > 5:   score += 22
        elif rs_vs_nifty > 0:   score += 14
        elif rs_vs_nifty > -5:  score += 7
        else:                   score += 2
    else:
        details['rs_vs_nifty'] = 'N/A'
        score += 14  # Neutral if no Nifty data

    # ── 1-month price momentum (20 pts) ──────────────────────────────────────
    details['mom_1m'] = round(mom_1m, 1)
    if mom_1m > 10:    score += 20
    elif mom_1m > 6:   score += 16
    elif mom_1m > 3:   score += 10
    elif mom_1m > 0:   score += 6
    else:              score += 1

    # ── 3-month momentum (20 pts) ────────────────────────────────────────────
    details['mom_3m'] = round(mom_3m, 1)
    if mom_3m > 20:    score += 20
    elif mom_3m > 12:  score += 15
    elif mom_3m > 6:   score += 10
    elif mom_3m > 0:   score += 5
    else:              score += 0

    # ── 52-week high proximity (30 pts) ──────────────────────────────────────
    pct_from_52wh = (price - w52_high) / w52_high * 100  # negative = below
    details['pct_from_52wh'] = round(pct_from_52wh, 1)
    if pct_from_52wh >= -3:    score += 30   # Within 3% = leadership
    elif pct_from_52wh >= -10: score += 22
    elif pct_from_52wh >= -20: score += 14
    elif pct_from_52wh >= -30: score += 7
    else:                      score += 1

    mom_score = min(100, round(score))
    details['mom_score'] = mom_score
    return mom_score, details


# ═══════════════════════════════════════════════════════════════════════════════
# MACRO SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_macro_score(macro):
    score = 0

    # RBI stance (20 pts)
    stance = macro.get('rbi_stance', 'neutral')
    if stance == 'easing':       score += 20
    elif stance == 'neutral':    score += 10
    else:                        score += 4  # tightening

    # VIX (20 pts)
    vix = macro.get('india_vix', 20)
    if vix < 12:      score += 20
    elif vix < 16:    score += 16
    elif vix < 20:    score += 10
    elif vix < 25:    score += 4
    else:             score += 0

    # FII flows 10-day (20 pts)
    fii = macro.get('fii_10day_cr', 0)
    if fii > 5000:       score += 20
    elif fii > 0:        score += 15
    elif fii > -5000:    score += 10
    elif fii > -15000:   score += 5
    else:                score += 0

    # CPI (20 pts)
    cpi = macro.get('cpi', 5)
    if cpi < 3:      score += 20
    elif cpi < 5:    score += 15
    elif cpi < 7:    score += 8
    else:            score += 2

    # GDP (20 pts)
    gdp = macro.get('gdp_growth', 6)
    if gdp > 7.5:    score += 20
    elif gdp > 6.5:  score += 15
    elif gdp > 5.5:  score += 8
    else:            score += 3

    macro_score = min(100, score)

    if macro_score >= 75:     regime = 'BULL MODE'
    elif macro_score >= 50:   regime = 'SELECTIVE'
    elif macro_score >= 30:   regime = 'CAUTION'
    else:                     regime = 'WAIT'

    # Trading signal
    vix_val = macro.get('india_vix', 20)
    nifty_vs_200 = macro.get('nifty_vs_200sma', 0)
    if vix_val > 25 or nifty_vs_200 < -5:
        signal = 'RED'
        signal_text = 'WAIT — Do not open new positions. Protect capital.'
        risk_advice = 'No new trades'
    elif vix_val > 18 or macro_score < 50:
        signal = 'YELLOW'
        signal_text = f'SELECTIVE — Trade setups scoring ≥ 80 only. Use 1.5% risk.'
        risk_advice = '1.5% per trade'
    else:
        signal = 'GREEN'
        signal_text = 'ACTIVE — Full 2% risk per trade. Deploy capital.'
        risk_advice = '2% per trade'

    return macro_score, regime, signal, signal_text, risk_advice


# ═══════════════════════════════════════════════════════════════════════════════
# POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_position(price, atr_val, capital, risk_pct, max_pos_pct):
    """
    Van Tharp fixed fractional position sizing.
    Stop = entry - (2 × ATR)
    """
    sl_distance   = CONFIG['atr_multiplier'] * atr_val
    sl_price      = round(price - sl_distance, 2)
    risk_amount   = capital * risk_pct
    shares_by_risk = int(risk_amount / sl_distance) if sl_distance > 0 else 0
    max_shares    = int((capital * max_pos_pct) / price) if price > 0 else 0
    shares        = min(shares_by_risk, max_shares)
    position_val  = shares * price
    actual_risk   = shares * sl_distance

    # Targets using R multiples
    t1 = round(price + 2.0 * sl_distance, 2)
    t2 = round(price + 3.5 * sl_distance, 2)
    rr = round((t1 - price) / sl_distance, 1) if sl_distance > 0 else 0

    return {
        'entry':          round(price, 2),
        'stop_loss':      sl_price,
        'target_1':       t1,
        'target_2':       t2,
        'sl_distance':    round(sl_distance, 2),
        'sl_pct':         round(-sl_distance / price * 100, 1),
        't1_pct':         round((t1 - price) / price * 100, 1),
        't2_pct':         round((t2 - price) / price * 100, 1),
        'rr':             f'1:{rr}',
        'shares':         shares,
        'position_value': round(position_val, 0),
        'risk_amount':    round(actual_risk, 0),
        'risk_pct_actual': round(actual_risk / capital * 100, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSITE SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def composite_score(tech, fund, mom, theme_bonus=0, style='both'):
    """
    Dual scoring: swing and position weights.
    """
    swing_score = round(tech * 0.50 + fund * 0.25 + mom * 0.15 + min(theme_bonus, 30) * 0.10)
    pos_score   = round(tech * 0.30 + fund * 0.45 + mom * 0.10 + min(theme_bonus, 30) * 0.15)
    both_score  = round(tech * 0.40 + fund * 0.30 + mom * 0.15 + min(theme_bonus, 30) * 0.15)

    # Signal label
    score = both_score
    if score >= 85:   signal, signal_class = 'STRONG BUY', 'BUY'
    elif score >= 72: signal, signal_class = 'BUY', 'BUY'
    elif score >= 62: signal, signal_class = 'WATCH', 'HOLD'
    elif score >= 50: signal, signal_class = 'HOLD', 'HOLD'
    else:             signal, signal_class = 'AVOID', 'AVOID'

    # Setup style
    if swing_score >= 75 and pos_score >= 75:  trade_style = 'both'
    elif swing_score >= 75:                     trade_style = 'swing'
    elif pos_score >= 75:                       trade_style = 'position'
    else:                                       trade_style = 'watch'

    return {
        'composite':    both_score,
        'swing_score':  swing_score,
        'pos_score':    pos_score,
        'signal':       signal,
        'signal_class': signal_class,
        'style':        trade_style,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_scan(test_mode=False):
    log.info("=" * 60)
    log.info("SwingEdge EOD Scanner Starting")
    log.info(f"Date: {datetime.now().strftime('%d %b %Y %H:%M IST')}")
    log.info("=" * 60)

    universe = ALL_STOCKS[:10] if test_mode else ALL_STOCKS
    log.info(f"Universe: {len(universe)} stocks {'(TEST MODE)' if test_mode else ''}")

    # ── Calculate macro score ─────────────────────────────────────────────────
    macro_score, regime, signal, signal_text, risk_advice = calculate_macro_score(MACRO_DATA)
    log.info(f"Macro Score: {macro_score} | Regime: {regime} | Signal: {signal}")

    if signal == 'RED' and not test_mode:
        log.warning("🔴 RED SIGNAL — Market in WAIT zone. Scanner will run but no trades recommended.")

    # ── Download Nifty 50 for RS calculation ─────────────────────────────────
    log.info("Downloading Nifty 50 benchmark...")
    try:
        nifty_df = yf.download('^NSEI', period=CONFIG['data_period'], interval='1d',
                               progress=False, auto_adjust=True)
        log.info(f"Nifty 50: {len(nifty_df)} days downloaded")
    except Exception as e:
        log.warning(f"Could not download Nifty: {e}")
        nifty_df = None

    # ── Scan each stock ───────────────────────────────────────────────────────
    results = []
    errors  = []

    for i, ticker in enumerate(universe):
        try:
            log.info(f"[{i+1:3d}/{len(universe)}] Scanning {ticker}...")

            # Download price data
            df = yf.download(ticker, period=CONFIG['data_period'], interval='1d',
                             progress=False, auto_adjust=True)

            if df is None or len(df) < 100:
                log.debug(f"  Skip: insufficient data ({len(df) if df is not None else 0} days)")
                continue

            # Download fundamentals
            try:
                tk   = yf.Ticker(ticker)
                info = tk.info or {}
            except Exception:
                info = {}

            # Scores
            tech_score, tech_details = score_technical(df)
            if tech_score == 0:
                log.debug(f"  Skip: failed Stage 2 gate ({tech_details.get('stage','?')})")
                continue

            fund_score, fund_details = score_fundamental(info)
            mom_score, mom_details   = score_momentum(df, nifty_df)

            # Sector + theme
            sector  = SECTOR_MAP.get(ticker, 'Other')
            theme   = THEME_MAP.get(sector, '')
            theme_bonus = 20 if theme in ['defence','ai'] else (15 if theme in ['renew','infra'] else (12 if theme in ['semi','ev','pharma'] else 0))

            # Composite score
            scores = composite_score(tech_score, fund_score, mom_score, theme_bonus)

            if scores['composite'] < CONFIG['min_score']:
                continue

            # Position sizing
            price   = tech_details['price']
            atr_val = tech_details['atr']
            pos     = calculate_position(price, atr_val, CONFIG['capital'],
                                         CONFIG['risk_pct'], CONFIG['max_pos_pct'])

            # R:R filter
            rr_val = float(pos['rr'].replace('1:', '')) if pos['rr'] != '1:0' else 0
            if rr_val < CONFIG['min_rr']:
                log.debug(f"  Skip: R:R {pos['rr']} below minimum {CONFIG['min_rr']}")
                continue

            # Format for dashboard
            name   = info.get('longName') or info.get('shortName') or ticker.replace('.NS','')
            chg    = round(df['Close'].iloc[-1] - df['Close'].iloc[-2], 2)
            pct    = round(chg / df['Close'].iloc[-2] * 100, 2)
            volume = int(df['Volume'].iloc[-1])
            vol_20 = int(df['Volume'].rolling(20).mean().iloc[-1])

            result = {
                # Identity
                'id':           ticker.replace('.NS',''),
                'ticker':       ticker,
                'name':         name[:40],
                'sector':       sector,
                'cap':          fund_details.get('cap_tier', 'Unknown'),
                'themes':       [theme] if theme else [],

                # Price
                'price':        price,
                'chg':          chg,
                'pct':          pct,
                'up':           chg >= 0,
                'volume':       volume,
                'vol_ratio':    tech_details.get('volume_ratio', 1.0),

                # Scores
                'score':        scores['composite'],
                'swing_score':  scores['swing_score'],
                'pos_score':    scores['pos_score'],
                'tech':         tech_score,
                'fund':         fund_score,
                'mom':          mom_score,
                'theme':        theme_bonus,
                'signal':       scores['signal'],
                'signal_class': scores['signal_class'],
                'style':        scores['style'],

                # Technical details
                'setup':            tech_details.get('pattern', 'None'),
                'rsi':              tech_details.get('rsi', 0),
                'macd_signal':      tech_details.get('macd_signal', ''),
                'adx':              tech_details.get('adx', 0),
                'supertrend':       tech_details.get('supertrend', ''),
                'ema_structure':    tech_details.get('ema_structure', ''),
                'template_passes':  tech_details.get('template_passes', 0),
                'sma50':            tech_details.get('sma50', 0),
                'sma150':           tech_details.get('sma150', 0),
                'sma200':           tech_details.get('sma200', 0),
                'w52_high':         tech_details.get('w52_high', 0),
                'w52_low':          tech_details.get('w52_low', 0),
                'pct_from_52wh':    mom_details.get('pct_from_52wh', 0),

                # Fundamental details
                'roe':              fund_details.get('roe', 0),
                'rev_growth':       fund_details.get('rev_growth', 0),
                'earn_growth':      fund_details.get('earn_growth', 0),
                'debt_equity':      fund_details.get('debt_equity', 0),
                'pat_margin':       fund_details.get('pat_margin', 0),
                'promoter':         fund_details.get('promoter_holding', 0),
                'inst_holding':     fund_details.get('inst_holding', 0),
                'market_cap_cr':    fund_details.get('market_cap_cr', 0),
                'pe':               fund_details.get('pe', 'N/A'),

                # Momentum
                'rs_vs_nifty':  mom_details.get('rs_vs_nifty', 0),
                'mom_1m':       mom_details.get('mom_1m', 0),
                'mom_3m':       mom_details.get('mom_3m', 0),

                # Trade levels (Van Tharp)
                'entry':        pos['entry'],
                'stop_loss':    pos['stop_loss'],
                'target_1':     pos['target_1'],
                'target_2':     pos['target_2'],
                'sl_pct':       f"{pos['sl_pct']}%",
                't1_pct':       f"+{pos['t1_pct']}%",
                't2_pct':       f"+{pos['t2_pct']}%",
                'rr':           pos['rr'],
                'shares':       pos['shares'],
                'position_value': pos['position_value'],
                'risk_amount':  pos['risk_amount'],

                # Hold period based on style
                'hold':         '5–14d' if scores['style'] == 'swing' else ('20–60d' if scores['style'] == 'position' else '8–20d'),
            }

            results.append(result)
            log.info(f"  ✅ Score:{scores['composite']} Tech:{tech_score} Fund:{fund_score} Mom:{mom_score} | {scores['signal']} | {tech_details.get('pattern','?')} | R:R {pos['rr']}")

            time.sleep(CONFIG['scan_delay'])

        except Exception as e:
            log.error(f"  ❌ Error on {ticker}: {e}")
            errors.append({'ticker': ticker, 'error': str(e)})
            continue

    # ── Sort and rank ─────────────────────────────────────────────────────────
    results.sort(key=lambda x: x['score'], reverse=True)

    # Add rank
    for i, r in enumerate(results):
        r['rank'] = i + 1

    log.info(f"\n{'='*60}")
    log.info(f"Scan complete: {len(results)} stocks qualified")
    log.info(f"Errors: {len(errors)}")
    log.info(f"Top 5: {[r['id'] for r in results[:5]]}")

    # ── Sector rankings ───────────────────────────────────────────────────────
    sector_scores = {}
    for r in results:
        s = r['sector']
        if s not in sector_scores:
            sector_scores[s] = []
        sector_scores[s].append(r['score'])

    sector_summary = {}
    for s, scores_list in sector_scores.items():
        avg = round(sum(scores_list) / len(scores_list))
        sector_summary[s] = {
            'avg_score': avg,
            'count':     len(scores_list),
            'quadrant':  'lead' if avg >= 70 else ('impr' if avg >= 55 else ('weak' if avg >= 40 else 'lag')),
        }

    # ── Build final JSON ──────────────────────────────────────────────────────
    output = {
        'meta': {
            'generated':    datetime.now().strftime('%d %b %Y %H:%M IST'),
            'date':         str(date.today()),
            'stocks_scanned': len(universe),
            'stocks_qualified': len(results),
            'errors':       len(errors),
            'version':      '3.0',
        },
        'macro': {
            **MACRO_DATA,
            'macro_score':  macro_score,
            'regime':       regime,
            'signal':       signal,
            'signal_text':  signal_text,
            'risk_advice':  risk_advice,
        },
        'config': {
            'capital':     CONFIG['capital'],
            'risk_pct':    CONFIG['risk_pct'],
        },
        'stocks':          results,
        'sector_summary':  sector_summary,
        'scan_errors':     errors[:10],  # Only include first 10 errors
    }

    return output


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT & GIT PUSH
# ═══════════════════════════════════════════════════════════════════════════════

def save_output(data, output_path):
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    log.info(f"✅ Saved: {output_path} ({os.path.getsize(output_path)/1024:.1f} KB)")

def git_push(repo_path):
    """Auto-push updated data.json to GitHub."""
    try:
        os.chdir(repo_path)
        subprocess.run(['git', 'add', 'data.json'], check=True)
        msg = f"EOD scan {datetime.now().strftime('%d %b %Y %H:%M')}"
        subprocess.run(['git', 'commit', '-m', msg], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        log.info("✅ Pushed to GitHub successfully")
        log.info(f"🌐 Dashboard live at: https://udayshankar448.github.io/swingEdge/")
    except subprocess.CalledProcessError as e:
        log.error(f"Git push failed: {e}")
    except FileNotFoundError:
        log.error("Repo path not found. Check REPO_PATH in scanner.py")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SwingEdge EOD Scanner')
    parser.add_argument('--test',  action='store_true', help='Test mode — scan 10 stocks only')
    parser.add_argument('--push',  action='store_true', help='Auto git push after scan')
    parser.add_argument('--capital', type=int, default=3000000, help='Capital in ₹ (default: 30L)')
    parser.add_argument('--risk',    type=float, default=0.02,  help='Risk per trade 0.01–0.05')
    args = parser.parse_args()

    # Apply CLI overrides
    CONFIG['capital']  = args.capital
    CONFIG['risk_pct'] = args.risk

    # ── Run scan ──────────────────────────────────────────────────────────────
    data = run_scan(test_mode=args.test)

    # ── Save output ───────────────────────────────────────────────────────────
    # Put data.json in the same folder as this script (= your swingEdge folder)
    script_dir  = Path(__file__).parent
    output_path = script_dir / CONFIG['output_file']
    save_output(data, output_path)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print(f"  SwingEdge Scan Complete — {data['meta']['date']}")
    print("="*60)
    print(f"  Stocks scanned:    {data['meta']['stocks_scanned']}")
    print(f"  Qualified picks:   {data['meta']['stocks_qualified']}")
    print(f"  Market signal:     {data['macro']['signal']} — {data['macro']['regime']}")
    print(f"  Macro score:       {data['macro']['macro_score']}/100")
    print()

    if data['stocks']:
        print("  TOP PICKS TODAY:")
        for s in data['stocks'][:5]:
            print(f"  #{s['rank']:2d} {s['id']:<14} Score:{s['score']:3d}  {s['signal']:<12} {s['setup']:<15} R:R {s['rr']}")
    else:
        print("  No stocks qualified today — WAIT signal active")

    print(f"\n  Output: {output_path}")

    # ── Git push ──────────────────────────────────────────────────────────────
    if args.push:
        REPO_PATH = str(script_dir)  # Assumes scanner.py is inside your swingEdge folder
        log.info(f"Pushing to GitHub from {REPO_PATH}...")
        git_push(REPO_PATH)

    print("="*60)
