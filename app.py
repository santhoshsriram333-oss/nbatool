# --- Matchup Advantage: Streamlit dashboard (plain, working version) ---
# Function over looks for now — we'll style it later. This just wires the
# data_pipeline functions up to a UI so I can actually click around the data.

import os
import warnings

# nba_api/urllib3 throws a NotOpenSSLWarning on macOS's LibreSSL — harmless,
# but it clutters the console, so silence it before anything imports urllib3.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc
import pandas as pd
import requests
import streamlit as st
from nba_api.stats.static import teams

import data_pipeline as dp


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


@st.cache_data(show_spinner="Finding the matchup to hunt…")
def cached_attack_mismatch(my_team, opponent, season):
    return dp.find_attack_mismatch(my_team, opponent, season)


@st.cache_data(show_spinner=False)
def cached_recommend_defender(star, opponent, my_team, season):
    return dp.recommend_defender(star, opponent, my_team, season)


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


def hot_cold_shot_chart(shots, league_avg_df):
    """Zone-shaded hot/cold chart: each shot coloured by the player's make% in
    its court zone vs the league average there (green = above, red = below).
    Zones with fewer than MIN_ZONE_ATTEMPTS shots are shown neutral grey so a
    tiny sample never paints an extreme colour. Keeps the half-court drawing."""
    import numpy as np

    # League FG% per (zone, area), aggregated over shot-distance ranges.
    la = league_avg_df.groupby(["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA"]).agg(
        fgm=("FGM", "sum"), fga=("FGA", "sum"))
    la["lpct"] = la["fgm"] / la["fga"].where(la["fga"] > 0)
    league_pct = la["lpct"].to_dict()

    # Player make% per zone, and the diff vs league (None if below the floor).
    pg = shots.groupby(["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA"])["SHOT_MADE_FLAG"] \
        .agg(makes="sum", att="count")
    zone_diff = {}
    for key, row in pg.iterrows():
        lp = league_pct.get(key)
        if row["att"] < MIN_ZONE_ATTEMPTS or lp is None or pd.isna(lp):
            zone_diff[key] = None
        else:
            zone_diff[key] = row["makes"] / row["att"] - lp

    keys = list(zip(shots["SHOT_ZONE_BASIC"], shots["SHOT_ZONE_AREA"]))
    diffs = np.array([zone_diff.get(k) if zone_diff.get(k) is not None else np.nan
                      for k in keys], dtype=float)
    xs, ys = shots["LOC_X"].to_numpy(), shots["LOC_Y"].to_numpy()
    neutral = np.isnan(diffs)

    surface = "#1e2125"
    fig, ax = plt.subplots(figsize=(6, 5.6))
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    ax.scatter(xs[neutral], ys[neutral], c="#555a61", s=16, alpha=0.5,
               edgecolors="none", label=f"low sample (<{MIN_ZONE_ATTEMPTS})")
    sc = ax.scatter(xs[~neutral], ys[~neutral], c=diffs[~neutral], cmap="RdYlGn",
                    vmin=-0.12, vmax=0.12, s=28, alpha=0.88, edgecolors="none")

    draw_court(ax, color="#7a8088")
    ax.set_xlim(-250, 250)
    ax.set_ylim(422.5, -47.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")

    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.02,
                        ticks=[-0.12, 0, 0.12])
    cbar.ax.set_yticklabels(["cold", "avg", "hot"])
    cbar.ax.tick_params(colors="#b7bcc2")
    cbar.outline.set_edgecolor("#3a3f45")
    ax.legend(loc="upper right", fontsize=7, framealpha=0.2, labelcolor="#b7bcc2")
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

    surface = "#1e2125"
    fig, ax = plt.subplots(figsize=(5.2, 5.2), subplot_kw={"polar": True})
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    for vals, colour, name in ((star_vals, "#d18a8a", star_name),
                               (def_vals, "#5aa17f", defender_name)):
        ax.plot(angles, vals, color=colour, linewidth=2, label=name)
        ax.fill(angles, vals, color=colour, alpha=0.18)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color="#c4c8cd", fontsize=8)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], color="#7a8088", fontsize=7)
    ax.set_ylim(0, 100)
    ax.spines["polar"].set_color("#3a3f45")
    ax.grid(color="#3a3f45", linewidth=0.6)
    ax.set_title("League percentile (higher = better)", color="#8a9198",
                 fontsize=8, pad=14)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.12), fontsize=8,
              facecolor=surface, edgecolor="#3a3f45", labelcolor="#c4c8cd")
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


