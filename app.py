# =============================================================================
# Matchup Advantage — merged app.py
# LOGIC: all functions verbatim from the audited app.py (unchanged).
# LOOK : visual shell (theme, CSS, sidebar, header, tabs, cards) from app_ui.py.
# =============================================================================

import os
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc, RegularPolygon
from matplotlib.colors import LinearSegmentedColormap, Normalize
import matplotlib as mpl
import numpy as np
import pandas as pd
import requests
import streamlit as st
from nba_api.stats.static import teams, players as nba_players

import data_pipeline as dp


# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="Matchup Advantage",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏀",
)


# =============================================================================
# PALETTE — NBA-authentic light theme (UI.py)
# =============================================================================
NBA_BLUE    = "#17408B"
NBA_RED     = "#C9082A"
WHITE       = "#FFFFFF"
LIGHT_GREY  = "#F4F6F9"
BORDER      = "#E1E5ED"
BORDER2     = "#C8CEDB"
CHARCOAL    = "#1A1F2E"
TEXT        = "#1A1F2E"
TEXT2       = "#3D4A5C"
TEXT3       = "#7A8799"
CARD        = "#FFFFFF"
CARD2       = "#F4F6F9"
SUCCESS     = "#1A7F4B"
WARN        = "#C47A1E"
DANGER      = "#C9082A"
LIGHT_S     = "#E8F5EE"
LIGHT_D     = "#FCE8E8"
LIGHT_P     = "#E8EEF8"

# Semantic aliases used by app.py takeaway logic
GREEN = SUCCESS
GREY  = TEXT3
RED   = DANGER


# =============================================================================
# CSS — Premium NBA analytics (UI.py aesthetic, enlarged + enhanced)
# =============================================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── base reset ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container {{
    background: {LIGHT_GREY} !important;
    color: {TEXT};
    font-family: 'Inter', system-ui, sans-serif;
}}
.block-container {{
    padding-top: 0 !important;
    padding-bottom: 3rem !important;
    max-width: 1600px;
}}

/* ── entrance animations ── */
@keyframes fadeSlideIn {{
    from {{ opacity: 0; transform: translateY(16px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to   {{ opacity: 1; }}
}}
@keyframes slideRight {{
    from {{ opacity: 0; transform: translateX(-14px); }}
    to   {{ opacity: 1; transform: translateX(0); }}
}}
@keyframes countUp {{
    from {{ opacity: 0; transform: scale(0.88); }}
    to   {{ opacity: 1; transform: scale(1); }}
}}

[data-testid="stTabPanel"] > div:first-child {{
    animation: fadeSlideIn 0.38s cubic-bezier(0.22,1,0.36,1) both;
}}

/* ── sidebar (wider) ── */
[data-testid="stSidebar"] {{
    background: {CHARCOAL} !important;
    border-right: none !important;
    min-width: 295px !important;
    max-width: 295px !important;
}}
[data-testid="stSidebar"] * {{ color: rgba(255,255,255,0.88) !important; }}
[data-testid="stSidebar"] .stSelectbox label {{
    color: rgba(255,255,255,0.45) !important;
    font-size: .72rem !important;
    font-weight: 800 !important;
    text-transform: uppercase;
    letter-spacing: .12em;
}}
div[data-baseweb="select"] > div {{
    background: rgba(255,255,255,0.07) !important;
    border-color: rgba(255,255,255,0.14) !important;
    color: #fff !important;
    border-radius: 8px !important;
    font-size: .95rem !important;
    transition: border-color .18s, background .18s;
}}
div[data-baseweb="select"] > div:hover {{
    background: rgba(255,255,255,0.11) !important;
    border-color: rgba(255,255,255,0.28) !important;
}}
div[data-baseweb="select"] svg {{ fill: rgba(255,255,255,0.45) !important; }}
div[data-baseweb="popover"] {{ background: {CARD} !important; border-radius: 9px !important; }}
/* dropdown option list — guarantee legible dark text on a light menu */
div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"] {{
    background: {CARD} !important;
}}
div[data-baseweb="popover"] li, div[data-baseweb="menu"] li,
ul[role="listbox"] li, [role="option"] {{
    color: {TEXT} !important; font-size: .92rem !important;
    background: {CARD} !important;
}}
[role="option"]:hover, ul[role="listbox"] li:hover {{ background: {LIGHT_P} !important; }}
[role="option"][aria-selected="true"] {{ background: {LIGHT_P} !important; color: {NBA_BLUE} !important; }}

/* ── global typography ── */
h1, h2, h3, h4 {{
    color: {TEXT} !important;
    font-weight: 900 !important;
    letter-spacing: -.03em;
    font-family: 'Inter', system-ui, sans-serif;
}}
p, li {{ font-size: 1.0rem; line-height: 1.7; }}

/* ── top header ── */
.ma-header {{
    background: linear-gradient(135deg, {CHARCOAL} 0%, #0D1627 100%);
    border-bottom: 3px solid {NBA_RED};
    padding: 1.8rem 2.5rem 1.7rem;
    margin-bottom: 0;
    display: flex;
    align-items: center;
    gap: 1.75rem;
    animation: fadeIn 0.4s ease both;
    position: relative;
    overflow: hidden;
}}
.ma-header::after {{
    content: '';
    position: absolute;
    top: -60%; right: -5%;
    width: 300px; height: 300px;
    border: 60px solid rgba(201,8,42,0.07);
    border-radius: 50%;
    pointer-events: none;
}}
.ma-app-title {{
    font-size: 2.4rem;
    font-weight: 900;
    color: {WHITE};
    letter-spacing: -.05em;
    line-height: 1;
    text-transform: uppercase;
}}
.ma-app-title span {{ color: {NBA_RED}; }}
.ma-app-tagline {{
    font-size: .78rem;
    color: rgba(255,255,255,0.42);
    font-weight: 600;
    letter-spacing: .14em;
    text-transform: uppercase;
    margin-top: .45rem;
}}
.ma-matchup-val {{
    font-size: 1.25rem;
    color: rgba(255,255,255,0.92);
    font-weight: 800;
    letter-spacing: -.02em;
    margin-top: .25rem;
}}
.ma-matchup-label {{
    font-size: .65rem;
    color: rgba(255,255,255,0.38);
    font-weight: 700;
    letter-spacing: .14em;
    text-transform: uppercase;
}}
.ma-season-badge {{
    background: {NBA_BLUE};
    border-radius: 9px;
    padding: .55rem 1.3rem;
    font-size: .85rem;
    color: {WHITE};
    font-weight: 800;
    letter-spacing: .06em;
    text-transform: uppercase;
    flex-shrink: 0;
}}
.ma-header-matchup {{
    text-align: right;
    border-right: 1px solid rgba(255,255,255,0.1);
    padding-right: 1.75rem;
    margin-right: .5rem;
    flex: 1;
}}

/* ── tabs ── */
[data-testid="stTabs"] [role="tab"] {{
    color: {TEXT3} !important;
    font-weight: 700 !important;
    padding: 1.25rem 2.5rem !important;
    border-bottom: 3px solid transparent !important;
    transition: color .18s, border-color .18s, background .18s;
    text-transform: uppercase;
    font-size: .88rem !important;
    letter-spacing: .09em !important;
}}
[data-testid="stTabs"] [role="tab"]:hover {{
    color: {NBA_BLUE} !important;
    background: {LIGHT_P} !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: {NBA_BLUE} !important;
    border-bottom-color: {NBA_RED} !important;
    font-weight: 900 !important;
}}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    border-bottom: 1px solid {BORDER} !important;
    background: {CARD} !important;
    gap: 0 !important;
    padding: 0 1.75rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
}}
[data-testid="stTabPanel"] {{
    padding-top: 2.5rem !important;
}}

/* ── section headers ── */
.sec-header {{
    font-size: .76rem;
    font-weight: 900;
    letter-spacing: .15em;
    text-transform: uppercase;
    color: {TEXT3};
    padding-bottom: .85rem;
    border-bottom: 2px solid {BORDER};
    margin-bottom: 1.75rem;
    margin-top: 2.75rem;
    display: flex;
    align-items: center;
    gap: .8rem;
    animation: slideRight 0.3s ease both;
}}
.sec-accent {{
    width: 4px;
    height: 18px;
    background: {NBA_RED};
    border-radius: 2px;
    flex-shrink: 0;
}}

/* ── KPI cards ── */
.stat-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 1.75rem 1.8rem 1.5rem;
    height: 100%;
    position: relative;
    overflow: hidden;
    transition: transform .2s, box-shadow .22s;
    animation: countUp 0.42s cubic-bezier(0.22,1,0.36,1) both;
}}
.stat-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(23,64,139,0.12);
}}
.stat-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 5px;
    border-radius: 14px 14px 0 0;
}}
.stat-card-primary::before  {{ background: {NBA_BLUE}; }}
.stat-card-danger::before   {{ background: {NBA_RED}; }}
.stat-card-success::before  {{ background: {SUCCESS}; }}
.stat-card-accent::before   {{ background: linear-gradient(90deg, {NBA_BLUE}, {NBA_RED}); }}
.stat-label {{
    font-size: .7rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .14em;
    color: {TEXT3};
    margin-bottom: .75rem;
}}
.stat-value {{
    font-size: 2.2rem;
    font-weight: 900;
    color: {TEXT};
    letter-spacing: -.04em;
    line-height: 1;
}}
.stat-sub {{
    font-size: .8rem;
    color: {TEXT3};
    margin-top: .5rem;
    line-height: 1.5;
    font-weight: 500;
}}

/* ── recommendation cards ── */
.rec-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 15px;
    padding: 1.9rem 2.1rem;
    margin-bottom: 1.2rem;
    position: relative;
    overflow: hidden;
    animation: fadeSlideIn 0.42s cubic-bezier(0.22,1,0.36,1) both;
    transition: box-shadow .22s;
}}
.rec-card:hover {{ box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
.rec-card-attack {{
    border-left: 5px solid {SUCCESS};
    background: linear-gradient(135deg, {LIGHT_S} 0%, {CARD} 55%);
}}
.rec-card-defend {{
    border-left: 5px solid {NBA_BLUE};
    background: linear-gradient(135deg, {LIGHT_P} 0%, {CARD} 55%);
}}
.rec-card-warn {{ border-left: 5px solid {WARN}; }}
.rec-eyebrow {{
    font-size: .7rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .15em;
    margin-bottom: .8rem;
    display: flex;
    align-items: center;
    gap: .55rem;
}}
.rec-eyebrow-attack {{ color: {SUCCESS}; }}
.rec-eyebrow-defend {{ color: {NBA_BLUE}; }}
.rec-eyebrow-warn   {{ color: {WARN}; }}
.rec-dot {{
    width: 9px; height: 9px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}}
.rec-dot-attack {{ background: {SUCCESS}; }}
.rec-dot-defend {{ background: {NBA_BLUE}; }}
.rec-dot-warn   {{ background: {WARN}; }}
.rec-name {{
    font-size: 2.2rem;
    font-weight: 900;
    color: {TEXT};
    letter-spacing: -.04em;
    margin-bottom: .5rem;
    line-height: 1.1;
}}
.rec-stat {{ font-size: 1.0rem; color: {TEXT2}; line-height: 1.75; }}
.rec-meta {{
    font-size: .76rem;
    color: {TEXT3};
    margin-top: .8rem;
    display: flex;
    align-items: center;
    gap: .7rem;
    flex-wrap: wrap;
    font-weight: 500;
}}

/* ── force directive ── */
.force-card {{
    background: linear-gradient(135deg, {LIGHT_P} 0%, {CARD} 60%);
    border: 1px solid {NBA_BLUE}33;
    border-left: 5px solid {NBA_BLUE};
    border-radius: 15px;
    padding: 1.5rem 1.9rem;
    margin: 1.2rem 0;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    animation: fadeSlideIn 0.45s ease both;
}}
.force-icon {{
    font-size: 1.9rem;
    line-height: 1;
    flex-shrink: 0;
    width: 58px; height: 58px;
    background: {NBA_BLUE};
    border-radius: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
}}
.force-title {{ font-size: 1.2rem; font-weight: 900; color: {TEXT}; margin-bottom: .28rem; letter-spacing: -.02em; }}
.force-sub   {{ font-size: .92rem; color: {TEXT2}; line-height: 1.65; }}

/* ── player identity strip ── */
.player-strip {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 13px;
    padding: 1.3rem 1.75rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
    animation: fadeIn 0.3s ease both;
}}
.player-strip-img {{
    width: 82px; height: 62px;
    object-fit: cover; object-position: top center;
    border-radius: 10px;
    border: 2px solid {BORDER};
    flex-shrink: 0;
    background: {CARD2};
}}
.player-strip-role {{
    font-size: .68rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .15em;
    color: {NBA_RED};
    margin-bottom: .32rem;
}}
.player-strip-name {{
    font-size: 1.55rem;
    font-weight: 900;
    color: {TEXT};
    letter-spacing: -.03em;
    line-height: 1.15;
}}
.player-strip-team {{ font-size: .85rem; color: {TEXT3}; margin-top: .2rem; font-weight: 500; }}

/* ── data tables ── */
.ma-table-wrap {{
    border: 1px solid {BORDER};
    border-radius: 13px;
    overflow: hidden;
    overflow-x: auto;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    animation: fadeSlideIn 0.4s ease both;
}}
.ma-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: .92rem;
    min-width: 480px;
}}
.ma-table thead {{ position: sticky; top: 0; z-index: 2; }}
.ma-table th {{
    background: {CHARCOAL};
    color: rgba(255,255,255,0.72);
    font-size: .67rem;
    font-weight: 800;
    letter-spacing: .13em;
    text-transform: uppercase;
    padding: .95rem 1.2rem;
    border-bottom: 2px solid rgba(255,255,255,0.08);
    text-align: left;
    white-space: nowrap;
}}
.ma-table th.rh {{ text-align: right; }}
.ma-table td {{
    padding: .82rem 1.2rem;
    border-bottom: 1px solid {BORDER};
    vertical-align: middle;
    color: {TEXT};
    font-size: .92rem;
    white-space: nowrap;
    transition: background .12s;
}}
.ma-table tr:nth-child(even) td {{ background: #FAFBFD; }}
.ma-table tr:last-child td {{ border-bottom: none; }}
.ma-table tr:hover td {{ background: {LIGHT_P} !important; }}
.ma-table .num {{
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: {TEXT2};
}}
.ma-table .pname {{ font-weight: 700; color: {TEXT}; font-size: .96rem; }}
.ma-table .ttag  {{ font-size: .82rem; color: {TEXT3}; font-weight: 600; letter-spacing: .04em; }}
.ma-table .rank-num {{ color: {TEXT3}; font-weight: 600; font-size: .86rem; text-align: right; }}

/* ── pts/poss coloring ── */
.ppp-good {{ color: {SUCCESS}; font-weight: 800; font-size: .96rem; }}
.ppp-ok   {{ color: {WARN};    font-weight: 800; font-size: .96rem; }}
.ppp-bad  {{ color: {NBA_RED}; font-weight: 800; font-size: .96rem; }}

/* ── verdict labels ── */
.lab-fav   {{ color: {SUCCESS}; font-weight: 700; }}
.lab-neu   {{ color: {TEXT3};   font-weight: 700; }}
.lab-tough {{ color: {NBA_RED}; font-weight: 700; }}

/* ── pill badges ── */
.pill {{
    display: inline-block; padding: 2px 10px;
    border-radius: 999px; font-size: .68rem;
    font-weight: 800; letter-spacing: .06em;
}}
.pill-actual    {{ background: rgba(23,64,139,0.12); color: {NBA_BLUE}; }}
.pill-projected {{ background: transparent; color: {TEXT3}; border: 1px solid {BORDER2}; }}

/* ── viz cards ── */
.viz-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 13px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    animation: fadeIn 0.45s ease both;
    transition: box-shadow .2s;
}}
.viz-card:hover {{ box-shadow: 0 8px 24px rgba(23,64,139,0.11); }}

