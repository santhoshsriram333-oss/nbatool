# --- TEMPORARY read-only diagnostic — safe to delete ---
# Runs the tool's CORE recommendation logic (no Streamlit/UI) across several
# matchups + seasons and flags likely flaws. It mirrors what app.py does:
#   - defender pick  == defend_takeaway()  (best observed defender, else projected)
#   - attack edge    == Attack tab league-wide table (top PTS_PER_POSS row)
#   - radar defender == the recommended defender (comparison_radar uses tk.assigned)
#   - four factors   == get_four_factors() for both teams
# It does NOT modify any app code.

import warnings
warnings.filterwarnings("ignore")

import data_pipeline as dp

# Pairings to audit. "at least these for 2023-24" + 2024-25 for cross-season breadth.
PAIRINGS = [
    ("Boston Celtics", "Denver Nuggets"),
    ("Oklahoma City Thunder", "Minnesota Timberwolves"),
    ("Milwaukee Bucks", "Indiana Pacers"),
    ("Phoenix Suns", "Los Angeles Lakers"),
]
SEASONS = ["2025-26", "2024-25", "2023-24"]   # 2025-26 first — it's the tool's default

# Thresholds for flagging artifacts.
MIN_GP = 20        # below this = small sample
MIN_MPG = 15.0     # below this = not a real rotation player
MIN_EDGE_POSS = 40 # an "edge" built on fewer possessions than this is shaky


def player_gp_mpg(team, player, season):
    """Games played and minutes-per-game for a player, from the team's per-game
    table. Returns (gp, mpg) or (None, None)."""
    try:
        df = dp.get_team_player_scoring(team, season)
    except Exception:
        return None, None
    row = df[df["PLAYER_NAME"] == player]
    if row.empty:
        row = df[df["PLAYER_NAME"].str.lower() == player.lower()]
    if row.empty:
        return None, None
    r = row.iloc[0]
    gp = int(r["GP"]) if "GP" in df.columns else None
    mpg = round(float(r["MIN"]), 1) if "MIN" in df.columns else None
    return gp, mpg


def recommended_defender(my_team, opponent, season):
    """Who the tool would assign to guard the opponent's top scorer. Calls the
    REAL core logic (dp.recommend_defender), so this audit tests exactly what
    the app does. Returns (star, defender, kind)."""
    star = dp.get_top_scorer(opponent, season)
    if not star:
        return None, None, "no-star"
    rec = dp.recommend_defender(star, opponent, my_team, season)
    if not rec:
        return star, None, "none"
    return star, rec["defender"], rec["kind"]


def top_attack_edge(my_team, season):
    """The top 'edge' defender in the Attack tab's league-wide table for our
    default attacker (top scorer). Returns (player, defender, poss, ppp)."""
    player = dp.get_top_scorer(my_team, season)
    if not player:
        return None, None, None, None
    try:
        mu = dp.get_matchups(player, season).sort_values("PTS_PER_POSS",
                                                         ascending=False)
    except Exception:
        return player, None, None, None
    if mu.empty:
        return player, None, None, None
    top = mu.iloc[0]
    return (player, top["DEF_PLAYER_NAME"],
            round(float(top["PARTIAL_POSS"]), 1), round(float(top["PTS_PER_POSS"]), 2))


_FACTOR_KEYS = ["efg_pct", "fta_rate", "tm_tov_pct", "oreb_pct"]


def four_factor_dupes(team_a, team_b, season):
    """Returns (ff_a, ff_b, list_of_matching_factor keys). Only compares the four
    VALUE factors — not the rank/total_teams metadata, which would always match."""
    a = dp.get_four_factors(team_a, season)
    b = dp.get_four_factors(team_b, season)
    matches = [k for k in _FACTOR_KEYS if a.get(k) is not None and a.get(k) == b.get(k)]
    return a, b, matches


def audit_team(my_team, opponent, season):
    """Run all checks for ONE direction (my_team game-planning vs opponent)."""
    res = {"season": season, "my_team": my_team, "opponent": opponent,
           "flags": []}

    # --- Check 1 + 3: recommended defender (radar uses this same player) ---
    star, defender, kind = recommended_defender(my_team, opponent, season)
    res["star"] = star
    res["defender"] = defender
    res["defender_kind"] = kind
    if defender:
        gp, mpg = player_gp_mpg(my_team, defender, season)
        res["def_gp"], res["def_mpg"] = gp, mpg
        small = (gp is not None and gp < MIN_GP) or (mpg is not None and mpg < MIN_MPG)
        res["def_small_sample"] = small
        if small:
            res["flags"].append("SMALL-SAMPLE DEFENDER")
        # Check 3 — radar defender is the same player; bench artifact if not rotation.
        bench = (gp is not None and gp < MIN_GP) or (mpg is not None and mpg < MIN_MPG)
        res["radar_bench"] = bench
        if bench:
            res["flags"].append("BENCH RADAR DEFENDER")
    else:
        res["def_gp"] = res["def_mpg"] = None
        res["def_small_sample"] = res["radar_bench"] = False

    # --- Check 2: top attack edge + possessions ---
    player, edge_def, poss, ppp = top_attack_edge(my_team, season)
    res["attacker"] = player
    res["edge_def"] = edge_def
    res["edge_poss"] = poss
    res["edge_ppp"] = ppp
    low_poss = poss is not None and poss < MIN_EDGE_POSS
    res["edge_low_poss"] = low_poss
    if low_poss:
        res["flags"].append("LOW-POSSESSION EDGE")

    # --- Check 5: the two Game Plan cards must show DISTINCT players. ---
    # Mirror app.py exactly: defensive card = recommended defender; attacking
    # card = find_attack_mismatch(exclude=defender).attacker, else my_star (only
    # if my_star isn't the assigned defender).
    def_card = defender
    exclude = {defender} if defender else None
    try:
        m = dp.find_attack_mismatch(my_team, opponent, season, exclude=exclude)
    except Exception:
        m = None
    if m:
        att_card = m["attacker"]
    else:
        my_star = dp.get_top_scorer(my_team, season)
        att_card = my_star if (my_star and my_star != def_card) else None
    res["def_card"] = def_card
    res["att_card"] = att_card
    dup = bool(def_card and att_card and def_card == att_card)
    res["dup_card"] = dup
    if dup:
        res["flags"].append("DUPLICATE CARD")

    return res


