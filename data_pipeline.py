# --- Matchup Advantage: data pipeline ---
# This is the main data layer for my NBA scouting tool. It started as
# sanity_check.py, but I pulled the useful bits into proper functions here and
# added caching + retries so the live demo doesn't fall over.

import os
import time
import functools

import pandas as pd
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    leagueseasonmatchups,
    shotchartdetail,
    commonteamroster,
    leaguedashplayerstats,
    leaguedashptdefend,
    leaguedashteamstats,
    leaguedashplayerclutch,
)

# only keep matchups with 40+ possessions — anything smaller gave really noisy,
# misleading per-possession numbers 
POSS_FLOOR = 40
TIMEOUT = 60

# I save every API pull to disk here. stats.nba.com is slow and sometimes times
# out, so once I've fetched something I never want to hit the network for it
# again — repeat runs (and the demo) just read the cached file.
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# --- Projection model (tune here) --------------------------------------------
# When two players never directly faced off, I estimate the matchup by overlaying
# where the attacker shoots against how well the defender holds shooters in those
# same zones. The three zones map to LeagueDashPtDefend's defense categories.
#
# PLUSMINUS in that endpoint = defender's allowed FG% minus the shooter's normal
# FG%. POSITIVE means the defender gives up MORE than usual -> good for the
# attacker. So a higher weighted score = more favourable for the attacker.
PROJ_FAVOURABLE_CUTOFF = 0.010   # weighted score >= this -> "Favourable"
PROJ_TOUGH_CUTOFF = -0.010       # weighted score <= this -> "Tough"

# Sample-size floor: a defender needs to have defended at least this many shots
# in a zone for that zone's number to be trustworthy. Below it, a single hot/cold
# game swings the plus-minus wildly (a deep reserve who defended 6 shots can post
# a -0.40 that's pure noise), so we drop the zone instead of letting it through.
MIN_DEFENDED_FGA = 50

# zone key -> (LeagueDashPtDefend category, allowed-FG% column, attempts column)
ZONE_DEFENSE_SPEC = {
    "at_rim":    {"category": "Less Than 6Ft",  "dfg_col": "LT_06_PCT", "fga_col": "FGA_LT_06"},
    "short_mid": {"category": "Less Than 10Ft", "dfg_col": "LT_10_PCT", "fga_col": "FGA_LT_10"},
    "three":     {"category": "3 Pointers",     "dfg_col": "FG3_PCT",   "fga_col": "FG3A"},
}
ZONE_LABELS = {
    "at_rim": "at the rim",
    "short_mid": "in the short-mid range",
    "three": "from three",
}
# Defend-tab verdict: the label is from the ATTACKER's point of view (Favourable
# = good for the shooter), so for the defending team we flip it into "us" terms.
DEFEND_VERDICT = {
    "Favourable": "hard for us to stop",
    "Neutral": "an even matchup",
    "Tough": "a matchup in our favour",
}


# ---------------------------------------------------------------------------
# Caching + retry helpers
# ---------------------------------------------------------------------------
def _cache_path(key):
    # turn the key into a filename that's safe on disk ,just swap anything
    # that isn't a letter/number for an underscore.
    safe = "".join(c if c.isalnum() else "_" for c in key)
    return os.path.join(CACHE_DIR, safe + ".pkl")


def cached_pull(key, fetch_fn):
    """If I've already pulled this data, load it from disk. Otherwise go fetch
    it, save it, and hand it back.

    fetch_fn is just a little no-argument function that does the actual API
    call and returns a DataFrame. i keep that separate so the caching logic
    doesn't care which endpoint it's talking to.
    """
    path = _cache_path(key)
    if os.path.exists(path):
        return pd.read_pickle(path)

    df = _with_retry(fetch_fn)
    df.to_pickle(path)
    return df


def _with_retry(fetch_fn, attempts=2, delay=2):
    # the NBA stats server flakes out fairly often, but usually it works on the
    # second try. So I retry exactly once, enough to ride out a random timeout
    # without hanging forever if the site is genuinely down.
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch_fn()
        except Exception as err:  # nba_api can throw a bunch of different errors, so catch broadly
            last_err = err
            print(f"  [retry] attempt {attempt}/{attempts} failed: {err}")
            if attempt < attempts:
                time.sleep(delay)
    raise last_err


# ---------------------------------------------------------------------------
# Turning names into IDs (this part is all offline — no internet needed)
# ---------------------------------------------------------------------------
# nba_api ships the player/team lists with the package, so I can look these up
# locally. The lru_cache just means a repeated name lookup is basically free.
@functools.lru_cache(maxsize=None)
def get_player_id(name):
    """Take a player's full name and give back their NBA id."""
    matches = players.find_players_by_full_name(name)
    if not matches:
        raise ValueError(f"No player found for name: {name!r}")
    return matches[0]["id"]


@functools.lru_cache(maxsize=None)
def get_team_id(name):
    """Take a team name and give back its NBA id.

    I wanted to be forgiving about how the team is typed, so it'll match the
    full name, nickname, city, or the 3-letter abbreviation (case doesn't
    matter).
    """
    needle = name.strip().lower()
    for t in teams.get_teams():
        candidates = {
            t["full_name"].lower(),
            t["nickname"].lower(),
            t["city"].lower(),
            t["abbreviation"].lower(),
        }
        if needle in candidates:
            return t["id"]
    # if none of those matched exactly, try a looser "is this text somewhere in
    # the full name" check before giving up.
    for t in teams.get_teams():
        if needle in t["full_name"].lower():
            return t["id"]
    raise ValueError(f"No team found for name: {name!r}")