/* ── insight panel ── */
.insight-panel {{
    background: linear-gradient(135deg, {LIGHT_P} 0%, #EEF3FB 100%);
    border: 1px solid {NBA_BLUE}22;
    border-left: 4px solid {NBA_BLUE};
    border-radius: 0 0 11px 11px;
    padding: .95rem 1.3rem;
    font-size: .86rem;
    color: {TEXT2};
    line-height: 1.7;
}}
.insight-label {{
    font-size: .64rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .14em;
    color: {NBA_BLUE};
    margin-bottom: .3rem;
}}

/* ── plan / takeaway cards ── */
.plan-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-left: 5px solid {NBA_BLUE};
    border-radius: 13px;
    padding: 1.3rem 1.75rem;
    margin: .8rem 0 .6rem 0;
    animation: fadeSlideIn 0.4s ease both;
}}
.plan-card.attack {{ border-left-color: {SUCCESS}; background: linear-gradient(135deg, {LIGHT_S} 0%, {CARD} 70%); }}
.plan-tag {{
    font-size: .68rem; font-weight: 900;
    letter-spacing: .12em; text-transform: uppercase;
    color: {TEXT3}; margin-bottom: .45rem;
}}
.plan-text {{ font-size: 1.05rem; color: {TEXT}; line-height: 1.45; font-weight: 600; }}
.plan-sub  {{ font-size: .9rem; color: {TEXT2}; margin-top: .5rem; line-height: 1.55; }}

/* ── game plan summary bullets ── */
.gp-summary {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 1.6rem 2rem;
    margin-bottom: 1.75rem;
    animation: fadeSlideIn 0.4s ease both;
}}
.gp-summary-tag {{
    font-size: .7rem; font-weight: 900;
    letter-spacing: .15em; text-transform: uppercase;
    color: {NBA_BLUE}; margin-bottom: 1rem;
}}
.gp-summary ul {{ margin: 0; padding-left: 1.4rem; }}
.gp-summary li {{ font-size: 1.0rem; color: {TEXT2}; margin-bottom: .55rem; line-height: 1.65; }}

/* ── adv chip (player card) ── */
.adv-row {{ display: flex; gap: .65rem; flex-wrap: wrap; margin-top: .7rem; }}
.adv-chip {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: .45rem .85rem;
    text-align: center;
    background: {CARD2};
    min-width: 68px;
}}
.adv-k {{ font-size: .62rem; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: {TEXT3}; margin-bottom: .2rem; }}
.adv-v {{ font-size: 1.05rem; font-weight: 800; line-height: 1; }}
.adv-r {{ font-size: .64rem; color: {TEXT3}; margin-top: .2rem; }}

/* ── four factors ── */
.ff-row {{
    display: flex; align-items: center;
    gap: 1rem; padding: .75rem 0;
    border-bottom: 1px solid {BORDER};
    font-size: .92rem;
}}
.ff-row:last-of-type {{ border-bottom: none; }}
.ff-label {{ width: 145px; font-weight: 700; color: {TEXT}; flex-shrink: 0; font-size: .88rem; }}
.ff-side {{ display: flex; align-items: center; gap: .6rem; flex: 1; min-width: 0; }}
.ff-name {{ font-size: .78rem; font-weight: 800; color: {TEXT3}; width: 40px; flex-shrink: 0; }}
.ff-track {{ flex: 1; height: 10px; background: {BORDER}; border-radius: 99px; overflow: hidden; min-width: 50px; }}
.ff-fill  {{ height: 100%; border-radius: 99px; transition: width .5s ease; }}
.ff-fill.ff-win  {{ background: {SUCCESS}; }}
.ff-fill.ff-lose {{ background: {BORDER2}; }}
.ff-val {{ font-size: .88rem; font-weight: 700; width: 58px; text-align: right; flex-shrink: 0; color: {TEXT}; }}
.ff-val.win {{ color: {SUCCESS}; }}
.ff-rank {{ font-size: .72rem; font-weight: 600; width: 60px; text-align: right; flex-shrink: 0; }}
.ff-note {{ font-size: .76rem; color: {TEXT3}; margin-top: .75rem; font-style: italic; }}

/* ── team strip (header card) ── */
.team-strip {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 1.1rem 1.75rem;
    display: flex;
    align-items: center;
    gap: 1.4rem;
    margin-bottom: 1.75rem;
    animation: fadeIn 0.35s ease both;
    flex-wrap: wrap;
}}
.team-badge {{
    display: flex; align-items: center;
    gap: .75rem; padding-left: 1rem;
}}
.team-logo {{ width: 36px; height: 36px; object-fit: contain; }}
.team-name {{ font-size: 1.05rem; font-weight: 800; color: {TEXT}; }}
.vs {{ font-size: .78rem; font-weight: 900; color: {TEXT3}; letter-spacing: .08em; text-transform: uppercase; }}
.season {{ font-size: .8rem; color: {TEXT3}; font-weight: 600; }}