def show_matchup_table(df, source="actual"):
    """Render an observed-matchup frame as a styled table with a Source pill on
    every row. Numbers formatted: FG%/3PT% one-decimal %, possessions 1dp,
    pts/poss 2dp."""
    if df.empty:
        st.caption("No defenders in this group.")
        return
    view = df[DISPLAY_COLS].rename(columns=COL_RENAME).copy()
    pill = _source_pill(source)
    headers = ["Source"] + list(view.columns)
    rows = []
    for _, r in view.iterrows():
        rows.append([
            pill,
            r["Defender"], r["Team"],
            f"{r['Possessions guarded']:.1f}",
            f"{r['Points scored']:.0f}",
            f"{r['Points per possession']:.2f}",
            f"{r['FG%'] * 100:.1f}%",
            f"{r['3PT%'] * 100:.1f}%",
        ])
    _html_table(headers, rows)


def show_projected_table(results, exclude_names=None, reason_key="reason"):
    """Render projected matchup dicts as a styled table: Projected pill, a
    colour-coded verdict, edge score, and the reason.

    `reason_key` picks the wording: "reason" (Attack — "he" is my attacker) or
    "reason_defend" (Defend — row is a defender, scouted player is the shooter).
    Players with no usable defensive data are dropped; a small grey line notes
    how many."""
    exclude = exclude_names or set()
    usable = [r for r in results if r["defender"] not in exclude]
    excluded = sum(1 for r in usable if r.get("insufficient"))
    keep = [r for r in usable if not r.get("insufficient")]
    if keep:
        pill = _source_pill("projected")
        rows = []
        for r in keep:
            score = r["score"] if abs(r["score"]) >= 0.005 else 0.0
            rows.append([
                pill, r["defender"], _label_html(r["label"]),
                f"{score:.2f}", r.get(reason_key, r["reason"]),
            ])
        _html_table(["Source", "Defender", "Projection", "Edge score", "Why"], rows)
        st.caption("Edge score = weighted FG% edge, roughly −0.10 to +0.10 "
                   "(positive favours the scorer). Within ±0.01 is Neutral; "
                   "±0.03 a modest edge, ±0.08+ a strong one.")
    else:
        st.caption("No projected matchups to show.")
    if excluded:
        st.caption(f"{excluded} player(s) excluded — insufficient defensive data.")