# ---------------------------------------------------------------------------
# Matchup data
# ---------------------------------------------------------------------------
def get_matchups(off_player_name, season):
    """Get who guarded this player and how he did against each defender.

    This pulls the season matchup data, trims it to the columns I care about,
    throws out the tiny-sample defenders, and works out points per possession
    so I can rank matchups by how well he actually scored against each guy.

    # NOTE for Aditi: two things to sanity-check here. (1) the >= 40 possession
    # floor — is 40 the right cutoff, or are we throwing away defenders we'd
    # actually want to see? (2) I sort by PTS_PER_POSS descending so the
    # *easiest* matchups land at the top of the table — confirm that's the
    # order we want for the scouting view (top = attack, bottom = avoid).
    """
    player_id = get_player_id(off_player_name)

    # wrap the actual API call so cached_pull can retry it / cache the result
    def fetch():
        mu = leagueseasonmatchups.LeagueSeasonMatchups(
            off_player_id_nullable=player_id,
            season=season,
            per_mode_simple="Totals",
            timeout=TIMEOUT,
        )
        return mu.get_data_frames()[0]

    df = cached_pull(f"matchups_{player_id}_{season}", fetch)

    keep = ["DEF_PLAYER_NAME", "PARTIAL_POSS", "PLAYER_PTS",
            "MATCHUP_FG_PCT", "MATCHUP_FG3_PCT"]
    clean = df[keep].copy()
    clean = clean[clean["PARTIAL_POSS"] >= POSS_FLOOR]
    # points per possession is the fairest way to compare matchups — raw points
    # just rewards whoever he happened to face the most.
    clean["PTS_PER_POSS"] = (clean["PLAYER_PTS"] / clean["PARTIAL_POSS"]).round(3)
    # sort best-scoring matchups first; reset_index so the row numbers are tidy
    clean = clean.sort_values("PTS_PER_POSS", ascending=False).reset_index(drop=True)
    return clean


# ---------------------------------------------------------------------------
# Shot-chart data
# ---------------------------------------------------------------------------
def get_shots(player_name, team_name, season):
    """Pull every shot this player took for the given team that season.

    The raw shot-chart endpoint returns a ton of columns; I only keep the ones
    I need for the hot/cold map and the tendency stats — where the shot was
    (LOC_X/LOC_Y, the zones, distance), whether it went in, and what kind of
    shot it was.
    """
    player_id = get_player_id(player_name)
    team_id = get_team_id(team_name)

    # same pattern as get_matchups — keep the live call in its own function
    def fetch():
        sc = shotchartdetail.ShotChartDetail(
            team_id=team_id,
            player_id=player_id,
            season_nullable=season,
            season_type_all_star="Regular Season",
            context_measure_simple="FGA",
            timeout=TIMEOUT,
        )
        return sc.get_data_frames()[0]

    df = cached_pull(f"shots_{player_id}_{team_id}_{season}", fetch)

    keep = ["LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "SHOT_TYPE",
            "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "ACTION_TYPE", "SHOT_DISTANCE"]
    return df[keep].copy()


# ---------------------------------------------------------------------------
# Scouting summary
# ---------------------------------------------------------------------------
def scouting_summary(player_name, team_name, season):
    """Boil a player's shot data down into a few scouting takeaways.

    Gives back a dict with the basics (total shots, average distance) plus his
    tendencies: what kinds of shots he likes, and where on the floor he's
    actually making them.

    # NOTE for Aditi: please double-check the percentage math here. The two
    # numbers mean different things and it's easy to mix them up:
    #   - action_type_pct is "share of his shots" (counts that sum toward 100%
    #     across all action types, and I only show the top 5).
    #   - make_pct_by_zone / make_pct_by_area are "how often shots from there
    #     went in" — each one is an independent FG% for that area, so they do
    #     NOT add up to 100%. Want to make sure that distinction is right.
    """
    shots = get_shots(player_name, team_name, season)
    total = len(shots)

    # which shot types he goes to most — normalize=True turns the raw counts
    # into fractions, then I scale to a percent and keep just the top 5.
    action_pct = (
        shots["ACTION_TYPE"].value_counts(normalize=True)
        .mul(100).round(1).head(5)
    )

    # SHOT_MADE_FLAG is 1/0, so taking the mean of it per group is literally the
    # make percentage for that group. Doing it once by basic zone, once by area.
    make_by_zone = (
        shots.groupby("SHOT_ZONE_BASIC")["SHOT_MADE_FLAG"]
        .mean().mul(100).round(1).sort_values(ascending=False)
    )
    make_by_area = (
        shots.groupby("SHOT_ZONE_AREA")["SHOT_MADE_FLAG"]
        .mean().mul(100).round(1).sort_values(ascending=False)
    )

    return {
        "player": player_name,
        "team": team_name,
        "season": season,
        "total_shots": total,
        "avg_shot_distance": round(shots["SHOT_DISTANCE"].mean(), 1),
        "action_type_pct": action_pct.to_dict(),
        "make_pct_by_zone": make_by_zone.to_dict(),
        "make_pct_by_area": make_by_area.to_dict(),
    }


def get_league_shot_averages(player_name, team_name, season):
    """League-average shooting by court zone for the season — the baseline for
    the hot/cold chart. Comes from ShotChartDetail's second frame (the same
    call shape as get_shots), which returns FG% per zone across the whole league.

    Cached by season (the league averages are identical for any player query),
    so it's fetched once per season then read from disk.
    """
    player_id = get_player_id(player_name)
    team_id = get_team_id(team_name)

    def fetch():
        sc = shotchartdetail.ShotChartDetail(
            team_id=team_id,
            player_id=player_id,
            season_nullable=season,
            season_type_all_star="Regular Season",
            context_measure_simple="FGA",
            timeout=TIMEOUT,
        )
        return sc.get_data_frames()[1]

    return cached_pull(f"leagueavg_{season}", fetch)


# ---------------------------------------------------------------------------
# Roster + top scorer
# ---------------------------------------------------------------------------
# The app uses these so the user picks players from dropdowns instead of typing
# names. Both go through cached_pull, so a roster/scoring table is only fetched
# from stats.nba.com once per team+season and then read off disk after that.
def get_roster(team_name, season):
    """Return a team's roster for the season as a DataFrame.

    The handy column for the UI is "PLAYER" (the player's display name).
    """
    team_id = get_team_id(team_name)

    def fetch():
        r = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            season=season,
            timeout=TIMEOUT,
        )
        return r.get_data_frames()[0]

    return cached_pull(f"roster_{team_id}_{season}", fetch)


