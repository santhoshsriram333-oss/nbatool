# Matchup Advantage

An NBA opponent advance-scouting tool. Given a player and season, it pulls how
they performed against each individual defender and where they shoot from on the
floor, so you can spot the matchups to attack and the spots to defend.

## Data layer

[`data_pipeline.py`](data_pipeline.py) is the data layer. It wraps the
[`nba_api`](https://github.com/swar/nba_api) endpoints with:

- **`get_player_id` / `get_team_id`** — resolve names to IDs from the bundled
  offline static data.
- **`get_matchups`** — per-defender matchup stats with a 40-possession floor and
  a points-per-possession column, sorted best-to-worst.
- **`get_shots`** — cleaned shot-chart data (locations, zones, make flag).
- **`scouting_summary`** — a tidy summary of a player's shooting tendencies.

Every API pull is cached to disk (`cache/`) and retried once on failure, so
repeat runs are instant and a flaky `stats.nba.com` can't break a demo.

`sanity_check.py` is the original throwaway script the pipeline grew out of.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install nba_api pandas
python data_pipeline.py   # runs a sample scouting report for Nikola Jokić
```
