# --- Matchup Advantage: Streamlit dashboard (plain, working version) ---
# Function over looks for now — we'll style it later. This just wires the
# data_pipeline functions up to a UI so I can actually click around the data.

import warnings

# nba_api/urllib3 throws a NotOpenSSLWarning on macOS's LibreSSL — harmless,
# but it clutters the console, so silence it before anything imports urllib3.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc
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
    return dp.get_matchups(player_name, season)


@st.cache_data(show_spinner="Pulling shot chart…")
def cached_shots(player_name, team_name, season):
    return dp.get_shots(player_name, team_name, season)


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


# -----------------------------------------------------------------------------
# Page
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Matchup Advantage", layout="wide")
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

tab_attack, tab_defend, tab_close = st.tabs(["Attack", "Defend", "Close"])


# -----------------------------------------------------------------------------
# DEFEND tab — the priority. Scout the opponent's star.
# -----------------------------------------------------------------------------
with tab_defend:
    st.subheader(f"Defend — scouting an {opponent} player")
    st.caption("Pick the opponent player to scout (defaults to their top "
               "scorer); we'll show how to defend him.")

    star = roster_dropdown(opponent, season, "Opponent player to scout",
                           key="defend_player")
    go = st.button("Generate scouting report", key="defend_go")

    if go:
        if not star:
            st.info("Select a player first, then click Generate.")
        else:
            try:
                summary = cached_summary(star, opponent, season)
                shots = cached_shots(star, opponent, season)
                matchups = cached_matchups(star, season)
            except ValueError as err:
                # Raised by get_player_id / get_team_id when a name can't be resolved.
                st.error(f"Couldn't find that player/team: {err}. "
                         "Check the spelling, or confirm he played for "
                         f"{opponent} in {season}.")
            except Exception as err:
                st.error(f"Something went wrong pulling the data: {err}")
            else:
                if shots.empty:
                    st.warning(f"No shot data for {star} on {opponent} in {season}. "
                               "Is he on this team this season?")
                else:
                    # --- 1. Scouting summary as metric cards + tables ---
                    st.markdown("### Scouting summary")
                    m1, m2 = st.columns(2)
                    m1.metric("Total shots", summary["total_shots"])
                    m2.metric("Avg shot distance", f'{summary["avg_shot_distance"]} ft')

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown("**Top action types (% of shots)**")
                        st.table({"%": summary["action_type_pct"]})
                    with c2:
                        st.markdown("**Make % by zone**")
                        st.table({"Make %": summary["make_pct_by_zone"]})
                    with c3:
                        st.markdown("**Make % by area**")
                        st.table({"Make %": summary["make_pct_by_area"]})

                    # --- 2. Shot chart ---
                    st.markdown("### Shot chart")
                    chart_col, _ = st.columns([2, 1])
                    with chart_col:
                        st.pyplot(shot_chart_figure(shots))

                    # --- 3. Matchups, framed as who to assign on defense ---
                    st.markdown("### Best defenders to assign")
                    st.caption("Toughest matchups first — these defenders held "
                               "him to the fewest points per possession.")
                    toughest_first = matchups.sort_values("PTS_PER_POSS",
                                                          ascending=True)
                    st.dataframe(toughest_first, use_container_width=True,
                                 hide_index=True)


# -----------------------------------------------------------------------------
# ATTACK tab — find my player's best matchup edges.
# -----------------------------------------------------------------------------
with tab_attack:
    st.subheader(f"Attack — find a {my_team} player's edges")
    st.caption("Pick one of my players (defaults to our top scorer); we'll rank "
               "the matchups he scored best against.")

    my_player = roster_dropdown(my_team, season, "My player", key="attack_player")
    go_attack = st.button("Show matchup edges", key="attack_go")

    if go_attack:
        if not my_player:
            st.info("Select a player first, then click the button.")
        else:
            try:
                matchups = cached_matchups(my_player, season)
            except ValueError as err:
                st.error(f"Couldn't find that player: {err}. Check the spelling.")
            except Exception as err:
                st.error(f"Something went wrong pulling the data: {err}")
            else:
                if matchups.empty:
                    st.warning(f"No matchup data for {my_player} in {season}.")
                else:
                    st.markdown("### Best matchup edges")
                    st.caption("Highest points-per-possession first — attack "
                               "these matchups.")
                    best_first = matchups.sort_values("PTS_PER_POSS",
                                                      ascending=False)
                    st.dataframe(best_first, use_container_width=True,
                                 hide_index=True)


# -----------------------------------------------------------------------------
# CLOSE tab — placeholder.
# -----------------------------------------------------------------------------
with tab_close:
    st.subheader("Close")
    st.info("Phase 2 — clutch decisions (coming soon)")