def get_team_player_scoring(team_name, season):
    """Per-game player stats for everyone who logged minutes for this team.

    I pull this separately from the roster because it's where the points-per-game
    (PTS, in PerGame mode) lives, that's what I use to find the top scorer.
    """
    team_id = get_team_id(team_name)

    def fetch():
        s = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            per_mode_detailed="PerGame",
            team_id_nullable=team_id,
            timeout=TIMEOUT,
        )
        return s.get_data_frames()[0]

    return cached_pull(f"teamscoring_{team_id}_{season}", fetch)


def get_top_scorer(team_name, season):
    """Name of the team's highest points-per-game player *on the current roster*.

    Used to pre-select a sensible default in the dropdowns. Returns None if the
    scoring table comes back empty (e.g. a season with no data yet).

    Important: the LeagueDashPlayerStats team filter still includes players who
    were traded away mid-season (they logged games for this team), so a departed
    star like a mid-year trade can outscore everyone still here. We intersect
    with the current CommonTeamRoster so the "top scorer" is someone actually on
    the team now — this also keeps the Game Plan tab and the Defend dropdown in
    agreement, since the dropdown lists that same roster.
    """
    df = get_team_player_scoring(team_name, season)
    if df.empty:
        return None
    try:
        roster_ids = set(get_roster(team_name, season)["PLAYER_ID"])
        on_roster = df[df["PLAYER_ID"].isin(roster_ids)]
        if not on_roster.empty:
            df = on_roster
    except Exception:
        pass
    top = df.sort_values("PTS", ascending=False).iloc[0]
    return top["PLAYER_NAME"]


# ---------------------------------------------------------------------------
# Player card data — photo, headline stats, season efficiency
# ---------------------------------------------------------------------------
def get_player_photo_url(player_name):
    """NBA CDN headshot URL (1040x760 png) for a player, via their player id."""
    pid = get_player_id(player_name)
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"


def get_player_headline_stats(player_name, team_name, season):
    """Per-game PTS/REB/AST plus position for a player.

    PTS/REB/AST come from LeagueDashPlayerStats (PerGame, team-filtered, via the
    cached get_team_player_scoring); position comes from the cached roster pull.
    Anything we can't find comes back as None / '' rather than raising, so a
    missing stat never breaks the card.
    """
    out = {"player": player_name, "team": team_name, "position": "",
           "ppg": None, "rpg": None, "apg": None}

    def _match(df, col):
        row = df[df[col] == player_name]
        if row.empty:
            row = df[df[col].str.lower() == player_name.lower()]
        return row

    try:
        stats = get_team_player_scoring(team_name, season)
        row = _match(stats, "PLAYER_NAME")
        if not row.empty:
            r = row.iloc[0]
            out["ppg"] = round(float(r["PTS"]), 1)
            out["rpg"] = round(float(r["REB"]), 1)
            out["apg"] = round(float(r["AST"]), 1)
    except Exception:
        pass

    try:
        roster = get_roster(team_name, season)
        rr = _match(roster, "PLAYER")
        if not rr.empty:
            out["position"] = str(rr.iloc[0]["POSITION"])
    except Exception:
        pass

    return out


def get_player_avg_matchup_pts_per_poss(player_name, season):
    """The player's overall season points-per-possession across all his
    matchups (total points / total partial possessions). This is the baseline
    a single matchup gets compared against. Returns None if there's no data."""
    df = get_matchups(player_name, season)
    if df.empty:
        return None
    total_poss = float(df["PARTIAL_POSS"].sum())
    if total_poss <= 0:
        return None
    return round(float(df["PLAYER_PTS"].sum()) / total_poss, 2)