def lowest_make_area_weighted(shots):
    """Coldest side for the attacker, weighting make% by shot VOLUME.

    Buckets SHOT_ZONE_AREA into left / right / down the middle and computes each
    bucket's make% as total makes / total attempts (so a high-volume sub-zone
    dominates its bucket, instead of a flat average of percentages). Backcourt
    heaves are dropped. Returns (label, make_pct, attempts) or None."""
    df = shots.copy()

    def bucket(zone):
        if "Back Court" in zone:
            return None
        if "Left" in zone:
            return "left"
        if "Right" in zone:
            return "right"
        return "down the middle"

    df["_bucket"] = df["SHOT_ZONE_AREA"].map(bucket)
    df = df[df["_bucket"].notna()]
    if df.empty:
        return None

    grp = df.groupby("_bucket")["SHOT_MADE_FLAG"].agg(makes="sum", attempts="count")
    grp = grp[grp["attempts"] > 0]
    if grp.empty:
        return None
    grp["make_pct"] = grp["makes"] / grp["attempts"] * 100
    grp = grp.sort_values("make_pct")
    coldest = grp.iloc[0]
    return grp.index[0], round(float(coldest["make_pct"]), 1), int(coldest["attempts"])


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
    out = {"sentence": None, "kind": "none"}
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
                out["sentence"] = (f"{head} Projected best edge: {p['defender']} "
                                   f"({p['label']}).")
            else:
                out["kind"] = "observed"
                out["sentence"] = head
    else:
        # No head-to-head data at all — fall back to projections, but only call
        # it an "attack" if the best projection is actually favourable.
        p = _top_projected_edge(my_player, my_team, opponent, season)
        if p and p["score"] > 0:
            out["kind"] = "projected"
            out["sentence"] = (f"Attack {p['defender']} — projected best edge vs "
                               f"{opponent} ({p['label']}).")
        elif p:
            out["kind"] = "projected"
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


GREEN, GREY, RED = "#63b384", "#9aa0a6", "#d18a8a"


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
    "close": ["clutch_def", "clutch_gp", "clutch_pts", "clutch_fg", "clutch_usg"],
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
st.set_page_config(page_title="Matchup Advantage", layout="wide")
st.markdown(TABLE_CSS, unsafe_allow_html=True)