def main():
    rows = []
    for season in SEASONS:
        for team_a, team_b in PAIRINGS:
            # Four-factors duplication is symmetric — check once per pairing.
            try:
                ffa, ffb, matches = four_factor_dupes(team_a, team_b, season)
            except Exception:
                ffa = ffb = {}
                matches = []

            print("=" * 92)
            print(f"{season}   {team_a}  vs  {team_b}")
            print("=" * 92)

            # Four factors block
            print("  Four Factors (my=%s / opp=%s):" % (team_a, team_b))
            for k in ["efg_pct", "fta_rate", "tm_tov_pct", "oreb_pct"]:
                va, vb = ffa.get(k), ffb.get(k)
                dup = " <-- DUPLICATE" if (va is not None and va == vb) else ""
                print(f"      {k:11}  {va}    {vb}{dup}")
            if matches:
                print(f"      >> FOUR-FACTOR DUPLICATION on: {matches}")

            for my_team, opponent in [(team_a, team_b), (team_b, team_a)]:
                r = audit_team(my_team, opponent, season)
                rows.append(r)
                print(f"\n  [{my_team}]")
                print(f"    Defend {opponent}'s star ({r['star']}):")
                print(f"        recommend: {r['defender']}  "
                      f"(GP={r['def_gp']}, MPG={r['def_mpg']}, src={r['defender_kind']})"
                      + ("   *** SMALL SAMPLE / BENCH ***"
                         if r["def_small_sample"] else ""))
                print(f"    Radar compares {r['star']} vs {r['defender']} "
                      f"-> {'BENCH ARTIFACT' if r['radar_bench'] else 'rotation player'}")
                print(f"    Top attack edge ({r['attacker']}):")
                print(f"        best vs: {r['edge_def']}  "
                      f"({r['edge_ppp']} ppp on {r['edge_poss']} poss)"
                      + ("   *** <40 POSS ***" if r["edge_low_poss"] else ""))
                print(f"    Game Plan cards: DEF={r['def_card']}  ATT={r['att_card']}"
                      + ("   *** DUPLICATE PLAYER ***" if r["dup_card"]
                         else "   (distinct)"))
            print()

    # ---- Clean summary table ----
    print("\n" + "#" * 92)
    print("SUMMARY — which matchups trigger which problems")
    print("#" * 92)
    hdr = (f"{'Season':8} {'Team':4} {'vs':4} {'SmallSampDef':12} {'BenchRadar':10} "
           f"{'LowPossEdge':11} {'DupCard':8} {'4F-Dup':7}")
    print(hdr)
    print("-" * len(hdr))
    any_flag = False
    for r in rows:
        ff_dup = "Y" if r.get("opponent") and _ff_dup_for_row(r) else "-"
        small = "Y" if r["def_small_sample"] else "-"
        bench = "Y" if r["radar_bench"] else "-"
        lowp = "Y" if r["edge_low_poss"] else "-"
        dupc = "Y" if r["dup_card"] else "-"
        if "Y" in (small, bench, lowp, dupc, ff_dup):
            any_flag = True
        print(f"{r['season']:8} {r['my_team'][:3]:4} {r['opponent'][:3]:4} "
              f"{small:12} {bench:10} {lowp:11} {dupc:8} {ff_dup:7}")
    print("-" * len(hdr))
    print("No problems detected." if not any_flag
          else "Problems flagged above (Y = triggered).")


# Cache four-factor dup results per (season, frozenset(pair)) so the summary can
# reuse what the detail block already computed.
_FF_DUP_CACHE = {}


def _ff_dup_for_row(r):
    key = (r["season"], frozenset((r["my_team"], r["opponent"])))
    if key not in _FF_DUP_CACHE:
        try:
            _, _, matches = four_factor_dupes(r["my_team"], r["opponent"],
                                              r["season"])
            _FF_DUP_CACHE[key] = bool(matches)
        except Exception:
            _FF_DUP_CACHE[key] = False
    return _FF_DUP_CACHE[key]


if __name__ == "__main__":
    main()
    print("\nDONE")