# Advanced metrics we surface on the cards: dict key -> (value col, rank col).
_ADV_FIELDS = {
    "off_rating": ("OFF_RATING", "OFF_RATING_RANK"),
    "def_rating": ("DEF_RATING", "DEF_RATING_RANK"),
    "net_rating": ("NET_RATING", "NET_RATING_RANK"),
    "ts_pct":     ("TS_PCT", "TS_PCT_RANK"),
    "efg_pct":    ("EFG_PCT", "EFG_PCT_RANK"),
    "usg_pct":    ("USG_PCT", "USG_PCT_RANK"),
    "reb_pct":    ("REB_PCT", "REB_PCT_RANK"),
    "ast_pct":    ("AST_PCT", "AST_PCT_RANK"),
}


def _league_advanced_stats(season):
    """Whole-league Advanced player stats (so the *_RANK columns are league-wide,
    not filtered to one team). Cached to disk."""
    def fetch():
        s = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            timeout=TIMEOUT,
        )
        return s.get_data_frames()[0]

    return cached_pull(f"advstats_{season}", fetch)


def get_advanced_player_stats(player_name, team_name, season):
    """Advanced metrics + league ranks for a player.

    Returns a dict: each of off_rating/def_rating/net_rating/ts_pct/efg_pct/
    usg_pct maps to {"value": float|None, "rank": int|None}, plus
    "total_players" (the size of the ranked pool). Every column is checked to
    exist before it's read, and anything missing comes back as None — a missing
    stat never raises.
    """
    out = {key: {"value": None, "rank": None} for key in _ADV_FIELDS}
    out["total_players"] = None

    try:
        df = _league_advanced_stats(season)
    except Exception:
        return out
    if df is None or df.empty or "PLAYER_NAME" not in df.columns:
        return out

    out["total_players"] = int(len(df))

    row = df[df["PLAYER_NAME"] == player_name]
    if row.empty:
        row = df[df["PLAYER_NAME"].str.lower() == player_name.lower()]
    if len(row) > 1:
        # Disambiguate a duplicate name by team when we can.
        try:
            abbr = get_team_abbreviation(team_name)
            narrowed = row[row["TEAM_ABBREVIATION"] == abbr]
            if not narrowed.empty:
                row = narrowed
        except Exception:
            pass
    if row.empty:
        return out

    r = row.iloc[0]
    for key, (vcol, rcol) in _ADV_FIELDS.items():
        if vcol in df.columns:
            try:
                out[key]["value"] = float(r[vcol])
            except (TypeError, ValueError):
                pass
        if rcol in df.columns:
            try:
                out[key]["rank"] = int(r[rcol])
            except (TypeError, ValueError):
                pass
    return out


# ---------------------------------------------------------------------------
# Four Factors (team-level) — the four things that swing games
# ---------------------------------------------------------------------------
def _league_four_factors(season):
    def fetch():
        s = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_detailed_defense="Four Factors",
            per_mode_detailed="PerGame",
            timeout=TIMEOUT,
        )
        return s.get_data_frames()[0]

    return cached_pull(f"fourfactors_{season}", fetch)


def _league_team_advanced(season):
    def fetch():
        s = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            timeout=TIMEOUT,
        )
        return s.get_data_frames()[0]

    return cached_pull(f"teamadv_{season}", fetch)


def get_four_factors(team_name, season):
    """A team's four factors: EFG_PCT, FTA_RATE, TM_TOV_PCT, OREB_PCT, each with
    its league rank (rank 1 = best — the NBA already accounts for direction, so
    rank 1 is lowest turnovers and highest eFG/FTA/OREB), plus total_teams.

    Pulls LeagueDashTeamStats with the Four Factors measure type. If that call
    errors, falls back to the Advanced team table (which carries efg/tov/oreb,
    no fta_rate, no ranks). Missing values come back as None.
    """
    out = {"efg_pct": None, "fta_rate": None, "tm_tov_pct": None, "oreb_pct": None,
           "efg_pct_rank": None, "fta_rate_rank": None, "tm_tov_pct_rank": None,
           "oreb_pct_rank": None, "total_teams": None}
    try:
        team_id = get_team_id(team_name)
    except Exception:
        return out

    # key -> (value column, rank column)
    fields = [("efg_pct", "EFG_PCT", "EFG_PCT_RANK"),
              ("fta_rate", "FTA_RATE", "FTA_RATE_RANK"),
              ("tm_tov_pct", "TM_TOV_PCT", "TM_TOV_PCT_RANK"),
              ("oreb_pct", "OREB_PCT", "OREB_PCT_RANK")]
    try:
        df = _league_four_factors(season)
        out["total_teams"] = int(len(df))
        row = df[df["TEAM_ID"] == team_id]
        if not row.empty:
            r = row.iloc[0]
            for key, col, rcol in fields:
                if col in df.columns:
                    try:
                        out[key] = float(r[col])
                    except (TypeError, ValueError):
                        pass
                if rcol in df.columns:
                    try:
                        out[key + "_rank"] = int(r[rcol])
                    except (TypeError, ValueError):
                        pass
            return out
    except Exception:
        pass

    # Fallback: the Advanced team table carries efg / tov / oreb (no fta_rate).
    try:
        adv = _league_team_advanced(season)
        row = adv[adv["TEAM_ID"] == team_id]
        if not row.empty:
            r = row.iloc[0]
            for key, col in [("efg_pct", "EFG_PCT"), ("tm_tov_pct", "TM_TOV_PCT"),
                             ("oreb_pct", "OREB_PCT")]:
                if col in adv.columns:
                    try:
                        out[key] = float(r[col])
                    except (TypeError, ValueError):
                        pass
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Clutch stats — who a team feeds in the last 5 minutes of a close game
# ---------------------------------------------------------------------------
# "Clutch" here = last 5 minutes of the 4th/OT with the score within 5 points,
# which is the NBA's standard clutch definition.
def _league_clutch(season, measure):
    def fetch():
        c = leaguedashplayerclutch.LeagueDashPlayerClutch(
            season=season,
            clutch_time="Last 5 Minutes",
            ahead_behind="Ahead or Behind",
            point_diff=5,
            measure_type_detailed_defense=measure,
            per_mode_detailed="PerGame",
            timeout=TIMEOUT,
        )
        return c.get_data_frames()[0]

    return cached_pull(f"clutch_{measure}_{season}", fetch)


