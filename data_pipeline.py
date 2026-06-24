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
    (PTS, in PerGame mode) lives — that's what I use to find the top scorer.
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
    """Name of the team's highest points-per-game player that season.

    Used to pre-select a sensible default in the dropdowns. Returns None if the
    scoring table comes back empty (e.g. a season with no data yet).
    """
    df = get_team_player_scoring(team_name, season)
    if df.empty:
        return None
    top = df.sort_values("PTS", ascending=False).iloc[0]
    return top["PLAYER_NAME"]


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
