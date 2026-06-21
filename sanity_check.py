# --- Matchup Advantage: data sanity check ---
import pandas as pd
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import leagueseasonmatchups, shotchartdetail

SEASON = "2023-24"

# 1. Resolve IDs offline (bundled, no network needed)
scorer = players.find_players_by_full_name("Anthony Davis")[0]
print("Scorer:", scorer["full_name"], scorer["id"])

# 2. MATCHUP DATA — who guarded him, and how he did against each defender
mu = leagueseasonmatchups.LeagueSeasonMatchups(
    off_player_id_nullable=scorer["id"],
    season=SEASON,
    per_mode_simple="Totals",
    timeout=60,
)
df = mu.get_data_frames()[0]
print("\nMatchup rows returned:", len(df))

keep = ["DEF_PLAYER_NAME", "PARTIAL_POSS", "PLAYER_PTS",
        "MATCHUP_FG_PCT", "MATCHUP_FG3_PCT"]
clean = df[keep].copy()
clean = clean[clean["PARTIAL_POSS"] >= 20]          # drop tiny samples
clean["PTS_PER_POSS"] = (clean["PLAYER_PTS"] / clean["PARTIAL_POSS"]).round(3)
clean = clean.sort_values("PTS_PER_POSS", ascending=False)

print("\nDefenders Davis scored MOST efficiently against (attack these):")
print(clean.head(5).to_string(index=False))
print("\nDefenders who slowed him DOWN (his tough matchups):")
print(clean.tail(5).to_string(index=False))

# 3. SHOT-CHART DATA — needed for the Defend tab hot/cold map
lakers = [t for t in teams.get_teams() if t["full_name"] == "Los Angeles Lakers"][0]
sc = shotchartdetail.ShotChartDetail(
    team_id=lakers["id"], player_id=scorer["id"],
    season_nullable=SEASON, season_type_all_star="Regular Season",
    context_measure_simple="FGA", timeout=60,
)
shots = sc.get_data_frames()[0]
print(f"\nShot-chart rows: {len(shots)}  | columns include LOC_X, LOC_Y, SHOT_MADE_FLAG:",
      all(c in shots.columns for c in ["LOC_X", "LOC_Y", "SHOT_MADE_FLAG"]))