def get_clutch_stats(team_name, season, top_n=5):
    """A team's key clutch players (last 5 min, margin <= 5), sorted by clutch
    points per game. Each entry: player, clutch GP, PTS/game, FG%, and usage
    (usage from the Advanced clutch table; None if unavailable). Returns []
    on any failure so the tab degrades gracefully.
    """
    out = []
    try:
        team_id = get_team_id(team_name)
    except Exception:
        return out
    try:
        base = _league_clutch(season, "Base")
    except Exception:
        return out

    base = base[base["TEAM_ID"] == team_id]
    if base.empty:
        return out
    # Drop one-off appearances so a single hot game doesn't top the list.
    if "GP" in base.columns and (base["GP"] >= 2).any():
        base = base[base["GP"] >= 2]

    # Usage comes from the Advanced clutch table (best-effort).
    usg_map = {}
    try:
        adv = _league_clutch(season, "Advanced")
        adv = adv[adv["TEAM_ID"] == team_id]
        if "USG_PCT" in adv.columns:
            usg_map = dict(zip(adv["PLAYER_ID"], adv["USG_PCT"]))
    except Exception:
        pass

    # Rank by total clutch scoring (games x points/game) so "who they feed late"
    # reflects volume + frequency, not a 2-game hot streak.
    base = base.copy()
    base["_total"] = base["PTS"] * base["GP"]
    base = base.sort_values("_total", ascending=False).head(top_n)
    for _, r in base.iterrows():
        usg = usg_map.get(r["PLAYER_ID"])
        out.append({
            "player": r["PLAYER_NAME"],
            "gp": int(r["GP"]) if "GP" in base.columns else None,
            "pts": float(r["PTS"]) if "PTS" in base.columns else None,
            "fg_pct": float(r["FG_PCT"]) if "FG_PCT" in base.columns else None,
            "usg": float(usg) if usg is not None else None,
        })
    return out


# ---------------------------------------------------------------------------
# Player -> team mapping (so the app can tell whose defenders are whose)
# ---------------------------------------------------------------------------
def get_team_abbreviation(team_name):
    """Three-letter abbreviation for a team's full name (offline static data)."""
    team_id = get_team_id(team_name)
    for t in teams.get_teams():
        if t["id"] == team_id:
            return t["abbreviation"]
    raise ValueError(f"No abbreviation found for team: {team_name!r}")


def _league_player_stats(season):
    """Whole-league per-player stats for the season (used for the team map)."""
    def fetch():
        s = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            per_mode_detailed="Totals",
            timeout=TIMEOUT,
        )
        return s.get_data_frames()[0]

    return cached_pull(f"leaguestats_{season}", fetch)


def get_player_team_map(season):
    """Map every player's name -> their team abbreviation for the season.

    A traded player can show up more than once; I keep the row where he played
    the most games (GP), so he maps to the team he actually spent most of the
    season with rather than a random stint.
    """
    df = _league_player_stats(season)
    if df.empty:
        return {}
    keep_idx = df.groupby("PLAYER_NAME")["GP"].idxmax()
    best = df.loc[keep_idx]
    return dict(zip(best["PLAYER_NAME"], best["TEAM_ABBREVIATION"]))


def annotate_matchups_with_team(matchups_df, season):
    """Add a TEAM column to a get_matchups() frame by looking up each defender's
    team. Defenders we can't place (name mismatch, etc.) get '—'."""
    team_map = get_player_team_map(season)
    out = matchups_df.copy()
    out["TEAM"] = out["DEF_PLAYER_NAME"].map(lambda name: team_map.get(name, "—"))
    return out


