# --- Matchup Advantage: possession-floor sensitivity check ---
# How much does the defensive game-plan change if I move the possession floor?
# This reuses the already-cached raw matchup pull, so it makes NO API calls.
# (get_matchups applies the floor *after* the cached pull, so the cache holds
# every defender — I just re-apply different floors here.)

import data_pipeline as dp

# -----------------------------------------------------------------------------
# Why I wrote this
# -----------------------------------------------------------------------------
# I kept wondering whether our 40-possession floor was just a number I picked out
# of nowhere, so this script is me actually checking it. The worry: the "toughest
# matchups" we hand a coach are the whole point of the defend view, and if those
# names flip around every time we nudge the floor, the scouting output isn't
# trustworthy.
#
# What it does: it takes the matchup data we've ALREADY cached (no new API
# calls), and re-applies three different floors — 30, 40, 50 — then compares the
# toughest-5 defender lists you'd get from each.
#
# What I found: under 40, the list gets hijacked by small-sample noise — guys
# with ~30 possessions who happened to hold Jokić to a handful of points. Those
# look impressive but they're basically flukes, and they wash out as soon as you
# raise the floor. From 40 upward the names settle down — Johnson, Horford, and
# Davis all survive into the 50 floor too. So 40 is the sweet spot: it's where
# the noisy small samples drop out but you still keep enough real matchups to
# build a plan around. That's why it's our default.
#
# It's also why the tool lets the user slide the floor themselves — there's no
# single "correct" cutoff, so we expose it and just default to 40 as the sane
# starting point.
# -----------------------------------------------------------------------------

PLAYER = "Nikola Jokić"
SEASON = "2025-26"
FLOORS = [30, 40, 50]
TOP_N = 5


def _raise_no_network():
    # Guard: if the cache is missing this should blow up rather than silently
    # hit stats.nba.com — the whole point is to stay offline.
    raise RuntimeError(
        "Raw matchup data is not cached — refusing to make a network call. "
        "Run data_pipeline.py for this player/season first."
    )


# Pull the RAW, unfiltered matchup table straight from the cache.
player_id = dp.get_player_id(PLAYER)
cache_key = f"matchups_{player_id}_{SEASON}"
raw = dp.cached_pull(cache_key, _raise_no_network)

# Keep only the columns we need and add PTS_PER_POSS once on the full table.
keep = ["DEF_PLAYER_NAME", "PARTIAL_POSS", "PLAYER_PTS"]
base = raw[keep].copy()
base["PTS_PER_POSS"] = (base["PLAYER_PTS"] / base["PARTIAL_POSS"]).round(3)

print("=" * 70)
print(f"POSSESSION-FLOOR SENSITIVITY — {PLAYER} ({SEASON})")
print(f"Raw defenders in cache (any sample size): {len(base)}")
print("=" * 70)

toughest_sets = {}  # floor -> set of 5 toughest defender names

for floor in FLOORS:
    cleared = base[base["PARTIAL_POSS"] >= floor].copy()
    cleared = cleared.sort_values("PTS_PER_POSS", ascending=False)

    easiest = cleared.head(TOP_N)                  # highest PTS_PER_POSS
    toughest = cleared.tail(TOP_N).iloc[::-1]      # lowest PTS_PER_POSS, worst first
    toughest_sets[floor] = set(toughest["DEF_PLAYER_NAME"])

    print(f"\n--- Floor >= {floor} possessions: {len(cleared)} defenders cleared ---")
    print(f"\nTOUGHEST {TOP_N} (lowest PTS_PER_POSS — defend with these):")
    print(toughest[["DEF_PLAYER_NAME", "PARTIAL_POSS",
                    "PLAYER_PTS", "PTS_PER_POSS"]].to_string(index=False))
    print(f"\nEASIEST {TOP_N} (highest PTS_PER_POSS — attack these):")
    print(easiest[["DEF_PLAYER_NAME", "PARTIAL_POSS",
                   "PLAYER_PTS", "PTS_PER_POSS"]].to_string(index=False))

# How stable is the defensive game-plan? Names common to all three toughest-5s.
common = set.intersection(*toughest_sets.values())

print("\n" + "=" * 70)
print("STABILITY OF THE TOUGHEST-5 ACROSS FLOORS")
print("=" * 70)
for floor in FLOORS:
    print(f"  floor {floor}: {sorted(toughest_sets[floor])}")
print(f"\nDefenders appearing in ALL three toughest-5 lists: {len(common)}")
print(f"  -> {sorted(common) if common else '(none)'}")