/* ── clutch bars ── */
.cl-chart {{ display: flex; flex-direction: column; gap: .55rem; margin: .75rem 0; }}
.cl-row {{ display: flex; align-items: center; gap: .75rem; }}
.cl-name {{ font-size: .88rem; font-weight: 700; color: {TEXT}; width: 140px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cl-track {{ flex: 1; height: 12px; background: {BORDER}; border-radius: 99px; overflow: hidden; }}
.cl-fill  {{ height: 100%; border-radius: 99px; transition: width .5s ease; }}
.cl-val   {{ font-size: .88rem; font-weight: 700; color: {TEXT2}; width: 38px; text-align: right; flex-shrink: 0; }}

/* ── context note ── */
.context-note {{
    font-size: .82rem;
    color: {TEXT3};
    line-height: 1.7;
    margin-bottom: 1rem;
    padding: .7rem 1rem;
    background: {CARD2};
    border-radius: 8px;
    border-left: 3px solid {BORDER2};
    font-weight: 500;
}}

/* ── legend ── */
.legend {{ font-size: .82rem; color: {TEXT3}; margin: .3rem 0 .8rem 0; }}

/* ── empty state ── */
.empty-state {{
    padding: 5rem 2rem;
    text-align: center;
    color: {TEXT3};
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 15px;
    margin-top: 1rem;
    animation: fadeIn 0.4s ease both;
}}
.empty-state-icon {{ font-size: 3.2rem; margin-bottom: 1.3rem; display: block; opacity: .35; }}
.empty-state-title {{ font-size: 1.3rem; font-weight: 800; color: {TEXT2}; margin-bottom: .55rem; }}

/* ── sidebar internals ── */
.sb-logo-row {{
    display: flex; align-items: center;
    gap: 1rem; padding: 1.6rem 0 1rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 1.1rem;
}}
.sb-app-name {{
    font-size: 1.1rem; font-weight: 900;
    color: {WHITE}; line-height: 1.2;
    letter-spacing: -.02em; text-transform: uppercase;
}}
.sb-app-name span {{ color: {NBA_RED}; }}
.sb-app-sub {{
    font-size: .62rem; font-weight: 700;
    color: rgba(255,255,255,0.35);
    letter-spacing: .15em; text-transform: uppercase; margin-top: .2rem;
}}
.sb-section {{
    font-size: .62rem; font-weight: 900;
    text-transform: uppercase; letter-spacing: .15em;
    color: rgba(255,255,255,0.32);
    margin-top: 1.6rem; margin-bottom: .55rem;
}}
.sb-footer {{
    font-size: .72rem; color: rgba(255,255,255,0.3);
    line-height: 2; border-top: 1px solid rgba(255,255,255,0.07);
    padding-top: .95rem; margin-top: 2rem;
}}

/* ── glossary ── */
.gloss-row {{
    display: flex; gap: 1.5rem; padding: .85rem 0;
    border-bottom: 1px solid {BORDER}; font-size: .88rem;
}}
.gloss-row:last-child {{ border-bottom: none; }}
.gloss-key {{ font-weight: 800; color: {TEXT}; flex: 0 0 190px; line-height: 1.5; }}
.gloss-val {{ color: {TEXT2}; line-height: 1.75; }}

/* ── expander ── */
[data-testid="stExpander"] {{
    background: {CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 13px !important;
    margin-top: 2rem !important;
}}
[data-testid="stExpander"] summary {{
    font-size: .9rem !important; font-weight: 700 !important;
    color: {TEXT2} !important; padding: 1.1rem 1.3rem !important;
}}

/* ── gp section label ── */
.gp-section-label {{
    font-size: .72rem; font-weight: 900;
    text-transform: uppercase; letter-spacing: .15em;
    color: {TEXT3}; margin-bottom: 1rem;
    display: flex; align-items: center; gap: .6rem;
}}

/* ── photo fallback ── */
.photo-fallback {{
    width: 82px; height: 62px; border-radius: 10px;
    background: {CARD2}; border: 1px dashed {BORDER2};
    display: flex; align-items: center; justify-content: center;
    color: {TEXT3}; font-size: .78rem;
}}

/* ── source pills inside tables ── */
.mt-wrap {{ overflow-x: auto; margin: 4px 0 12px 0; }}
.mt-table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
.mt-table th {{
    text-align: left; padding: .8rem 1.1rem;
    color: rgba(255,255,255,0.72);
    font-weight: 800; font-size: .67rem;
    letter-spacing: .12em; text-transform: uppercase;
    border-bottom: 2px solid rgba(255,255,255,0.08);
    white-space: nowrap; background: {CHARCOAL};
}}
.mt-table td {{
    padding: .78rem 1.1rem; color: {TEXT};
    border-bottom: 1px solid {BORDER}; white-space: nowrap; font-size: .9rem;
}}
.mt-table tr:nth-child(even) td {{ background: #FAFBFD; }}
.mt-table tr:last-child td {{ border-bottom: none; }}
.mt-table tr:hover td {{ background: {LIGHT_P} !important; }}

/* ── spinner ── */
[data-testid="stSpinner"] {{ color: {NBA_BLUE} !important; }}

/* ── button ── */
.stButton > button {{
    background: {NBA_BLUE} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 800 !important;
    font-size: .92rem !important;
    padding: .7rem 1.8rem !important;
    letter-spacing: .03em !important;
    transition: background .18s, transform .15s, box-shadow .18s !important;
}}
.stButton > button:hover {{
    background: #0f2f6a !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(23,64,139,0.25) !important;
}}
</style>
""", unsafe_allow_html=True)

# matplotlib chart palette (light theme)
MPLBG = "#FFFFFF"
MPLTX = "#1A1F2E"
MPLDM = "#7A8799"
MPLGR = "#E8EDF4"
C_PRIMARY = NBA_BLUE
C_SUCCESS = SUCCESS
C_DANGER  = NBA_RED


# ===== LOGIC (verbatim from app.py) =====

# -----------------------------------------------------------------------------
# Cached wrappers — every data_pipeline call goes through @st.cache_data so a
# repeated view (same args) is instant and doesn't re-hit the pipeline.
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def team_names():
    return sorted(t["full_name"] for t in teams.get_teams())


@st.cache_data(show_spinner="Pulling matchup data…")
def cached_matchups(player_name, season):
    """Matchup table annotated with each defender's team abbreviation."""
    df = dp.get_matchups(player_name, season)
    return dp.annotate_matchups_with_team(df, season)


@st.cache_data(show_spinner=False)
def cached_team_abbr(team_name):
    return dp.get_team_abbreviation(team_name)


@st.cache_data(show_spinner="Projecting matchups…")
def cached_best_defenders_projected(star_name, star_team, my_team, season):
    return dp.best_defenders_projected(star_name, star_team, my_team, season)


@st.cache_data(show_spinner="Projecting matchups…")
def cached_projected_vs_roster(attacker_name, attacker_team, opp_team, season):
    """Project my attacker against every player on the opponent's roster."""
    roster = dp.get_roster(opp_team, season)["PLAYER"].tolist()
    return [dp.project_matchup(attacker_name, attacker_team, d, season)
            for d in roster]


@st.cache_data(show_spinner="Pulling shot chart…")
def cached_shots(player_name, team_name, season):
    return dp.get_shots(player_name, team_name, season)


@st.cache_data(show_spinner=False)
def cached_league_shot_avgs(player_name, team_name, season):
    return dp.get_league_shot_averages(player_name, team_name, season)


@st.cache_data(show_spinner="Building scouting summary…")
def cached_summary(player_name, team_name, season):
    return dp.scouting_summary(player_name, team_name, season)


@st.cache_data(show_spinner="Loading roster…")
def cached_roster_names(team_name, season):
    """List of player display names on a team's roster for the season."""
    return dp.get_roster(team_name, season)["PLAYER"].tolist()


@st.cache_data(show_spinner=False)
def cached_top_scorer(team_name, season):
    return dp.get_top_scorer(team_name, season)


@st.cache_data(show_spinner=False)
def cached_photo_bytes(player_name):
    """Headshot image bytes, or None if it can't be fetched (graceful — a
    missing photo must never crash a card)."""
    try:
        url = dp.get_player_photo_url(player_name)
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        return None
    return None


@st.cache_data(show_spinner=False)
def cached_headline_stats(player_name, team_name, season):
    return dp.get_player_headline_stats(player_name, team_name, season)


@st.cache_data(show_spinner=False)
def cached_avg_ppp(player_name, season):
    return dp.get_player_avg_matchup_pts_per_poss(player_name, season)


@st.cache_data(show_spinner=False)
def cached_advanced_stats(player_name, team_name, season):
    return dp.get_advanced_player_stats(player_name, team_name, season)


@st.cache_data(show_spinner=False)
def cached_four_factors(team_name, season):
    return dp.get_four_factors(team_name, season)


@st.cache_data(show_spinner="Pulling clutch stats…")
def cached_clutch_stats(team_name, season):
    return dp.get_clutch_stats(team_name, season)


@st.cache_data(show_spinner="Pulling clutch shot profile…")
def cached_clutch_shot_profile(player_name, team_name, season):
    return dp.get_clutch_shot_profile(player_name, team_name, season)


@st.cache_data(show_spinner="Finding the matchup to hunt…")
def cached_attack_mismatch(my_team, opponent, season, exclude_defender=None):
    exclude = {exclude_defender} if exclude_defender else None
    return dp.find_attack_mismatch(my_team, opponent, season, exclude=exclude)


@st.cache_data(show_spinner=False)
def cached_recommend_defender(star, opponent, my_team, season):
    return dp.recommend_defender(star, opponent, my_team, season)


@st.cache_data(show_spinner=False)
def cached_position_map(season):
    return dp.get_player_position_map(season)


@st.cache_data(show_spinner=False)
def cached_attacker_profile(player_name, team_name, season):
    return dp.get_attacker_zone_profile(player_name, team_name, season)


@st.cache_data(show_spinner=False)
def cached_defender_zone_defense(season):
    return dp.get_defender_zone_defense(season)


def _default_index(names, target):
    """Index of `target` in `names`, tolerant of case/accent-ish mismatches;
    falls back to 0 so a dropdown always has a valid default."""
    if not target:
        return 0
    if target in names:
        return names.index(target)
    low = target.lower()
    for i, name in enumerate(names):
        if name.lower() == low:
            return i
    return 0


def roster_dropdown(team_name, season, label, key):
    """Render a player dropdown from a team's roster, defaulting to the top
    scorer. Returns the selected player name, or None if the roster/stat pull
    failed (a message is shown in that case)."""
    try:
        names = cached_roster_names(team_name, season)
    except Exception as err:
        st.error(f"Couldn't load the {team_name} roster for {season}: {err}")
        return None
    if not names:
        st.warning(f"No roster found for {team_name} in {season}.")
        return None

    try:
        top = cached_top_scorer(team_name, season)
    except Exception:
        # Non-fatal — we just lose the smart default and start at the top of the list.
        top = None

    idx = _default_index(names, top)
    return st.selectbox(label, names, index=idx, key=key)


# -----------------------------------------------------------------------------
# Half-court shot chart (matplotlib)
# -----------------------------------------------------------------------------
def draw_court(ax, color="black", lw=1.5):
    """Draw a simple half court on `ax`, in the nba_api coordinate system
    (hoop at (0, 0); LOC_X ~ -250..250, LOC_Y ~ -50..420)."""
    hoop = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False)
    backboard = Rectangle((-30, -7.5), 60, -1, linewidth=lw, color=color)

    # Paint (the lane) + free-throw circle.
    outer_box = Rectangle((-80, -47.5), 160, 190, linewidth=lw, color=color, fill=False)
    inner_box = Rectangle((-60, -47.5), 120, 190, linewidth=lw, color=color, fill=False)
    top_ft = Arc((0, 142.5), 120, 120, theta1=0, theta2=180, linewidth=lw, color=color)
    bottom_ft = Arc((0, 142.5), 120, 120, theta1=180, theta2=0, linewidth=lw,
                    color=color, linestyle="dashed")
    restricted = Arc((0, 0), 80, 80, theta1=0, theta2=180, linewidth=lw, color=color)

    # Three-point line: corners + arc.
    corner_left = Rectangle((-220, -47.5), 0, 140, linewidth=lw, color=color)
    corner_right = Rectangle((220, -47.5), 0, 140, linewidth=lw, color=color)
    three_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158, linewidth=lw, color=color)

    outer = Rectangle((-250, -47.5), 500, 470, linewidth=lw, color=color, fill=False)

    for element in [hoop, backboard, outer_box, inner_box, top_ft, bottom_ft,
                    restricted, corner_left, corner_right, three_arc, outer]:
        ax.add_patch(element)
    return ax


def shot_chart_figure(shots):
    fig, ax = plt.subplots(figsize=(6, 5.6))
    made = shots[shots["SHOT_MADE_FLAG"] == 1]
    missed = shots[shots["SHOT_MADE_FLAG"] == 0]

    ax.scatter(missed["LOC_X"], missed["LOC_Y"], c="#c0392b", marker="x",
               s=28, linewidths=1.2, alpha=0.7, label="Missed")
    ax.scatter(made["LOC_X"], made["LOC_Y"], facecolors="none",
               edgecolors="#27ae60", marker="o", s=34, linewidths=1.2,
               alpha=0.8, label="Made")

    draw_court(ax)
    ax.set_xlim(-250, 250)
    ax.set_ylim(422.5, -47.5)   # flip so the hoop sits at the bottom
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    return fig


MIN_ZONE_ATTEMPTS = 5   # below this in a zone, the make% is too noisy to colour
MIN_HEX_ATTEMPTS = 3    # below this in a hex bin, show neutral grey (low sample)
HEX_GRIDSIZE = 17       # hexagons across the court width (bigger bins = cleaner zones)
HEX_EXTENT = (-250, 250, -47.5, 422.5)


def hot_cold_shot_chart(shots, league_avg_df):
    """Goldsberry-style hexbin hot/cold chart. Shots are aggregated into
    hexagonal bins across the half-court, encoding two variables:
      - hex SIZE  = shot volume from that spot (bigger = more attempts)
      - hex COLOUR = player make% there vs the league average for that zone
                     (green = above/hot, red = below/cold)
    Bins with fewer than MIN_HEX_ATTEMPTS shots are drawn small and neutral grey
    (low sample). Court lines are drawn on top so they stay visible. Pure
    rendering change — the data (get_shots) is untouched."""
    import numpy as np
    import matplotlib as mpl
    from matplotlib.patches import RegularPolygon

    # League FG% per (zone, area), and a per-shot league baseline for each shot.
    la = league_avg_df.groupby(["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA"]).agg(
        fgm=("FGM", "sum"), fga=("FGA", "sum"))
    la["lpct"] = la["fgm"] / la["fga"].where(la["fga"] > 0)
    league_pct = la["lpct"].to_dict()
    overall_lg = (float(league_avg_df["FGM"].sum())
                  / max(float(league_avg_df["FGA"].sum()), 1.0))

    x = shots["LOC_X"].to_numpy(dtype=float)
    y = shots["LOC_Y"].to_numpy(dtype=float)
    made = shots["SHOT_MADE_FLAG"].to_numpy(dtype=float)
    keys = list(zip(shots["SHOT_ZONE_BASIC"], shots["SHOT_ZONE_AREA"]))
    lg_per_shot = np.array(
        [league_pct[k] if (k in league_pct and not pd.isna(league_pct[k]))
         else overall_lg for k in keys], dtype=float)

    surface = "#FFFFFF"
    fig, ax = plt.subplots(figsize=(6, 5.6))
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    # Use hexbin once just to get the hex-lattice centres (we draw the hexes
    # ourselves so we can vary their size). Each shot then belongs to its nearest
    # centre — for a hex lattice that is exactly its hexagonal cell.
    hb = ax.hexbin(x, y, gridsize=HEX_GRIDSIZE, extent=HEX_EXTENT, mincnt=1)
    centres = np.asarray(hb.get_offsets(), dtype=float)
    hb.remove()

    if len(centres) == 0:
        draw_court(ax, color="#8090A8")
        ax.set_xlim(-250, 250)
        ax.set_ylim(422.5, -47.5)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
        return fig

    ox, oy = centres[:, 0], centres[:, 1]
    idx = ((x[:, None] - ox[None, :]) ** 2
           + (y[:, None] - oy[None, :]) ** 2).argmin(axis=1)
    nbins = len(centres)
    counts = np.bincount(idx, minlength=nbins).astype(float)
    makes = np.bincount(idx, weights=made, minlength=nbins)
    lgsum = np.bincount(idx, weights=lg_per_shot, minlength=nbins)
    with np.errstate(invalid="ignore", divide="ignore"):
        pmake = np.where(counts > 0, makes / counts, np.nan)
        lgbase = np.where(counts > 0, lgsum / counts, np.nan)
    diff = pmake - lgbase

    # Hex sizing: radius scales with sqrt(volume) so area ~ attempts.
    cell = (HEX_EXTENT[1] - HEX_EXTENT[0]) / HEX_GRIDSIZE
    r_max, r_min = cell * 0.62, cell * 0.18
    peak = counts.max() if counts.max() > 0 else 1.0
    cmap = mpl.cm.RdYlGn
    norm = mpl.colors.Normalize(vmin=-0.12, vmax=0.12)

    for i in range(nbins):
        c = counts[i]
        if c <= 0:
            continue
        if c < MIN_HEX_ATTEMPTS or np.isnan(diff[i]):
            # low sample -> small, faint grey so it recedes (still shown)
            colour, radius, alpha = "#C8CEDB", r_min * 0.6, 0.4
        else:
            colour = cmap(norm(diff[i]))
            radius = r_min + (r_max - r_min) * np.sqrt(c / peak)
            alpha = 0.92
        ax.add_patch(RegularPolygon((ox[i], oy[i]), numVertices=6, radius=radius,
                                    orientation=0.0, facecolor=colour,
                                    edgecolor="none", alpha=alpha, zorder=1))

    draw_court(ax, color="#7A8799", lw=1.4)            # court lines on top
    ax.set_xlim(-250, 250)
    ax.set_ylim(422.5, -47.5)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")

    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.02, ticks=[-0.12, 0, 0.12])
    cbar.ax.set_yticklabels(["cold", "avg", "hot"])
    cbar.ax.tick_params(colors="#7A8799")
    cbar.outline.set_edgecolor("#D5DCE6")
    # Legend: low-sample swatch + a note that hex size = volume.
    proxy = RegularPolygon((0, 0), numVertices=6, radius=1, facecolor="#C8CEDB",
                           edgecolor="none")
    ax.legend([proxy], [f"low sample (<{MIN_HEX_ATTEMPTS})"], loc="upper right",
              fontsize=7, framealpha=0.2, labelcolor="#7A8799", handlelength=1.0)
    return fig


# Radar axes: (label, advanced-stats key). All use league RANK -> percentile, so
# higher percentile = better at that metric (defense is already ranked so #1 =
# best defender, which lines up).
RADAR_METRICS = [
    ("Scoring\nefficiency", "ts_pct"),
    ("Usage", "usg_pct"),
    ("Offensive\nrating", "off_rating"),
    ("Defensive\nrating", "def_rating"),
    ("Rebounding", "reb_pct"),
    ("Playmaking", "ast_pct"),
]


def _percentile(adv, key):
    """Turn a league rank into a 0–100 percentile (rank 1 = ~100). None if the
    rank/total is missing."""
    rank = adv.get(key, {}).get("rank")
    total = adv.get("total_players")
    if not rank or not total or total <= 1:
        return None
    return (1 - (rank - 1) / (total - 1)) * 100


def comparison_radar(star_name, star_team, defender_name, defender_team, season):
    """Percentile radar comparing the scouted star vs our assigned defender
    across six advanced metrics. Each axis is a league percentile (0–100)."""
    import numpy as np

    star_adv = cached_advanced_stats(star_name, star_team, season)
    def_adv = cached_advanced_stats(defender_name, defender_team, season)

    labels = [m[0] for m in RADAR_METRICS]
    star_vals = [_percentile(star_adv, k) or 0 for _, k in RADAR_METRICS]
    def_vals = [_percentile(def_adv, k) or 0 for _, k in RADAR_METRICS]

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]                       # close the loop
    star_vals += star_vals[:1]
    def_vals += def_vals[:1]

    surface = "#FFFFFF"
    fig, ax = plt.subplots(figsize=(5.2, 5.2), subplot_kw={"polar": True})
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    for vals, colour, name in ((star_vals, "#d18a8a", star_name),
                               (def_vals, "#5aa17f", defender_name)):
        ax.plot(angles, vals, color=colour, linewidth=2, label=name)
        ax.fill(angles, vals, color=colour, alpha=0.18)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color="#1A1F2E", fontsize=8)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], color="#8090A8", fontsize=7)
    ax.set_ylim(0, 100)
    ax.spines["polar"].set_color("#D5DCE6")
    ax.grid(color="#D5DCE6", linewidth=0.6)
    ax.set_title("League percentile (higher = better)", color="#7A8799",
                 fontsize=8, pad=14)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.12), fontsize=8,
              facecolor=surface, edgecolor="#D5DCE6", labelcolor="#1A1F2E")
    return fig