# ---------------------------------------------------------------------------
# Projection model — estimate a matchup when there's no head-to-head data
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def get_defender_zone_defense(season):
    """How well each defender holds shooters, by zone.

    Pulls LeagueDashPtDefend once per zone (cached to disk) and returns:
        {player_name: {zone: {"d_fg_pct": float, "plusminus": float}}}
    where plusminus < 0 means the defender holds shooters BELOW their normal
    clip (a good defender). lru_cache keeps the assembled dict around so the
    per-roster projection loop doesn't rebuild it for every player.
    """
    by_player = {}
    for zone, spec in ZONE_DEFENSE_SPEC.items():
        category = spec["category"]
        dfg_col = spec["dfg_col"]
        fga_col = spec["fga_col"]

        def fetch(category=category):
            d = leaguedashptdefend.LeagueDashPtDefend(
                season=season,
                defense_category=category,
                per_mode_simple="Totals",
                timeout=TIMEOUT,
            )
            return d.get_data_frames()[0]

        df = cached_pull(f"ptdefend_{category.replace(' ', '_')}_{season}", fetch)
        if df.empty:
            continue
        # One row per defender — if a name somehow repeats, keep his busiest row.
        df = df.sort_values("GP", ascending=False).drop_duplicates("PLAYER_NAME")
        for _, row in df.iterrows():
            # Sample-size floor: skip this zone if the defender hasn't faced
            # enough shots there. With too few attempts the plus-minus is noise,
            # so we treat it as "not enough data" rather than trusting it.
            if float(row[fga_col]) < MIN_DEFENDED_FGA:
                continue
            rec = by_player.setdefault(row["PLAYER_NAME"], {})
            rec[zone] = {
                "d_fg_pct": float(row[dfg_col]),
                "plusminus": float(row["PLUSMINUS"]),
            }
    return by_player


@functools.lru_cache(maxsize=None)
def get_attacker_zone_profile(player_name, team_name, season):
    """Where the attacker scores, in the same three zones.

    From his shot chart, the share of shots and make% in each of at-rim
    (<6 ft), short-mid (other 2s), and three. Returns:
        {zone: {"share": 0..1, "make_pct": 0..100}, "total_shots": int}
    """
    shots = get_shots(player_name, team_name, season)
    total = len(shots)

    profile = {}
    if total == 0:
        for zone in ZONE_DEFENSE_SPEC:
            profile[zone] = {"share": 0.0, "make_pct": 0.0}
        profile["total_shots"] = 0
        return profile

    is_three = shots["SHOT_TYPE"] == "3PT Field Goal"
    masks = {
        "at_rim": (~is_three) & (shots["SHOT_DISTANCE"] < 6),
        "short_mid": (~is_three) & (shots["SHOT_DISTANCE"] >= 6),
        "three": is_three,
    }
    for zone, mask in masks.items():
        zone_shots = shots[mask]
        n = len(zone_shots)
        make = float(zone_shots["SHOT_MADE_FLAG"].mean()) if n else 0.0
        profile[zone] = {"share": round(n / total, 3),
                         "make_pct": round(make * 100, 1)}
    profile["total_shots"] = total
    return profile


def project_matchup(attacker_name, attacker_team, defender_name, season):
    """Estimate how a matchup would go from each player's season profile.

    Overlays the attacker's zone shot-share against the defender's zone defense
    (weighting each zone by how often the attacker shoots there). Returns a dict
    with a label ("Favourable"/"Neutral"/"Tough"), the weighted score, and a
    one-line plain-English reason.
    """
    profile = get_attacker_zone_profile(attacker_name, attacker_team, season)
    defense = get_defender_zone_defense(season)
    def_zones = defense.get(defender_name)

    result = {"defender": defender_name, "label": "Neutral", "score": 0.0,
              "reason": "", "reason_defend": "", "insufficient": False}

    if profile["total_shots"] == 0:
        result["insufficient"] = True
        result["reason"] = f"No shot data for {attacker_name} — can't project."
        result["reason_defend"] = result["reason"]
        return result
    if not def_zones:
        result["insufficient"] = True
        result["reason"] = f"No defensive profile for {defender_name} this season."
        result["reason_defend"] = result["reason"]
        return result

    # Weighted score = average of (zone plusminus) weighted by attacker shot share.
    # `contrib` tracks each zone's signed push on the verdict (share x plusminus)
    # so the reason can name the zone actually driving the result.
    score, weight = 0.0, 0.0
    contrib = {}
    for zone in ZONE_DEFENSE_SPEC:
        share = profile.get(zone, {}).get("share", 0.0)
        zd = def_zones.get(zone)
        if zd is None or share == 0:
            continue
        score += share * zd["plusminus"]
        weight += share
        contrib[zone] = share * zd["plusminus"]
    if weight > 0:
        score /= weight       # normalise so zones we lack defense data for don't dilute
    score = round(score, 4)

    if score >= PROJ_FAVOURABLE_CUTOFF:
        label = "Favourable"
    elif score <= PROJ_TOUGH_CUTOFF:
        label = "Tough"
    else:
        label = "Neutral"

    # Reason keys off the *driving* zone: where the attacker takes a meaningful
    # share AND the defender deviates most from average — i.e. the zone with the
    # largest |share x plusminus|. This makes the reason vary by defender instead
    # of always defaulting to the rim.
    driver = max(contrib, key=lambda z: abs(contrib[z])) if contrib else \
        max(ZONE_DEFENSE_SPEC, key=lambda z: profile.get(z, {}).get("share", 0.0))
    driver_share = profile[driver]["share"] * 100
    driver_pm = def_zones.get(driver, {}).get("plusminus", 0.0)
    if driver_pm > 0.005:
        defender_quality = "below-average"
    elif driver_pm < -0.005:
        defender_quality = "above-average"
    else:
        defender_quality = "about average"

    result["label"] = label
    result["score"] = score
    # Attack-tab wording: "He" = my attacker, which reads correctly there.
    result["reason"] = (
        f"He takes {driver_share:.0f}% of shots {ZONE_LABELS[driver]}, where this "
        f"defender is {defender_quality} — {label.lower()}."
    )
    # Defend-tab wording: the row is the DEFENDER, so name the scouted attacker
    # as the shooter explicitly — never let it read as if the defender shoots.
    attacker_first = attacker_name.split()[0]
    result["reason_defend"] = (
        f"{attacker_first} takes {driver_share:.0f}% of his shots "
        f"{ZONE_LABELS[driver]}, where {defender_name} is {defender_quality} — "
        f"{DEFEND_VERDICT[label]}."
    )
    return result