def load_css(filename):
    """Inject an external stylesheet if present (graceful if it's missing)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    try:
        with open(path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass


load_css("style.css")
st.title("Matchup Advantage — NBA Opponent Scouting")

ALL_TEAMS = team_names()
SEASONS = ["2025-26", "2024-25", "2023-24"]

col_team, col_opp, col_season = st.columns(3)
with col_team:
    my_team = st.selectbox("My Team", ALL_TEAMS, index=0)
with col_opp:
    opponent = st.selectbox("Opponent", ALL_TEAMS, index=1)
with col_season:
    season = st.selectbox("Season", SEASONS, index=0)

tab_overview, tab_attack, tab_defend, tab_close = st.tabs(
    ["Game Plan", "Attack", "Defend", "Close"])


# -----------------------------------------------------------------------------
# GAME PLAN tab — the at-a-glance front door.
# -----------------------------------------------------------------------------
with tab_overview:
    st.subheader("Game Plan")
    render_team_strip(my_team, opponent, season)

    try:
        opp_star = cached_top_scorer(opponent, season)
    except Exception:
        opp_star = None
    try:
        my_star = cached_top_scorer(my_team, season)
    except Exception:
        my_star = None

    # Compute the takeaways once, up front — reused by the summary and the cards.
    # Defence centres on THEIR star; offence hunts the best MATCHUP (not just our
    # top scorer), so we find the strongest mismatch across our whole roster.
    try:
        defend_tk = defend_takeaway(opp_star, opponent, my_team, season) \
            if opp_star else None
    except Exception:
        defend_tk = None
    try:
        mismatch = cached_attack_mismatch(my_team, opponent, season)
    except Exception:
        mismatch = None

    # --- Game plan at a glance (auto-summary) ---
    if opp_star and my_star:
        try:
            bullets = game_plan_bullets(my_team, opponent, my_star, opp_star,
                                        season, defend_tk, mismatch)
            render_game_plan_summary(bullets)
        except Exception:
            pass

    col_def, col_att = st.columns(2)

    with col_def:
        if opp_star:
            st.markdown(f"#### Our defensive assignment — who guards {opp_star}")
        else:
            st.markdown("#### Our defensive assignment")
        if opp_star:
            # Card shows OUR assigned defender (a my-team player), not their star.
            if defend_tk and defend_tk.get("assigned"):
                render_player_card(defend_tk["assigned"], my_team, season)
            else:
                st.caption(f"No defender to assign from {my_team} yet.")
            if defend_tk:
                render_plan("DEFENSIVE PLAN", defend_tk["sentence"],
                            accent="defend", sub=defend_tk.get("force"))
            st.caption(f"→ Defending {opp_star}. See the Defend tab for the "
                       "full breakdown.")
        else:
            st.info(f"Couldn't load {opponent}'s top scorer.")

    with col_att:
        if mismatch:
            st.markdown("#### Our attacking edge — who to hunt "
                        f"{mismatch['defender']} with")
        else:
            st.markdown("#### Our attacking edge")
        if mismatch:
            # Feature OUR hunter (the player with the real edge), and name the
            # weak-link defender to attack in the plan text.
            render_player_card(mismatch["attacker"], my_team, season)
            if mismatch["kind"] == "observed":
                sentence = (
                    f"Hunt {mismatch['defender']} with {mismatch['attacker']} — "
                    f"{mismatch['ppp']:.2f} pts/poss on him (+{mismatch['edge']:.2f} "
                    f"above his {mismatch['attacker_avg']:.2f} average) over "
                    f"{mismatch['poss']:.0f} possessions. Get him switched onto "
                    f"{mismatch['defender']}.")
            else:
                sentence = (
                    f"Hunt {mismatch['defender']} with {mismatch['attacker']} — "
                    f"projected {mismatch['label']} matchup. Get him switched onto "
                    f"{mismatch['defender']}.")
            render_plan("ATTACK PLAN", sentence, accent="attack")
            if my_star and my_star != mismatch["attacker"]:
                st.caption(f"Engine: {my_star} still runs the offence — keep "
                           "feeding him too.")
            st.caption("→ See the Attack tab for the full breakdown.")
        elif my_star:
            # No clear seam in the opponent's rotation — attack through our engine.
            render_player_card(my_star, my_team, season)
            render_plan("ATTACK PLAN",
                        f"No clear matchup edge vs {opponent} — attack through "
                        f"{my_star} (our engine) and take what the defence gives.",
                        accent="attack")
            st.caption("→ See the Attack tab for the full breakdown.")
        else:
            st.info(f"Couldn't load {my_team}'s roster.")

    # --- Four Factors team comparison ---
    st.markdown(f"#### Four Factors — {my_team} vs {opponent}")
    st.caption("The four team stats that decide games. The better side of each "
               "is highlighted; turnovers are better when lower.")
    try:
        my_ff = cached_four_factors(my_team, season)
        opp_ff = cached_four_factors(opponent, season)
        render_four_factors(my_team, opponent, my_ff, opp_ff)
    except Exception as err:
        st.caption(f"Four Factors unavailable: {err}")

    render_glossary("overview")


# -----------------------------------------------------------------------------
# DEFEND tab — the priority. Scout the opponent's star.
# -----------------------------------------------------------------------------
with tab_defend:
    st.subheader(f"Defend — scouting an {opponent} player")
    st.caption("Pick the opponent player to scout (defaults to their top "
               f"scorer); we'll show who on {my_team} can guard him.")

    star = roster_dropdown(opponent, season, "Opponent player to scout",
                           key="defend_player")
    # Live card — reflects the dropdown immediately, before the report is run.
    if star:
        render_player_card(star, opponent, season)
    go = st.button("Generate scouting report", key="defend_go")

    if go:
        if not star:
            st.info("Select a player first, then click Generate.")
        else:
            try:
                summary = cached_summary(star, opponent, season)
                shots = cached_shots(star, opponent, season)
                matchups = cached_matchups(star, season)
                my_abbr = cached_team_abbr(my_team)
            except ValueError as err:
                # Raised by get_player_id / get_team_id when a name can't be resolved.
                st.error(f"Couldn't find that player/team: {err}. "
                         "Check the spelling, or confirm he played for "
                         f"{opponent} in {season}.")
            except Exception as err:
                st.error(f"Something went wrong pulling the data: {err}")
            else:
                # Split defenders into "my roster" vs everyone else, toughest first.
                roster_def = matchups[matchups["TEAM"] == my_abbr] \
                    .sort_values("PTS_PER_POSS", ascending=True)
                league_def = matchups[matchups["TEAM"] != my_abbr] \
                    .sort_values("PTS_PER_POSS", ascending=True)

                # --- Takeaway headline (shared logic with the Game Plan tab) ---
                tk = defend_takeaway(star, opponent, my_team, season)
                render_plan("DEFENSIVE PLAN", tk["sentence"], accent="defend",
                            sub=tk.get("force"))

                # --- Scouting summary + shot chart ---
                if shots.empty:
                    st.warning(f"No shot data for {star} on {opponent} in {season}. "
                               "Is he on this team this season?")
                else:
                    st.markdown("### Scouting summary")
                    m1, m2 = st.columns(2)
                    m1.metric("Total shots", summary["total_shots"])
                    m2.metric("Avg shot distance", f'{summary["avg_shot_distance"]} ft')

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown("**Top action types (% of shots)**")
                        st.table({"%": _pct_dict(summary["action_type_pct"])})
                    with c2:
                        st.markdown("**Make % by zone**")
                        st.table({"Make %": _pct_dict(summary["make_pct_by_zone"])})
                    with c3:
                        st.markdown("**Make % by area**")
                        st.table({"Make %": _pct_dict(summary["make_pct_by_area"])})

                    st.markdown("### Shot chart")
                    st.caption("Each shot shaded by his make% in that zone vs the "
                               "league average there — green = hot, red = cold.")
                    chart_col, _ = st.columns([2, 1])
                    with chart_col:
                        try:
                            league_avgs = cached_league_shot_avgs(star, opponent, season)
                            st.pyplot(hot_cold_shot_chart(shots, league_avgs))
                        except Exception:
                            # Fall back to the plain made/missed chart if league
                            # averages are unavailable.
                            st.pyplot(shot_chart_figure(shots))

                # --- Matchup radar: the star vs our assigned defender ---
                if tk and tk.get("assigned"):
                    st.markdown(f"### Matchup radar — {star} vs {tk['assigned']}")
                    st.caption("Each axis is a league percentile (0–100) for that "
                               "metric; further out = better. Defensive rating is "
                               "ranked so a strong defender scores high.")
                    radar_col, _ = st.columns([2, 1])
                    with radar_col:
                        try:
                            st.pyplot(comparison_radar(star, opponent,
                                                       tk["assigned"], my_team, season))
                        except Exception as err:
                            st.caption(f"Radar unavailable: {err}")

                # --- Who to assign: my roster first, then league context ---
                st.markdown(f"### From your roster ({my_team})")
                source_legend("Toughest matchups first.")
                show_matchup_table(roster_def, source="actual")

                # Projected supplement — fills the gap for roster players who
                # haven't logged enough head-to-head possessions vs this star.
                observed_names = set(roster_def["DEF_PLAYER_NAME"])
                try:
                    projected = cached_best_defenders_projected(
                        star, opponent, my_team, season)
                except Exception as err:
                    projected = []
                    st.caption(f"Projection unavailable: {err}")
                st.markdown("#### Projected matchups "
                            "(roster players he hasn't faced enough)")
                st.caption("Projected matchups estimate the battle from each "
                           "player's season profile when they haven't directly "
                           "faced off. Treat as a guide, not a certainty.")
                show_projected_table(projected, exclude_names=observed_names,
                                     reason_key="reason_defend")

                st.markdown("### League-wide (for context)")
                st.caption("Everyone else who guarded him, toughest first.")
                show_matchup_table(league_def, source="actual")

    render_glossary("defend")


# -----------------------------------------------------------------------------
# ATTACK tab — find my player's best matchup edges.
# -----------------------------------------------------------------------------
with tab_attack:
    st.subheader(f"Attack — {my_team} edges vs {opponent}")
    st.caption("Pick one of my players (defaults to our top scorer); we'll rank "
               f"the matchups he scored best against, {opponent} first.")

    my_player = roster_dropdown(my_team, season, "My player", key="attack_player")
    # Live card — reflects the dropdown immediately, before the edges are run.
    if my_player:
        render_player_card(my_player, my_team, season)
    go_attack = st.button("Show matchup edges", key="attack_go")

    if go_attack:
        if not my_player:
            st.info("Select a player first, then click the button.")
        else:
            try:
                matchups = cached_matchups(my_player, season)
                opp_abbr = cached_team_abbr(opponent)
            except ValueError as err:
                st.error(f"Couldn't find that player/team: {err}. Check the spelling.")
            except Exception as err:
                st.error(f"Something went wrong pulling the data: {err}")
            else:
                # Best edges first; opponent's defenders split out from the rest.
                # (Filtering/sorting works even if matchups is empty.)
                vs_opp = matchups[matchups["TEAM"] == opp_abbr] \
                    .sort_values("PTS_PER_POSS", ascending=False)
                league = matchups[matchups["TEAM"] != opp_abbr] \
                    .sort_values("PTS_PER_POSS", ascending=False)

                # --- Takeaway headline (shared logic with the Game Plan tab) ---
                tk = attack_takeaway(my_player, my_team, opponent, season)
                render_plan("ATTACK PLAN", tk["sentence"], accent="attack")

                # --- Observed matchups vs the opponent ---
                st.markdown(f"### vs {opponent}'s defenders")
                source_legend("Best edges first.")
                show_matchup_table(vs_opp, source="actual")

                # --- Projected edges vs opponent defenders he hasn't faced enough ---
                observed_names = set(vs_opp["DEF_PLAYER_NAME"])
                try:
                    proj = cached_projected_vs_roster(my_player, my_team,
                                                      opponent, season)
                except Exception as err:
                    proj = []
                    st.caption(f"_Projection unavailable: {err}_")
                proj = sorted(proj, key=lambda r: r["score"], reverse=True)  # favourable first
                st.markdown(f"#### Projected edges (other {opponent} defenders)")
                st.caption("Projected matchups estimate the battle from each "
                           "player's season profile when they haven't directly "
                           "faced off. Treat as a guide, not a certainty.")
                show_projected_table(proj, exclude_names=observed_names)

                st.markdown("### League-wide (for context)")
                st.caption("Every other defender he faced, best edges first.")
                show_matchup_table(league, source="actual")

    render_glossary("attack")


# -----------------------------------------------------------------------------
# CLOSE tab — placeholder (no metrics shown, so no glossary).
# -----------------------------------------------------------------------------
with tab_close:
    st.subheader(f"Close — {opponent}'s clutch threats")
    st.caption("Clutch = the last 5 minutes of a game with the score within 5 "
               "points (the NBA's standard definition). These are the players "
               f"{opponent} feeds late — plan your final-possession defence "
               "around them.")
    try:
        clutch = cached_clutch_stats(opponent, season)
    except Exception as err:
        clutch = []
        st.caption(f"Clutch stats unavailable: {err}")

    if not clutch:
        st.info(f"No clutch data for {opponent} in {season} yet.")
    else:
        rows = []
        for c in clutch:
            fg = "—" if c["fg_pct"] is None else f"{c['fg_pct'] * 100:.1f}%"
            usg = "—" if c["usg"] is None else f"{c['usg'] * 100:.1f}%"
            pts = "—" if c["pts"] is None else f"{c['pts']:.1f}"
            gp = "—" if c["gp"] is None else f"{c['gp']}"
            rows.append([c["player"], gp, pts, fg, usg])
        _html_table(["Player", "Clutch GP", "Clutch PTS/G", "Clutch FG%",
                     "Clutch USG%"], rows)
        st.caption("Ordered by total clutch scoring (games × points). Higher "
                   "usage = more of the offence runs through him late.")

    render_glossary("close")