# -----------------------------------------------------------------------------
# Presentation helpers — plain-language columns and a shared table renderer
# -----------------------------------------------------------------------------
DISPLAY_COLS = ["DEF_PLAYER_NAME", "TEAM", "PARTIAL_POSS", "PLAYER_PTS",
                "PTS_PER_POSS", "MATCHUP_FG_PCT", "MATCHUP_FG3_PCT"]
COL_RENAME = {
    "DEF_PLAYER_NAME": "Defender",
    "TEAM": "Team",
    "PARTIAL_POSS": "Possessions guarded",
    "PLAYER_PTS": "Points scored",
    "PTS_PER_POSS": "Points per possession",
    "MATCHUP_FG_PCT": "FG%",
    "MATCHUP_FG3_PCT": "3PT%",
}


# Professional styling — no emojis. Text pills for source, coloured text for
# projection verdicts, all tuned for the dark Streamlit background.
TABLE_CSS = """
<style>
.mt-wrap { overflow-x: auto; margin: 2px 0 10px 0; }
.mt-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.mt-table th {
    text-align: left; padding: 6px 12px; color: #8a9198; font-weight: 600;
    font-size: 0.68rem; letter-spacing: 0.05em; text-transform: uppercase;
    border-bottom: 1px solid rgba(255,255,255,0.14); white-space: nowrap;
}
.mt-table td {
    padding: 6px 12px; color: #e3e5e8;
    border-bottom: 1px solid rgba(255,255,255,0.06); white-space: nowrap;
}
.pill {
    display: inline-block; padding: 1px 9px; border-radius: 999px;
    font-size: 0.64rem; font-weight: 700; letter-spacing: 0.06em;
}
.pill-actual { background: rgba(255,255,255,0.16); color: #eceef0; }
.pill-projected {
    background: transparent; color: #9aa0a6;
    border: 1px solid rgba(255,255,255,0.24);
}
.lab { font-weight: 600; }
.lab-fav   { color: #63b384; }   /* muted green  */
.lab-neu   { color: #9aa0a6; }   /* grey         */
.lab-tough { color: #d18a8a; }   /* muted red    */
/* Takeaway plan cards */
.plan-card {
    padding: 10px 16px; border-radius: 8px; margin: 6px 0 4px 0;
    background: rgba(255,255,255,0.035); border-left: 3px solid #5f7fa6;
}
.plan-card.attack { border-left-color: #5aa17f; }
.plan-tag {
    font-size: 0.64rem; font-weight: 700; letter-spacing: 0.09em;
    text-transform: uppercase; color: #8a9198; margin-bottom: 3px;
}
.plan-text { font-size: 0.98rem; color: #f1f3f4; line-height: 1.35; }
.plan-sub  { font-size: 0.85rem; color: #b7bcc2; margin-top: 4px; }
.legend { font-size: 0.78rem; color: #9aa0a6; margin: 2px 0 6px 0; }
.legend-note { color: #8a9198; }
/* Player card */
.gp-header { font-size: 1.02rem; color: #b7bcc2; margin: 2px 0 10px 0; }
.card-name { font-size: 1.06rem; font-weight: 700; color: #f1f3f4; }
.card-meta { font-size: 0.84rem; color: #9aa0a6; margin-bottom: 6px; }
.card-stats { font-size: 0.92rem; color: #e3e5e8; }
.card-stats span { margin-right: 16px; }
.card-stats b { color: #f1f3f4; }
.photo-fallback {
    width: 140px; height: 102px; border-radius: 6px;
    background: rgba(255,255,255,0.05); border: 1px dashed rgba(255,255,255,0.18);
    display: flex; align-items: center; justify-content: center;
    color: #8a9198; font-size: 0.8rem;
}
</style>
"""

LABEL_CLASS = {"Favourable": "lab-fav", "Neutral": "lab-neu", "Tough": "lab-tough"}


def _pct_dict(d):
    """Format a {label: number} dict of already-percentage values as clean
    one-decimal percent strings, e.g. 61.8 -> '61.8%'."""
    return {k: f"{v:.1f}%" for k, v in d.items()}


def _source_pill(kind):
    """Subtle text tag: 'actual' reads solid/confident, 'projected' muted."""
    if kind == "projected":
        return '<span class="pill pill-projected">PROJECTED</span>'
    return '<span class="pill pill-actual">ACTUAL</span>'


def _label_html(label):
    cls = LABEL_CLASS.get(label, "lab-neu")
    return f'<span class="lab {cls}">{label}</span>'


def source_legend(order_note):
    st.markdown(
        f"<div class='legend'>{_source_pill('actual')} real possessions this "
        f"season &nbsp;&nbsp; {_source_pill('projected')} estimated from season "
        f"profiles. <span class='legend-note'>{order_note}</span></div>",
        unsafe_allow_html=True)


def _html_table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
                   for row in rows)
    st.markdown(f"<div class='mt-wrap'><table class='mt-table'><thead><tr>{head}"
                f"</tr></thead><tbody>{body}</tbody></table></div>",
                unsafe_allow_html=True)


def show_matchup_table(df, source="actual", positions=None, limit=None):
    """Render an observed-matchup frame as a styled table with a Source pill on
    every row. Numbers formatted: FG%/3PT% one-decimal %, possessions 1dp,
    pts/poss 2dp.

    `positions` (name -> pos dict) adds a defender Position column. `limit` caps
    the visible rows; the rest go behind a 'Show all' expander."""
    if df.empty:
        st.caption("No defenders in this group.")
        return
    view = df[DISPLAY_COLS].rename(columns=COL_RENAME).copy()
    pill = _source_pill(source)
    pos = positions or {}
    headers = ["Source", "Defender", "Team"]
    if positions is not None:
        headers.append("Pos")
    headers += ["Possessions guarded", "Points scored", "Points per possession",
                "FG%", "3PT%"]
    rows = []
    for _, r in view.iterrows():
        row = [pill, r["Defender"], r["Team"]]
        if positions is not None:
            row.append(pos.get(r["Defender"], "—"))
        row += [
            f"{r['Possessions guarded']:.1f}",
            f"{r['Points scored']:.0f}",
            ppp_value(r['Points per possession']),
            f"{r['FG%'] * 100:.1f}%",
            f"{r['3PT%'] * 100:.1f}%",
        ]
        rows.append(row)

    if limit and len(rows) > limit:
        _html_table(headers, rows[:limit])
        with st.expander(f"Show all {len(rows)} defenders"):
            _html_table(headers, rows[limit:])
    else:
        _html_table(headers, rows)


def show_projected_table(results, exclude_names=None, reason_key="reason",
                         positions=None):
    """Render projected matchup dicts as a styled table: Projected pill, a
    colour-coded verdict, edge score, and the reason.

    `reason_key` picks the wording: "reason" (Attack — "he" is my attacker) or
    "reason_defend" (Defend — row is a defender, scouted player is the shooter).
    `positions` (name -> pos dict) adds a defender Position column. Players with
    no usable defensive data are dropped; a small grey line notes how many."""
    exclude = exclude_names or set()
    pos = positions or {}
    usable = [r for r in results if r["defender"] not in exclude]
    excluded = sum(1 for r in usable if r.get("insufficient"))
    keep = [r for r in usable if not r.get("insufficient")]
    if keep:
        pill = _source_pill("projected")
        headers = ["Source", "Defender"]
        if positions is not None:
            headers.append("Pos")
        headers += ["Projection", "Edge score", "Why"]
        rows = []
        for r in keep:
            score = r["score"] if abs(r["score"]) >= 0.005 else 0.0
            row = [pill, r["defender"]]
            if positions is not None:
                row.append(pos.get(r["defender"], "—"))
            row += [_label_html(r["label"]), f"{score:.2f}",
                    r.get(reason_key, r["reason"])]
            rows.append(row)
        _html_table(headers, rows)
        st.caption("Edge score = weighted FG% edge, roughly −0.10 to +0.10 "
                   "(positive favours the scorer). Within ±0.01 is Neutral; "
                   "±0.03 a modest edge, ±0.08+ a strong one.")
    else:
        st.caption("No projected matchups to show.")
    if excluded:
        st.caption(f"{excluded} player(s) excluded — insufficient defensive data.")


def force_direction_chart(shots, recommended):
    """Small grouped bar chart supporting the 'force him {direction}' tip:
    per direction (Left / Centre / Right), his make% and his shot volume, with
    the recommended (coldest) direction highlighted. Returns a fig or None."""
    import numpy as np

    b = direction_breakdown(shots)
    if not b:
        return None
    order = [("left", "Left"), ("down the middle", "Centre"), ("right", "Right")]
    labels, makes, vols, keys = [], [], [], []
    for key, disp in order:
        if key in b:
            labels.append(disp)
            makes.append(b[key]["make_pct"])
            vols.append(b[key]["attempts"])
            keys.append(key)
    n = len(labels)
    if n == 0:
        return None
    rec_idx = keys.index(recommended) if recommended in keys else None

    surface = "#FFFFFF"
    fig, ax = plt.subplots(figsize=(4.3, 2.4))
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    ax2 = ax.twinx()

    x = np.arange(n)
    w = 0.38
    # Make% bars on the left axis; the recommended (coldest) side is highlighted
    # red, the others muted, so the chart confirms the text tip at a glance.
    make_colours = ["#d18a8a" if i == rec_idx else "#8090A8" for i in range(n)]
    ax.bar(x - w / 2, makes, w, color=make_colours, zorder=3)
    # Volume (attempts) bars on the right axis, muted blue.
    ax2.bar(x + w / 2, vols, w, color="#5A7FA0", zorder=3)

    ax.set_ylim(0, max(100, max(makes) * 1.1))
    ax2.set_ylim(0, max(vols) * 1.25 if vols else 1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="#1A1F2E", fontsize=8)
    if rec_idx is not None:
        ax.get_xticklabels()[rec_idx].set_color("#C9082A")
        ax.get_xticklabels()[rec_idx].set_fontweight("bold")
        ax.annotate("force here", xy=(rec_idx, 0), xytext=(rec_idx, -18),
                    textcoords="data", ha="center", fontsize=7.5,
                    color="#d18a8a", annotation_clip=False)

    ax.set_ylabel("Make %", color="#7A8799", fontsize=8)
    ax2.set_ylabel("Attempts", color="#3D4A5C", fontsize=8)
    for a in (ax, ax2):
        a.tick_params(colors="#8090A8", labelsize=7)
        for s in a.spines.values():
            s.set_color("#D5DCE6")
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E8EDF4", linewidth=0.6)
    fig.tight_layout()
    return fig