def best_defenders_projected(star_name, star_team, my_team, season):
    """Projected version of 'who on my roster can guard him'.

    Runs project_matchup for every player on My Team (star = attacker, my player
    = defender) and returns them sorted toughest-first (lowest score = the
    defender who'd give the attacker the least)."""
    roster = get_roster(my_team, season)["PLAYER"].tolist()
    results = [project_matchup(star_name, star_team, defender, season)
               for defender in roster]
    results.sort(key=lambda r: r["score"])   # toughest matchup for attacker first
    return results


# ---------------------------------------------------------------------------
# Offensive matchup hunting — who to attack (their weak link) and with whom
# ---------------------------------------------------------------------------
ROTATION_MIN_MPG = 15.0   # only hunt defenders who actually play rotation minutes
MIN_ATTACK_EDGE = 0.02    # an observed edge must clear this to count as a real seam
                          # (smaller than this rounds to "+0.00" and is just noise)


def _rotation_players(team_name, season, min_mpg=ROTATION_MIN_MPG):
    """Current-roster players who log at least `min_mpg` minutes per game — the
    ones actually worth game-planning around (you can't hunt a benchwarmer)."""
    df = get_team_player_scoring(team_name, season)
    if df.empty or "MIN" not in df.columns or "PLAYER_NAME" not in df.columns:
        return set()
    try:
        roster_ids = set(get_roster(team_name, season)["PLAYER_ID"])
        df = df[df["PLAYER_ID"].isin(roster_ids)]
    except Exception:
        pass
    return set(df[df["MIN"] >= min_mpg]["PLAYER_NAME"])


def find_attack_mismatch(my_team, opponent, season, exclude=None):
    """The best offensive matchup to hunt: which of our players has the biggest
    scoring edge against which of the opponent's rotation defenders.

    Offense is about hunting mismatches, not featuring your top scorer — so this
    scans our whole roster against the opponent's rotation defenders and returns
    the strongest edge as {attacker, defender, kind, ...}, or None.

    Guardrails: the defender must be an opponent rotation player (>= ROTATION_MIN_MPG)
    so we don't scheme to attack someone who barely plays, and observed matchups
    already carry get_matchups' 40-possession floor. A real observed edge (our
    player scores above his own season average on that defender) is preferred;
    otherwise it falls back to the projection model.
    """
    try:
        opp_abbr = get_team_abbreviation(opponent)
    except Exception:
        return None
    opp_rotation = _rotation_players(opponent, season)
    if not opp_rotation:
        return None
    # Only hunt WITH our own rotation players — a bench guy with a fluky 40-poss
    # sample shouldn't be the recommended attacker either.
    my_rotation = _rotation_players(my_team, season)
    try:
        my_roster = get_roster(my_team, season)["PLAYER"].tolist()
    except Exception:
        return None
    if my_rotation:
        my_roster = [p for p in my_roster if p in my_rotation]
    # The player guarding their star isn't our primary hunter — exclude him so
    # the attack card never duplicates the defensive-assignment card.
    if exclude:
        my_roster = [p for p in my_roster if p not in exclude]

    # 1) Observed: among genuine-edge matchups vs opponent rotation defenders,
    # pick the one with the highest raw points-per-possession. We rank by raw
    # scoring (not edge-over-average) so a real offensive threat wins, rather
    # than a low-usage defensive specialist whose tiny baseline inflates his
    # "edge" — that bug made the attack card duplicate the defender card.
    best = None
    for attacker in my_roster:
        try:
            mu = annotate_matchups_with_team(get_matchups(attacker, season), season)
        except Exception:
            continue
        avg = get_player_avg_matchup_pts_per_poss(attacker, season)
        if avg is None:
            continue
        vs = mu[(mu["TEAM"] == opp_abbr)
                & (mu["DEF_PLAYER_NAME"].isin(opp_rotation))]
        for _, r in vs.iterrows():
            ppp = float(r["PTS_PER_POSS"])
            edge = ppp - avg
            if edge < MIN_ATTACK_EDGE:
                continue                      # not a meaningful edge for this player
            cand = {"attacker": attacker, "defender": r["DEF_PLAYER_NAME"],
                    "kind": "observed", "ppp": round(ppp, 2),
                    "attacker_avg": round(avg, 2), "edge": round(edge, 2),
                    "poss": round(float(r["PARTIAL_POSS"]), 1)}
            if best is None or cand["ppp"] > best["ppp"]:
                best = cand
    if best is not None:
        return best

    # 2) Fallback: projection model — best favourable (attacker, defender) pair.
    best_proj = None
    for attacker in my_roster:
        for defender in opp_rotation:
            try:
                res = project_matchup(attacker, my_team, defender, season)
            except Exception:
                continue
            # Only a genuinely Favourable projection counts as a seam to hunt.
            if res.get("insufficient") or res["score"] < PROJ_FAVOURABLE_CUTOFF:
                continue
            if best_proj is None or res["score"] > best_proj["score"]:
                best_proj = {"attacker": attacker, "defender": defender,
                             "kind": "projected", "score": res["score"],
                             "label": res["label"]}
    return best_proj