def attack_edge_chart(profile, def_zones, attacker_name, defender_name):
    """Diverging bar chart for the selected matchup: my attacker's shot diet
    (share of shots at rim / short-mid / three) on the left, and the defender's
    performance in those same zones on the right (allowed FG% vs league average,
    where ABOVE-average allowed = the defender is exploitable). The zone where
    the attacker's volume overlaps the defender's weakness is highlighted — that
    is the edge the plan sentence points at."""
    import numpy as np

    zones = [("at_rim", "At rim"), ("short_mid", "Short-mid"), ("three", "Three")]
    labels, shares, pms = [], [], []
    for key, disp in zones:
        labels.append(disp)
        shares.append((profile.get(key, {}).get("share", 0.0) or 0.0) * 100)
        pm = 0.0
        if def_zones and key in def_zones:
            pm = (def_zones[key].get("plusminus", 0.0) or 0.0) * 100   # pp vs avg
        pms.append(pm)

    # Edge = where his volume meets the defender's weakness (positive pm).
    edge_scores = [(shares[i] / 100.0) * max(pms[i], 0.0) for i in range(3)]
    edge_idx = int(np.argmax(edge_scores)) if max(edge_scores) > 0 else None

    y = np.arange(3)[::-1]            # At rim on top
    surface = "#FFFFFF"
    fig, (axL, axR) = plt.subplots(
        1, 2, sharey=True, figsize=(5.6, 2.5),
        gridspec_kw={"wspace": 0.55})
    fig.patch.set_facecolor(surface)
    for a in (axL, axR):
        a.set_facecolor(surface)

    # Left — attacker shot diet (grows leftward).
    bl = axL.barh(y, shares, height=0.62, color="#5a7fa0", zorder=3)
    axL.invert_xaxis()
    axL.set_xlim(max(shares + [1]) * 1.18, 0)
    axL.set_title(f"{attacker_name.split()[-1]} shot diet (%)", fontsize=8,
                  color="#7A8799")
    for yi, s in zip(y, shares):
        axL.text(s + max(shares) * 0.03, yi, f"{s:.0f}%", va="center", ha="right",
                 fontsize=7.5, color="#1A1F2E")

    # Right — defender vs league average (positive = exploitable green).
    colours = ["#63b384" if p > 0.3 else ("#d18a8a" if p < -0.3 else "#9aa0a6")
               for p in pms]
    axR.barh(y, pms, height=0.62, color=colours, zorder=3)
    axR.axvline(0, color="#5a6068", lw=0.8)
    lim = max(4.0, max(abs(p) for p in pms) * 1.25)
    axR.set_xlim(-lim, lim)
    axR.set_title(f"{defender_name.split()[-1]} D — FG% vs avg", fontsize=8,
                  color="#7A8799")
    for yi, p in zip(y, pms):
        off = lim * 0.05
        axR.text(p + (off if p >= 0 else -off), yi, f"{p:+.1f}", va="center",
                 ha="left" if p >= 0 else "right", fontsize=7.5, color="#1A1F2E")

    # Highlight the edge zone (volume meets weakness): tag its label + band it.
    disp = [labels[i] + ("  ◂ EDGE" if i == edge_idx else "") for i in range(3)]
    axL.set_yticks(y)
    axL.set_yticklabels(disp, fontsize=8, color="#1A1F2E")
    for a in (axL, axR):
        a.tick_params(colors="#8090A8", labelsize=7)
        for s in a.spines.values():
            s.set_color("#D5DCE6")
        a.set_xticks([])

    if edge_idx is not None:
        ey = y[edge_idx]
        for a in (axL, axR):
            a.axhspan(ey - 0.46, ey + 0.46, color="#63b384", alpha=0.10, zorder=0)
        axL.get_yticklabels()[edge_idx].set_color("#74c79c")
        axL.get_yticklabels()[edge_idx].set_fontweight("bold")
    fig.tight_layout()
    return fig


def direction_breakdown(shots):
    """Volume-weighted make% and attempts per direction (left / down the middle /
    right), bucketing SHOT_ZONE_AREA. Each bucket's make% = total makes / total
    attempts. Backcourt heaves dropped. Returns
    {label: {"make_pct": float, "attempts": int}} or {}."""
    def bucket(zone):
        if "Back Court" in zone:
            return None
        if "Left" in zone:
            return "left"
        if "Right" in zone:
            return "right"
        return "down the middle"

    df = shots.copy()
    df["_bucket"] = df["SHOT_ZONE_AREA"].map(bucket)
    df = df[df["_bucket"].notna()]
    if df.empty:
        return {}
    grp = df.groupby("_bucket")["SHOT_MADE_FLAG"].agg(makes="sum", attempts="count")
    out = {}
    for label in ("left", "down the middle", "right"):
        if label in grp.index and grp.loc[label, "attempts"] > 0:
            a = int(grp.loc[label, "attempts"])
            m = float(grp.loc[label, "makes"])
            out[label] = {"make_pct": round(m / a * 100, 1), "attempts": a}
    return out


def lowest_make_area_weighted(shots):
    """Coldest side for the attacker (lowest volume-weighted make%). Returns
    (label, make_pct, attempts) or None. Same logic as `direction_breakdown`,
    so the chart and the 'force him' sentence always agree."""
    b = direction_breakdown(shots)
    if not b:
        return None
    label = min(b, key=lambda k: b[k]["make_pct"])
    return label, b[label]["make_pct"], b[label]["attempts"]


# -----------------------------------------------------------------------------
# Takeaways (shared by the Overview, Attack and Defend tabs) + plan / card UI
# -----------------------------------------------------------------------------
def _avg_compare(value, avg):
    """Phrase a matchup pts/poss against the player's season average, e.g.
    'well below his 0.52 average'. Returns '' if there's no average."""
    if avg is None:
        return ""
    diff = value - avg
    if abs(diff) < 0.03:
        rel = "in line with"
    elif diff < 0:
        rel = "well below" if diff <= -0.08 else "below"
    else:
        rel = "well above" if diff >= 0.08 else "above"
    return f"{rel} his {avg:.2f} average"


def _cmp_suffix(value, avg):
    phrase = _avg_compare(value, avg)
    return f" — {phrase}" if phrase else ""


def defend_takeaway(star, opponent, my_team, season):
    """Defensive takeaway used by the Defend tab and Overview. Returns
    {sentence, force, kind, assigned}; kind in {observed, projected, none}.
    `assigned` is the my-team defender we'd put on the star (or None).

    The defender is chosen by dp.recommend_defender, which only considers
    rotation players (same ROTATION_MIN_MPG filter as the attack side) — so the
    'Assign X' plan and the radar that uses it never surface a bench artifact."""
    out = {"sentence": None, "force": None, "kind": "none", "assigned": None}
    try:
        rec = cached_recommend_defender(star, opponent, my_team, season)
    except Exception:
        rec = None
    avg = cached_avg_ppp(star, season)

    if rec and rec["kind"] == "observed":
        out["kind"] = "observed"
        out["assigned"] = rec["defender"]
        out["sentence"] = (
            f"Assign {rec['defender']} — held {star} to {rec['ppp']:.2f} "
            f"pts/poss over {rec['poss']:.0f} possessions"
            f"{_cmp_suffix(rec['ppp'], avg)}.")
    elif rec and rec["kind"] == "projected":
        out["kind"] = "projected"
        out["assigned"] = rec["defender"]
        out["sentence"] = (f"Assign {rec['defender']} — projected best rotation "
                           f"matchup vs {star} ({rec['label']}).")
    else:
        out["sentence"] = f"No rotation defender with matchup data vs {star} yet."

    try:
        shots = cached_shots(star, opponent, season)
        area = None if shots.empty else lowest_make_area_weighted(shots)
        if area:
            label, pct, _ = area
            out["force"] = f"Force him {label} — he shoots only {pct:.1f}% there."
    except Exception:
        pass
    return out


def _top_projected_edge(my_player, my_team, opponent, season, exclude=None):
    """Highest-scoring projected edge vs the opponent (best for my player), or
    None. The score may be <= 0 if no favourable matchup exists — the caller
    decides whether it's good enough to recommend."""
    exclude = exclude or set()
    try:
        proj = [r for r in cached_projected_vs_roster(my_player, my_team, opponent,
                                                      season)
                if not r.get("insufficient") and r["defender"] not in exclude]
    except Exception:
        return None
    proj.sort(key=lambda r: r["score"], reverse=True)
    return proj[0] if proj else None


def attack_takeaway(my_player, my_team, opponent, season):
    """Attack takeaway used by the Attack tab and Overview. Returns
    {sentence, kind}; kind in {observed, projected, none}.

    Only recommends "Attack X" when there's a genuine edge — i.e. my player
    scores at or above his own season average against that defender. If the best
    matchup he's actually faced is BELOW his average, the defender is doing a
    good job, so recommending an attack there would be backwards; instead we say
    so plainly and point to the best projected edge."""
    out = {"sentence": None, "kind": "none", "defender": None}
    try:
        matchups = cached_matchups(my_player, season)
        opp_abbr = cached_team_abbr(opponent)
    except Exception:
        return out
    avg = cached_avg_ppp(my_player, season)

    vs_opp = matchups[matchups["TEAM"] == opp_abbr] \
        .sort_values("PTS_PER_POSS", ascending=False)

    if not vs_opp.empty:
        best = vs_opp.iloc[0]
        ppp = best["PTS_PER_POSS"]
        if avg is None or ppp >= avg:
            # A real edge: he scores at/above his own average here.
            out["kind"] = "observed"
            out["defender"] = best["DEF_PLAYER_NAME"]
            out["sentence"] = (
                f"Attack {best['DEF_PLAYER_NAME']} — {my_player} scored {ppp:.2f} "
                f"pts/poss against him{_cmp_suffix(ppp, avg)}.")
        else:
            # His best observed matchup is still below his average — no proven
            # edge. Don't say "attack"; surface a projected edge if there is one.
            observed = set(vs_opp["DEF_PLAYER_NAME"])
            p = _top_projected_edge(my_player, my_team, opponent, season, observed)
            n = len(vs_opp)
            # Be honest about sample size — "everyone he's faced" overstates it
            # when it's really just one or two defenders.
            if n == 1:
                head = (f"No proven edge vs {opponent} — {my_player}'s only "
                        f"matchup there ({best['DEF_PLAYER_NAME']}) held him to "
                        f"{ppp:.2f}, below his {avg:.2f} average.")
            else:
                head = (f"No proven edge vs {opponent} — {my_player} is below his "
                        f"{avg:.2f} average against all {n} of their defenders "
                        f"he's faced (best: {best['DEF_PLAYER_NAME']}, {ppp:.2f}).")
            if p and p["score"] > 0:
                out["kind"] = "projected"
                out["defender"] = p["defender"]
                out["sentence"] = (f"{head} Projected best edge: {p['defender']} "
                                   f"({p['label']}).")
            else:
                out["kind"] = "observed"
                out["defender"] = best["DEF_PLAYER_NAME"]
                out["sentence"] = head
    else:
        # No head-to-head data at all — fall back to projections, but only call
        # it an "attack" if the best projection is actually favourable.
        p = _top_projected_edge(my_player, my_team, opponent, season)
        if p and p["score"] > 0:
            out["kind"] = "projected"
            out["defender"] = p["defender"]
            out["sentence"] = (f"Attack {p['defender']} — projected best edge vs "
                               f"{opponent} ({p['label']}).")
        elif p:
            out["kind"] = "projected"
            out["defender"] = p["defender"]
            out["sentence"] = (f"No favourable matchup projected vs {opponent} — "
                               f"closest is {p['defender']} ({p['label']}).")
        else:
            out["sentence"] = f"No usable matchup data vs {opponent} yet."
    return out


def render_plan(tag, sentence, accent="defend", sub=None):
    """Render a takeaway as a clean plan card with a small uppercase label."""
    if not sentence:
        return
    cls = "plan-card attack" if accent == "attack" else "plan-card"
    sub_html = f"<div class='plan-sub'>{sub}</div>" if sub else ""
    st.markdown(
        f"<div class='{cls}'><div class='plan-tag'>{tag}</div>"
        f"<div class='plan-text'>{sentence}</div>{sub_html}</div>",
        unsafe_allow_html=True)


GREEN, GREY, RED = SUCCESS, TEXT3, DANGER


def rank_cue(rank, total):
    """Colour for a league rank (rank 1 = best): top third green, middle grey,
    bottom third red. Unknown rank/total -> grey."""
    if not rank or not total or total <= 0:
        return GREY
    if rank <= total / 3:
        return GREEN
    if rank > 2 * total / 3:
        return RED
    return GREY


def _adv_chip(label, value_str, rank, total):
    """A single bordered advanced-metric chip: label, colour-coded value, rank."""
    cue = rank_cue(rank, total)
    rank_str = f"#{rank} of {total}" if rank and total else "—"
    return (f"<div class='adv-chip'><div class='adv-k'>{label}</div>"
            f"<div class='adv-v' style='color:{cue}'>{value_str}</div>"
            f"<div class='adv-r'>{rank_str}</div></div>")


def game_plan_bullets(my_team, opponent, my_star, opp_star, season,
                      defend_tk, mismatch):
    """Coach's-notes summary: 4–6 plain-English bullets templated purely from
    values we've already pulled (takeaways + advanced stats). Each piece is
    guarded so a missing stat just drops its bullet."""
    bullets = []
    # 1. Offence — hunt the best matchup (not just feature our top scorer).
    if mismatch and mismatch["kind"] == "observed":
        bullets.append(
            f"Hunt {mismatch['defender']} with {mismatch['attacker']} — "
            f"{mismatch['ppp']:.2f} pts/poss on him, above his "
            f"{mismatch['attacker_avg']:.2f} average.")
    elif mismatch:
        bullets.append(
            f"Hunt {mismatch['defender']} with {mismatch['attacker']} — "
            f"projected {mismatch['label']} matchup.")
    # 2 + 3. Defence — assign the best defender, force him to his weak side.
    if defend_tk and defend_tk.get("sentence"):
        bullets.append(defend_tk["sentence"])
    if defend_tk and defend_tk.get("force"):
        bullets.append(defend_tk["force"].replace("Force him", f"Force {opp_star}"))

    try:
        oadv = cached_advanced_stats(opp_star, opponent, season)
        usg, total = oadv["usg_pct"], oadv.get("total_players")
        if usg["value"] is not None and usg["rank"] and total:
            bullets.append(
                f"{opp_star} dominates the ball — {usg['value'] * 100:.0f}% usage "
                f"(#{usg['rank']} of {total}); make someone else beat you.")
    except Exception:
        pass

    try:
        madv = cached_advanced_stats(my_star, my_team, season)
        ts, total = madv["ts_pct"], madv.get("total_players")
        if ts["value"] is not None and ts["rank"] and total:
            bullets.append(
                f"Get {my_star} going — {ts['value'] * 100:.1f}% true shooting "
                f"(#{ts['rank']} of {total}); feed the hot hand.")
    except Exception:
        pass

    return bullets[:6]


def render_game_plan_summary(bullets):
    if not bullets:
        return
    items = "".join(f"<li>{b}</li>" for b in bullets)
    st.markdown(
        "<div class='gp-summary'><div class='gp-summary-tag'>GAME PLAN AT A "
        f"GLANCE</div><ul>{items}</ul></div>", unsafe_allow_html=True)


# (label, key, higher_is_better, value formatter)
FF_FACTORS = [
    ("Effective FG%", "efg_pct", True, "pct"),
    ("Free-throw rate", "fta_rate", True, "rate"),
    ("Turnover %", "tm_tov_pct", False, "pct"),
    ("Off. rebound %", "oreb_pct", True, "pct"),
]


def _ff_fmt(kind, value):
    if value is None:
        return "—"
    return f"{value:.3f}" if kind == "rate" else f"{value * 100:.1f}%"


def render_four_factors(my_team, opponent, my_ff, opp_ff):
    """Our team vs the opponent across the four factors, as paired horizontal
    bars per factor with the better side highlighted green."""
    try:
        my_abbr = cached_team_abbr(my_team)
    except Exception:
        my_abbr = "US"
    try:
        opp_abbr = cached_team_abbr(opponent)
    except Exception:
        opp_abbr = "OPP"

    total = my_ff.get("total_teams") or opp_ff.get("total_teams")
    html = ""
    for label, key, higher_better, kind in FF_FACTORS:
        a, b = my_ff.get(key), opp_ff.get(key)
        a_rank, b_rank = my_ff.get(key + "_rank"), opp_ff.get(key + "_rank")
        a_win = b_win = False
        if a is not None and b is not None and a != b:
            if (a > b) == higher_better:
                a_win = True
            else:
                b_win = True
        scale = max([v for v in (a, b) if v is not None], default=0)

        rows = ""
        for name, value, rank, win in ((my_abbr, a, a_rank, a_win),
                                       (opp_abbr, b, b_rank, b_win)):
            width = 0 if value is None or scale <= 0 else max(3, value / scale * 100)
            fill = "ff-win" if win else "ff-lose"
            vcls = "ff-val win" if win else "ff-val"
            # rank 1 = best for all four factors, so rank_cue colours uniformly
            cue = rank_cue(rank, total)
            rank_html = (f"<span class='ff-rank' style='color:{cue}'>#{rank}</span>"
                         if rank and total else "")
            rows += (f"<div class='ff-side'><span class='ff-name'>{name}</span>"
                     f"<div class='ff-track'><div class='ff-fill {fill}' "
                     f"style='width:{width:.0f}%'></div></div>"
                     f"<span class='{vcls}'>{_ff_fmt(kind, value)}</span>"
                     f"{rank_html}</div>")
        html += f"<div class='ff-row'><div class='ff-label'>{label}</div>{rows}</div>"

    # caption clarifies the colour-coded ranks (out of `total` teams)
    if total:
        html += (f"<div class='ff-note'>Each value is ranked across all {total} "
                 "teams — green = top third, grey = middle, red = bottom third "
                 "(rank 1 = best; for turnovers that means fewest).</div>")

    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Team identity — primary colours for the Game Plan header strip.
# -----------------------------------------------------------------------------
TEAM_COLORS = {
    "Atlanta Hawks": "#E03A3E", "Boston Celtics": "#007A33",
    "Brooklyn Nets": "#000000", "Charlotte Hornets": "#1D1160",
    "Chicago Bulls": "#CE1141", "Cleveland Cavaliers": "#860038",
    "Dallas Mavericks": "#00538C", "Denver Nuggets": "#0E2240",
    "Detroit Pistons": "#C8102E", "Golden State Warriors": "#1D428A",
    "Houston Rockets": "#CE1141", "Indiana Pacers": "#002D62",
    "Los Angeles Clippers": "#C8102E", "Los Angeles Lakers": "#552583",
    "Memphis Grizzlies": "#5D76A9", "Miami Heat": "#98002E",
    "Milwaukee Bucks": "#00471B", "Minnesota Timberwolves": "#236192",
    "New Orleans Pelicans": "#0C2340", "New York Knicks": "#F58426",
    "Oklahoma City Thunder": "#007AC1", "Orlando Magic": "#0077C0",
    "Philadelphia 76ers": "#006BB6", "Phoenix Suns": "#E56020",
    "Portland Trail Blazers": "#E03A3E", "Sacramento Kings": "#5A2D81",
    "San Antonio Spurs": "#C4CED4", "Toronto Raptors": "#CE1141",
    "Utah Jazz": "#002B5C", "Washington Wizards": "#E31837",
}

# Clutch shot-type bucket -> plain-language defensive read.
CLUTCH_READ = {
    "Drive / rim": "downhill rim",
    "Pull-up mid": "pull-up jumper",
    "Pull-up 3": "pull-up three",
    "Spot-up 3": "spot-up three",
    "Floater": "floater",
    "Post / fade": "post / fadeaway",
    "Mid-range": "mid-range",
}