def recommend_defender(star_name, star_team, my_team, season):
    """Which of my players to assign to guard the opponent's star.

    Mirrors find_attack_mismatch's rotation guardrail: only my-team players who
    pass the same ROTATION_MIN_MPG filter are considered, so a bench guy with one
    good 40-possession stretch can't be recommended on a superstar. Prefers a
    real observed matchup (best = fewest points per possession allowed, 40+ poss
    via get_matchups' floor); if no rotation defender has observed data, falls
    back to the best rotation defender by projection. Returns
    {defender, kind, ...} or None.
    """
    try:
        my_abbr = get_team_abbreviation(my_team)
    except Exception:
        return None
    rotation = _rotation_players(my_team, season)

    # 1) Observed: best rotation defender who has actually guarded the star.
    try:
        mu = annotate_matchups_with_team(get_matchups(star_name, season), season)
    except Exception:
        mu = None
    if mu is not None and not mu.empty:
        roster_def = mu[mu["TEAM"] == my_abbr]
        if rotation:                          # skip filter only if we have no MPG data
            roster_def = roster_def[roster_def["DEF_PLAYER_NAME"].isin(rotation)]
        roster_def = roster_def.sort_values("PTS_PER_POSS", ascending=True)
        if not roster_def.empty:
            r = roster_def.iloc[0]
            return {"defender": r["DEF_PLAYER_NAME"], "kind": "observed",
                    "ppp": round(float(r["PTS_PER_POSS"]), 2),
                    "poss": round(float(r["PARTIAL_POSS"]), 1)}

    # 2) Fallback: best rotation defender by projection (clearly labelled).
    try:
        proj = [p for p in best_defenders_projected(star_name, star_team,
                                                    my_team, season)
                if not p.get("insufficient")]
    except Exception:
        proj = []
    if rotation:
        proj = [p for p in proj if p["defender"] in rotation]
    if proj:
        best = proj[0]                        # already sorted toughest-first
        return {"defender": best["defender"], "kind": "projected",
                "label": best["label"]}
    return None


# ---------------------------------------------------------------------------
# Quick manual test — run this file directly to check all four functions work.
# I use Jokić because his data is rich enough to eyeball whether the numbers
# look sane.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    PLAYER = "Nikola Jokić"
    TEAM = "Denver Nuggets"
    SEASON = "2023-24"

    print("=" * 70)
    print(f"SCOUTING REPORT — {PLAYER} ({TEAM}, {SEASON})")
    print("=" * 70)

    # first check the two id lookups resolve
    pid = get_player_id(PLAYER)
    tid = get_team_id(TEAM)
    print(f"\nPlayer ID: {pid}   Team ID: {tid}")

    # matchups: print the best and worst defenders so I can compare the extremes
    matchups = get_matchups(PLAYER, SEASON)
    print(f"\nMatchups (>= {POSS_FLOOR} possessions): {len(matchups)} defenders")
    print("\nMOST efficient matchups (attack these):")
    print(matchups.head(5).to_string(index=False))
    print("\nTOUGHEST matchups (slowed him down):")
    print(matchups.tail(5).to_string(index=False))

    # shots: just confirm we got rows back and the columns look right
    shots = get_shots(PLAYER, TEAM, SEASON)
    print(f"\nShot-chart rows: {len(shots)}")
    print(shots.head().to_string(index=False))

    # and finally the summary that ties the shot data into actual tendencies
    summary = scouting_summary(PLAYER, TEAM, SEASON)
    print("\n" + "-" * 70)
    print("SCOUTING SUMMARY")
    print("-" * 70)
    print(f"Total shots: {summary['total_shots']}")
    print(f"Avg shot distance: {summary['avg_shot_distance']} ft")

    print("\n% of shots by ACTION_TYPE (top 5):")
    for action, pct in summary["action_type_pct"].items():
        print(f"  {pct:5.1f}%  {action}")

    print("\nMake % by SHOT_ZONE_BASIC:")
    for zone, pct in summary["make_pct_by_zone"].items():
        print(f"  {pct:5.1f}%  {zone}")

    print("\nMake % by SHOT_ZONE_AREA:")
    for area, pct in summary["make_pct_by_area"].items():
        print(f"  {pct:5.1f}%  {area}")