def render_team_strip(my_team, opponent, season):
    """Header strip: '{My Team} vs {Opponent} · {Season}' with each team's
    primary colour as an accent and its logo (graceful if a logo doesn't load)."""
    def badge(team):
        color = TEAM_COLORS.get(team, "#888888")
        logo = ""
        try:
            tid = dp.get_team_id(team)
            logo = (f"<img class='team-logo' src='https://cdn.nba.com/logos/nba/"
                    f"{tid}/primary/L/logo.svg' alt='' />")
        except Exception:
            pass
        return (f"<span class='team-badge' style='border-left:5px solid {color}'>"
                f"{logo}<span class='team-name'>{team}</span></span>")

    st.markdown(
        f"<div class='team-strip'>{badge(my_team)}<span class='vs'>vs</span>"
        f"{badge(opponent)}<span class='season'>· {season}</span></div>",
        unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Glossary — each tab shows definitions for ONLY the metrics it displays.
# -----------------------------------------------------------------------------
GLOSSARY = {
    "source": ("Actual vs Projected", "*Actual* rows are real possessions the two "
               "players logged head-to-head this season; *Projected* rows are "
               "estimated from each player's season profile when they haven't "
               "faced off enough."),
    "poss_guarded": ("Possessions guarded", "how many times the two players went "
                     "head-to-head (Actual rows). More = more reliable."),
    "points_scored": ("Points scored", "points the scorer put up across those "
                      "head-to-head possessions."),
    "ppp": ("Points per possession", "scoring efficiency in a matchup; higher "
            "means the scorer won the battle. Takeaways compare it to the "
            "player's season average."),
    "fg": ("FG% / 3PT%", "field-goal and three-point percentage the scorer shot "
           "when guarded by that defender."),
    "projection": ("Projection", "the estimated verdict for a matchup with no "
                   "real data: *Favourable*, *Neutral*, or *Tough* for the scorer."),
    "edge": ("Edge score", "the projection's underlying number — a weighted FG% "
             "edge on a roughly −0.10 to +0.10 scale: positive favours the "
             "scorer, negative favours the defender, and within ±0.01 counts as "
             "Neutral. So ±0.03 is a modest edge, ±0.08+ a strong one."),
    "ppg": ("PPG / RPG / APG", "the player's season per-game points, rebounds, "
            "and assists."),
    "ts": ("TS%", "true shooting % — scoring efficiency across 2s, 3s, and free "
           "throws. The #N of M is the league rank; colour-coded green (top "
           "third) / grey (middle) / red (bottom third)."),
    "usg": ("USG%", "usage rate — the share of the team's plays a player finishes "
            "while on the floor. Higher = more central to the offence. Ranked and "
            "colour-coded like TS%."),
    "ortg": ("ORtg", "offensive rating — points the player's team scores per 100 "
             "possessions with him on the floor. Ranked and colour-coded."),
    "four_factors": ("Four Factors", "the four team stats that most decide games — "
                     "Effective FG%, Free-throw rate, Turnover %, and Offensive "
                     "rebound %. The better side of each is highlighted (for "
                     "turnovers, lower is better)."),
    "hotcold": ("Hot/cold shot chart", "each shot is shaded by the player's make% "
                "in that court zone vs the league average there — green = above "
                "average (hot), red = below (cold). Low-sample zones are greyed out."),
    "shot_zones": ("Make % by zone / area", "how often the player makes shots from "
                   "each part of the floor; each is its own FG%, so they don't add "
                   "up to 100%."),
    "action_types": ("Top action types", "the share of his shots that come from "
                     "each play type (jump shot, driving layup, etc.) — top 5 by "
                     "frequency."),
    "avg_dist": ("Avg shot distance", "the average distance of his shot attempts, "
                 "in feet."),
    "radar": ("Matchup radar", "each axis is a league percentile (0–100) for an "
              "advanced metric — further from the centre is better. Defensive "
              "rating is ranked so a strong defender scores high."),
    "clutch_def": ("Clutch", "the last 5 minutes of a game with the score within "
                   "5 points — the NBA's standard clutch window."),
    "clutch_gp": ("Clutch GP", "games in which the player logged clutch minutes. "
                  "More = a regular late-game presence."),
    "clutch_pts": ("Clutch PTS/G", "points per game the player scores in clutch "
                   "minutes."),
    "clutch_vs_lg": ("vs league", "how his clutch PTS/G compares to the league "
                     "average clutch scorer — green is above, red below."),
    "clutch_share": ("% of his pts", "the share of the player's season points "
                     "that come in clutch time — higher = more of a closer."),
    "clutch_fg": ("Clutch FG%", "field-goal percentage in clutch minutes."),
    "clutch_usg": ("Clutch USG%", "share of the team's clutch plays the player "
                   "finishes — how much the offence runs through him late."),
}

GLOSSARY_TABS = {
    "overview": ["ppg", "ts", "usg", "ortg", "ppp", "four_factors"],
    "attack": ["source", "poss_guarded", "points_scored", "ppp", "fg",
               "projection", "edge", "ppg", "ts", "usg", "ortg"],
    "defend": ["source", "poss_guarded", "points_scored", "ppp", "fg",
               "projection", "edge", "ppg", "ts", "usg", "ortg",
               "action_types", "shot_zones", "avg_dist", "hotcold", "radar"],
    "close": ["clutch_def", "clutch_gp", "clutch_pts", "clutch_vs_lg",
              "clutch_share", "clutch_fg", "clutch_usg"],
}


def render_glossary(tab_key):
    """Render the 'What do these numbers mean?' expander with only the metrics
    that appear on this tab."""
    keys = GLOSSARY_TABS.get(tab_key, [])
    if not keys:
        return
    lines = "\n".join(f"- **{GLOSSARY[k][0]}** — {GLOSSARY[k][1]}" for k in keys)
    with st.expander("What do these numbers mean?"):
        st.markdown(lines)


def render_player_card(player_name, team_name, season):
    """Headshot + name/team/position + PPG/RPG/APG, plus a row of ranked,
    colour-coded advanced metrics (TS%, USG%, ORtg). Photo and every stat fail
    gracefully (fallback box / em dashes) so the card never crashes a tab."""
    try:
        img = cached_photo_bytes(player_name)
    except Exception:
        img = None
    try:
        hs = cached_headline_stats(player_name, team_name, season)
    except Exception:
        hs = {"position": "", "ppg": None, "rpg": None, "apg": None}
    try:
        adv = cached_advanced_stats(player_name, team_name, season)
    except Exception:
        adv = None

    c_photo, c_info = st.columns([1, 2])
    with c_photo:
        if img:
            st.image(img, width=140)
        else:
            st.markdown("<div class='photo-fallback'>No photo</div>",
                        unsafe_allow_html=True)
    with c_info:
        meta = " · ".join([x for x in [team_name, hs.get("position") or ""] if x])

        def fmt(v):
            return "—" if v is None else f"{v:.1f}"

        st.markdown(
            f"<div class='card-name'>{player_name}</div>"
            f"<div class='card-meta'>{meta}</div>"
            f"<div class='card-stats'>"
            f"<span><b>{fmt(hs.get('ppg'))}</b> PPG</span>"
            f"<span><b>{fmt(hs.get('rpg'))}</b> RPG</span>"
            f"<span><b>{fmt(hs.get('apg'))}</b> APG</span></div>",
            unsafe_allow_html=True)

        if adv and adv.get("total_players"):
            total = adv["total_players"]

            def pct(metric):
                v = adv[metric]["value"]
                return "—" if v is None else f"{v * 100:.1f}%"

            def num(metric):
                v = adv[metric]["value"]
                return "—" if v is None else f"{v:.1f}"

            chips = (
                _adv_chip("TS%", pct("ts_pct"), adv["ts_pct"]["rank"], total) +
                _adv_chip("USG%", pct("usg_pct"), adv["usg_pct"]["rank"], total) +
                _adv_chip("ORtg", num("off_rating"), adv["off_rating"]["rank"], total)
            )
            st.markdown(f"<div class='adv-row'>{chips}</div>",
                        unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Page
# -----------------------------------------------------------------------------


# ===== VISUAL HELPERS (from app_ui.py) =====
ACCENT_BAR = '<span class="sec-accent"></span>'


def player_photo_url(player_name: str) -> str:
    try:
        matches = nba_players.find_players_by_full_name(player_name)
        if matches:
            pid = matches[0]["id"]
            return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
    except Exception:
        pass
    return ""


def team_logo_url(team_name: str) -> str:
    try:
        tid = dp.get_team_id(team_name)
        return f"https://cdn.nba.com/logos/nba/{tid}/global/L/logo.svg"
    except Exception:
        return ""


def sec(text):
    st.markdown(f'<div class="sec-header">{ACCENT_BAR}{text}</div>', unsafe_allow_html=True)


def ppp_value(v):
    cls = "ppp-good" if v <= 0.80 else ("ppp-ok" if v <= 1.00 else "ppp-bad")
    return f'<span class="{cls}">{v:.2f}</span>'


def confidence_label(poss):
    if poss >= 80: return "High", SUCCESS
    if poss >= 50: return "Medium", WARN
    return "Low", DANGER


def player_strip(name, role, team_name=""):
    url = player_photo_url(name)
    img = f'<img src="{url}" class="player-strip-img" onerror="this.style.display=\'none\'">'
    st.markdown(f"""<div class="player-strip">
        {img}
        <div>
            <div class="player-strip-role">{role}</div>
            <div class="player-strip-name">{name}</div>
            <div class="player-strip-team">{team_name}</div>
        </div>
    </div>""", unsafe_allow_html=True)


def _fig(w=8, h=5):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(MPLBG)
    ax.set_facecolor(MPLBG)
    for sp in ax.spines.values():
        sp.set_edgecolor(MPLGR)
    ax.tick_params(colors=MPLDM, labelsize=10)
    return fig, ax


def _wrap_fig(fig, insight_text=None):
    if insight_text:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        st.markdown(
            f'<div class="insight-panel"><div class="insight-label">Coaching Insight</div>{insight_text}</div>',
            unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        st.markdown('</div>', unsafe_allow_html=True)


def fig_shot_donut(action_dict):
    if not action_dict:
        return None
    labels  = [k[:30] for k in action_dict.keys()]
    vals    = list(action_dict.values())
    palette = [NBA_BLUE, NBA_RED, SUCCESS, WARN, "#7C3AED", "#0891B2", "#D97706", "#4B5563"][:len(labels)]
    fig, ax = plt.subplots(figsize=(7, 6))
    fig.patch.set_facecolor(MPLBG); ax.set_facecolor(MPLBG)
    wedges, _, autos = ax.pie(
        vals, colors=palette, autopct="%1.0f%%", pctdistance=0.78,
        wedgeprops={"width": 0.52, "edgecolor": MPLBG, "linewidth": 3}, startangle=90)
    for at in autos:
        at.set_color("#fff"); at.set_fontsize(9); at.set_fontweight("bold")
    ax.legend(wedges, labels, loc="lower center", ncol=2, fontsize=9,
              frameon=False, labelcolor=MPLTX, bbox_to_anchor=(0.5, -0.28))
    ax.set_title("Shot Type Mix", color=MPLTX, fontsize=12.5, fontweight="bold", pad=10)
    fig.tight_layout(pad=1.8)
    return fig


def fig_court_side(make_by_area):
    if not make_by_area:
        return None
    buckets = {"Left": [], "Centre": [], "Right": []}
    for zone, pct in make_by_area.items():
        if "Back Court" in zone: continue
        if "Left"  in zone: buckets["Left"].append(pct)
        elif "Right" in zone: buckets["Right"].append(pct)
        else: buckets["Centre"].append(pct)
    avgs    = {k: (sum(v) / len(v) if v else 0) for k, v in buckets.items()}
    colours = [C_SUCCESS if v >= 50 else (WARN if v >= 38 else C_DANGER) for v in avgs.values()]
    fig, ax = _fig(w=6, h=4.5)
    bars = ax.bar(list(avgs.keys()), list(avgs.values()), color=colours, width=0.55, edgecolor="none")
    ax.set_ylim(0, 75)
    ax.axhline(40, color=MPLDM, linewidth=1.4, linestyle="--", alpha=0.5, label="~40% avg")
    ax.legend(fontsize=9, frameon=False, labelcolor=MPLTX)
    ax.set_ylabel("Make %", color=MPLDM, fontsize=10)
    ax.set_title("Make % by Court Side", color=MPLTX, fontsize=12.5, fontweight="bold", pad=12)
    ax.tick_params(axis="x", colors=MPLTX, labelsize=12); ax.tick_params(axis="y", colors=MPLDM, labelsize=10)
    ax.yaxis.grid(True, color=MPLGR, linewidth=0.9); ax.set_axisbelow(True)
    for bar, v in zip(bars, avgs.values()):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 2,
                f"{v:.1f}%", ha="center", fontsize=12, fontweight="800", color=MPLTX)
    fig.tight_layout(pad=1.3)
    return fig


# ===== LAYOUT (from app_ui.py) =====
# =============================================================================
# SIDEBAR
# =============================================================================
ALL_TEAMS = team_names()
SEASONS   = ["2025-26", "2024-25", "2023-24"]

with st.sidebar:
    st.markdown(f"""
    <div class="sb-logo-row">
        <div>
            <div class="sb-app-name">Matchup<span> Advantage</span></div>
            <div class="sb-app-sub">NBA Scouting Platform</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sb-section">Your Team</div>', unsafe_allow_html=True)
    my_team = st.selectbox("My Team", ALL_TEAMS, index=0, key="sb_my_team")

    st.markdown('<div class="sb-section">Opponent</div>', unsafe_allow_html=True)
    opponent = st.selectbox("Opponent", ALL_TEAMS, index=1 if len(ALL_TEAMS) > 1 else 0, key="sb_opponent")

    st.markdown('<div class="sb-section">Season</div>', unsafe_allow_html=True)
    season = st.selectbox("Season", SEASONS, index=0, key="sb_season")

    st.markdown('<div class="sb-section">Scout (Defend)</div>', unsafe_allow_html=True)
    try:
        opp_names = cached_roster_names(opponent, season)
    except Exception:
        opp_names = []
    star = None
    if opp_names:
        try:    opp_top = cached_top_scorer(opponent, season)
        except: opp_top = None
        star = st.selectbox("Opponent Player", opp_names, index=_default_index(opp_names, opp_top), key="sb_star")
    else:
        st.caption(f"No roster data — {opponent} / {season}")

    st.markdown('<div class="sb-section">Attack</div>', unsafe_allow_html=True)
    try:
        my_names = cached_roster_names(my_team, season)
    except Exception:
        my_names = []
    my_player = None
    if my_names:
        try:    my_top = cached_top_scorer(my_team, season)
        except: my_top = None
        my_player = st.selectbox("Your Player", my_names, index=_default_index(my_names, my_top), key="sb_my_player")
    else:
        st.caption(f"No roster data — {my_team} / {season}")

    st.markdown(f"""
    <div class="sb-footer">
        Data: NBA Stats API &nbsp;·&nbsp; {season}<br>
    </div>""", unsafe_allow_html=True)


# =============================================================================
# PAGE HEADER
# =============================================================================
st.markdown(f"""
<div class="ma-header">
    <div>
        <div class="ma-app-title">Matchup <span>Advantage</span></div>
        <div class="ma-app-tagline">NBA Opponent Scouting &amp; Game-Plan Intelligence</div>
    </div>
    <div class="ma-header-matchup">
        <div class="ma-matchup-label">Matchup</div>
        <div class="ma-matchup-val">{my_team} vs {opponent}</div>
    </div>
    <div class="ma-season-badge">{season}</div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# TABS
# =============================================================================
tab_plan, tab_attack, tab_defend, tab_close = st.tabs([
    "Game Plan",
    "Attack",
    "Defend",
    "Close",
])


# =============================================================================
# TAB 1 — GAME PLAN  (app.py full logic)
# =============================================================================
with tab_plan:
    render_team_strip(my_team, opponent, season)

    try:
        opp_star = cached_top_scorer(opponent, season)
    except Exception:
        opp_star = None
    try:
        my_star = cached_top_scorer(my_team, season)
    except Exception:
        my_star = None

    try:
        defend_tk = defend_takeaway(opp_star, opponent, my_team, season) if opp_star else None
    except Exception:
        defend_tk = None

    _assigned = defend_tk.get("assigned") if defend_tk else None

    try:
        mismatch = cached_attack_mismatch(my_team, opponent, season, _assigned)
    except Exception:
        mismatch = None

    if opp_star and my_star:
        try:
            bullets = game_plan_bullets(my_team, opponent, my_star, opp_star, season, defend_tk, mismatch)
            render_game_plan_summary(bullets)
        except Exception:
            pass

    col_def, col_att = st.columns(2, gap="large")

    with col_def:
        if opp_star:
            st.markdown(f"#### Defensive assignment — who guards {opp_star}")
        else:
            st.markdown("#### Defensive assignment")
        if opp_star:
            if defend_tk and defend_tk.get("assigned"):
                render_player_card(defend_tk["assigned"], my_team, season)
            else:
                st.caption(f"No defender to assign from {my_team} yet.")
            if defend_tk:
                render_plan("DEFENSIVE PLAN", defend_tk["sentence"], accent="defend", sub=defend_tk.get("force"))
            st.caption(f"→ Defending {opp_star}. See the Defend tab for the full breakdown.")
        else:
            st.info(f"Couldn't load {opponent}'s top scorer.")

    with col_att:
        if mismatch:
            st.markdown(f"#### Attacking edge — hunt {mismatch['defender']} with {mismatch['attacker']}")
        else:
            st.markdown("#### Attacking edge")
        if mismatch:
            render_player_card(mismatch["attacker"], my_team, season)
            if mismatch["kind"] == "observed":
                sentence = (
                    f"Hunt {mismatch['defender']} with {mismatch['attacker']} — "
                    f"{mismatch['ppp']:.2f} pts/poss on him (+{mismatch['edge']:.2f} "
                    f"above his {mismatch['attacker_avg']:.2f} average) over "
                    f"{mismatch['poss']:.0f} possessions.")
            else:
                sentence = (
                    f"Hunt {mismatch['defender']} with {mismatch['attacker']} — "
                    f"projected {mismatch['label']} matchup.")
            render_plan("ATTACK PLAN", sentence, accent="attack")
            if my_star and my_star != mismatch["attacker"]:
                st.caption(f"Engine: {my_star} still runs the offence — keep feeding him too.")
            st.caption("→ See the Attack tab for the full breakdown.")
        elif my_star and my_star != _assigned:
            render_player_card(my_star, my_team, season)
            render_plan("ATTACK PLAN",
                        f"No clear matchup edge vs {opponent} — attack through "
                        f"{my_star} (our engine) and take what the defence gives.",
                        accent="attack")
            st.caption("→ See the Attack tab for the full breakdown.")
        else:
            st.caption(f"No distinct attacking edge vs {opponent}'s rotation yet — see the Attack tab.")

    sec(f"Four Factors — {my_team} vs {opponent}")
    st.markdown('<div class="context-note">The four team stats that decide games. Better side highlighted; turnovers are better when lower.</div>', unsafe_allow_html=True)
    try:
        my_ff  = cached_four_factors(my_team, season)
        opp_ff = cached_four_factors(opponent, season)
        render_four_factors(my_team, opponent, my_ff, opp_ff)
    except Exception as err:
        st.caption(f"Four Factors unavailable: {err}")

    render_glossary("overview")


# =============================================================================
# TAB 2 — ATTACK  (app.py full logic + UI.py charts)
# =============================================================================
with tab_attack:
    if not my_player:
        st.markdown(
            f'<div class="empty-state">'
            f'<div class="empty-state-title">No Player Selected</div>'
            f'Select your player in the sidebar to load attack data.</div>',
            unsafe_allow_html=True)
    else:
        player_strip(my_player, "Your Player — Attacker", my_team)

        go_attack = st.button("Show matchup edges", key="attack_go")

        if go_attack:
            with st.spinner(f"Loading attack data for {my_player}…"):
                try:
                    matchups = cached_matchups(my_player, season)
                    opp_abbr = cached_team_abbr(opponent)
                    my_abbr  = cached_team_abbr(my_team)
                except ValueError as err:
                    st.error(f"Couldn't find that player/team: {err}")
                    st.stop()
                except Exception as err:
                    st.error(f"Something went wrong pulling the data: {err}")
                    st.stop()

            vs_opp = matchups[matchups["TEAM"] == opp_abbr].sort_values("PTS_PER_POSS", ascending=False)
            league = matchups[matchups["TEAM"] != opp_abbr].sort_values("PTS_PER_POSS", ascending=False)

            tk = attack_takeaway(my_player, my_team, opponent, season)
            render_plan("ATTACK PLAN", tk["sentence"], accent="attack")

            if tk.get("defender"):
                try:
                    prof = cached_attacker_profile(my_player, my_team, season)
                    dz   = cached_defender_zone_defense(season).get(tk["defender"])
                except Exception:
                    prof, dz = None, None
                if prof and prof.get("total_shots"):
                    ec, _ = st.columns([3, 2])
                    with ec:
                        _wrap_fig(attack_edge_chart(prof, dz, my_player, tk["defender"]),
                                  insight_text=f"{my_player}'s shot volume (left) vs {tk['defender']}'s zone defence (right). Green = defender allows above-average FG% there — exploitable.")

            try:
                positions = cached_position_map(season)
            except Exception:
                positions = {}

            sec(f"vs {opponent}'s defenders")
            source_legend("Best edges first.")
            show_matchup_table(vs_opp, source="actual", positions=positions)

            observed_names = set(vs_opp["DEF_PLAYER_NAME"])
            try:
                proj = cached_projected_vs_roster(my_player, my_team, opponent, season)
            except Exception as err:
                proj = []
                st.caption(f"Projection unavailable: {err}")
            proj = sorted(proj, key=lambda r: r["score"], reverse=True)
            sec(f"Projected edges (other {opponent} defenders)")
            st.markdown('<div class="context-note">Estimated from each player\'s season profile when they haven\'t directly faced off. Treat as a guide, not a certainty.</div>', unsafe_allow_html=True)
            show_projected_table(proj, exclude_names=observed_names, positions=positions)

            sec("League-wide comparison")
            st.markdown(f'<div class="context-note">All defenders league-wide this season with ≥40 possessions. Top {min(10, len(league))} of {len(league)} shown.</div>', unsafe_allow_html=True)
            show_matchup_table(league, source="actual", positions=positions, limit=10)

            # Shot charts
            try:
                atk_shots = cached_shots(my_player, my_team, season)
                atk_sum   = cached_summary(my_player, my_team, season)
            except Exception:
                atk_shots = None
                atk_sum   = None

            if atk_shots is not None and not atk_shots.empty:
                if atk_sum:
                    sec("Shooting Tendencies")
                    t1, t2 = st.columns(2, gap="medium")
                    with t1:
                        f = fig_shot_donut(atk_sum["action_type_pct"])
                        if f: _wrap_fig(f)
                    with t2:
                        f = fig_court_side(atk_sum["make_pct_by_area"])
                        if f: _wrap_fig(f)

        render_glossary("attack")


# =============================================================================
# TAB 3 — DEFEND  (app.py full logic + all charts)
# =============================================================================
with tab_defend:
    if not star:
        st.markdown(
            f'<div class="empty-state">'
            f'<div class="empty-state-title">No Scout Target Selected</div>'
            f'Select an opponent player in the sidebar to load scouting data.</div>',
            unsafe_allow_html=True)
    else:
        player_strip(star, "Scouting Target", opponent)
        render_player_card(star, opponent, season)

        go_defend = st.button("Generate scouting report", key="defend_go")

        if go_defend:
            with st.spinner(f"Scouting {star}…"):
                try:
                    def_mu_raw = cached_matchups(star, season)
                    def_sum    = cached_summary(star, opponent, season)
                    my_abbr    = cached_team_abbr(my_team)
                    opp_abbr   = cached_team_abbr(opponent)
                    def_shots  = cached_shots(star, opponent, season)
                except ValueError as err:
                    st.error(f"Couldn't find that player/team: {err}")
                    st.stop()
                except Exception as err:
                    st.error(f"Something went wrong: {err}")
                    st.stop()

            roster_def = def_mu_raw[def_mu_raw["TEAM"] == my_abbr].sort_values("PTS_PER_POSS", ascending=True).copy()
            league_def = def_mu_raw[def_mu_raw["TEAM"] != my_abbr].sort_values("PTS_PER_POSS", ascending=True).copy()

            tk = defend_takeaway(star, opponent, my_team, season)
            render_plan("DEFENSIVE PLAN", tk["sentence"], accent="defend", sub=tk.get("force"))

            if tk.get("force") and not def_shots.empty:
                area = lowest_make_area_weighted(def_shots)
                rec  = area[0] if area else None
                fig  = force_direction_chart(def_shots, rec)
                if fig is not None:
                    fc, _ = st.columns([3, 4])
                    with fc:
                        _wrap_fig(fig, insight_text="Make% and attempt volume by court side. Red bar = the cold zone to force him to.")

            # Scouting summary
            if def_shots.empty:
                st.warning(f"No shot data for {star} on {opponent} in {season}.")
            else:
                sec("Scouting Summary")
                m1, m2 = st.columns(2)
                m1.metric("Total shots", def_sum["total_shots"])
                m2.metric("Avg shot distance", f'{def_sum["avg_shot_distance"]} ft')

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**Top action types (% of shots)**")
                    st.table({"%": _pct_dict(def_sum["action_type_pct"])})
                with c2:
                    st.markdown("**Make % by zone**")
                    st.table({"Make %": _pct_dict(def_sum["make_pct_by_zone"])})
                with c3:
                    st.markdown("**Make % by area**")
                    st.table({"Make %": _pct_dict(def_sum["make_pct_by_area"])})

                sec("Shot Chart & Matchup Radar")
                st.markdown('<div class="context-note">Left: hex size = shot volume, colour = make% vs league avg (green = hot, red = cold). Right: league percentile (0-100) for the star vs your assigned defender — further out = better.</div>', unsafe_allow_html=True)
                sr1, sr2 = st.columns(2, gap="large")
                with sr1:
                    try:
                        league_avgs = cached_league_shot_avgs(star, opponent, season)
                        _wrap_fig(hot_cold_shot_chart(def_shots, league_avgs))
                    except Exception:
                        _wrap_fig(shot_chart_figure(def_shots))
                with sr2:
                    if tk and tk.get("assigned"):
                        try:
                            _wrap_fig(comparison_radar(star, opponent, tk["assigned"], my_team, season))
                        except Exception as err:
                            st.caption(f"Radar unavailable: {err}")
                    else:
                        st.caption("No assigned defender to compare.")

                sec("Shooting Tendencies")
                t1, t2 = st.columns(2, gap="medium")
                with t1:
                    f = fig_shot_donut(def_sum["action_type_pct"])
                    if f: _wrap_fig(f)
                with t2:
                    f = fig_court_side(def_sum["make_pct_by_area"])
                    if f: _wrap_fig(f)

            # My roster
            sec(f"Who Can Guard {star} — Your Roster ({my_team})")
            source_legend("Toughest matchups first.")
            show_matchup_table(roster_def, source="actual")

            observed_names = set(roster_def["DEF_PLAYER_NAME"])
            try:
                projected = cached_best_defenders_projected(star, opponent, my_team, season)
            except Exception as err:
                projected = []
                st.caption(f"Projection unavailable: {err}")
            sec("Projected matchups (roster players he hasn't faced enough)")
            st.markdown('<div class="context-note">Estimated from season profiles. Treat as a guide, not a certainty.</div>', unsafe_allow_html=True)
            show_projected_table(projected, exclude_names=observed_names, reason_key="reason_defend")

            sec("League-wide (for context)")
            st.markdown('<div class="context-note">Everyone else who guarded him, toughest first.</div>', unsafe_allow_html=True)
            show_matchup_table(league_def, source="actual")

        render_glossary("defend")


# =============================================================================
# TAB 4 — CLOSE  (full app.py clutch logic + UI.py styling)
# =============================================================================
with tab_close:
    st.markdown(f"#### {opponent}'s clutch threats")

    try:
        clutch_data = cached_clutch_stats(opponent, season)
    except Exception as err:
        clutch_data = {"players": [], "league_avg_pts": None}
        st.caption(f"Clutch stats unavailable: {err}")

    players    = clutch_data.get("players", [])
    league_avg = clutch_data.get("league_avg_pts")

    if not players:
        st.markdown('<div class="context-note">Clutch = the last 5 minutes of a game with the score within 5 points (the NBA\'s standard definition).</div>', unsafe_allow_html=True)
        st.info(f"No clutch data for {opponent} in {season} yet.")
    else:
        names = [p["player"] for p in players]
        lead  = f"{names[0]} and {names[1]}" if len(names) >= 2 else names[0]
        render_plan("CLOSING THREATS",
                    f"Plan your final-possession defence around {lead} — they take "
                    f"the most clutch shots for {opponent}.",
                    accent="defend")
        st.markdown(
            f'<div class="context-note">Clutch = the last 5 minutes of a game within 5 points. '
            f'Ordered by total clutch scoring. League average: '
            f'{league_avg if league_avg is not None else "—"} clutch pts/game.</div>',
            unsafe_allow_html=True)

        # Table
        rows = []
        for c in players:
            gp    = "—" if c["gp"]    is None else f"{c['gp']}"
            pts   = "—" if c["pts"]   is None else f"{c['pts']:.1f}"
            fg    = "—" if c["fg_pct"] is None else f"{c['fg_pct'] * 100:.1f}%"
            usg   = "—" if c["usg"]   is None else f"{c['usg'] * 100:.1f}%"
            share = "—" if c.get("clutch_share") is None else f"{c['clutch_share']:.1f}%"
            if c["pts"] is not None and league_avg is not None:
                d      = c["pts"] - league_avg
                colour = SUCCESS if d >= 0.5 else (DANGER if d <= -0.5 else TEXT3)
                sign   = "+" if d >= 0 else "−"
                vs_lg  = f"<span style='color:{colour}'>{sign}{abs(d):.1f}</span>"
            else:
                vs_lg = "—"
            rows.append([c["player"], gp, pts, vs_lg, share, fg, usg])
        _html_table(["Player", "Clutch GP", "Clutch PTS/G", "vs league", "% of his pts", "Clutch FG%", "Clutch USG%"], rows)

        # Clutch scoring bar chart
        sec("Clutch scoring (pts / game)")
        bar_colour = TEAM_COLORS.get(opponent, NBA_BLUE)
        scored = [p for p in players if p["pts"] is not None]
        peak   = max((p["pts"] for p in scored), default=0) or 1
        bars   = ""
        for p in scored:
            width = max(3, p["pts"] / peak * 100)
            bars += (f"<div class='cl-row'><span class='cl-name'>{p['player']}</span>"
                     f"<div class='cl-track'><div class='cl-fill' style='width:"
                     f"{width:.0f}%; background:{bar_colour}'></div></div>"
                     f"<span class='cl-val'>{p['pts']:.1f}</span></div>")
        st.markdown(f"<div class='cl-chart'>{bars}</div>", unsafe_allow_html=True)

        # Clutch shot profile for top player
        top = players[0]
        sec(f"How {top['player']} scores late")
        try:
            prof = cached_clutch_shot_profile(top["player"], opponent, season)
        except Exception as err:
            prof = {"buckets": {}, "attempts": 0, "dominant": None, "proxy": ""}
            st.caption(f"Clutch shot profile unavailable: {err}")

        if not prof.get("buckets"):
            n = prof.get("attempts", 0)
            if n > 0:
                st.caption(f"Only {n} late-game shots for {top['player']} — too thin to break down.")
            else:
                st.caption(f"No clutch shot data available for {top['player']}.")
        else:
            phrase = CLUTCH_READ.get(prof["dominant"], prof["dominant"])
            st.markdown(f"In the clutch, **{top['player']}** is a **{phrase}** "
                        "threat — defend accordingly.")
            peak2  = max(prof["buckets"].values()) or 1
            sbars  = ""
            for i, (b, share) in enumerate(prof["buckets"].items()):
                colour = bar_colour if i == 0 else "#8090A8"
                w      = max(3, share / peak2 * 100)
                sbars += (f"<div class='cl-row'><span class='cl-name'>{b}</span>"
                          f"<div class='cl-track'><div class='cl-fill' style='width:"
                          f"{w:.0f}%; background:{colour}'></div></div>"
                          f"<span class='cl-val'>{share:.0f}%</span></div>")
            st.markdown(f"<div class='cl-chart'>{sbars}</div>", unsafe_allow_html=True)
            st.caption(f"Share of his late shots by type. Clutch proxy: {prof['proxy']}.")

    render_glossary("close")

