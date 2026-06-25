"""
One-time data collection script for the F1 Prediction + RAG pipeline.

  1. Fetches Jolpica race context (grid pos, results, points) for every race
     in the 2022-2024 regulation era and saves it to jolpica_raw.csv.
  2. Warms the FastF1 local cache so subsequent stage runs read from disk
     instead of re-downloading.

Run once before the pipeline:
    python collect_data.py

Flags:
    --jolpica-only   Skip FastF1 download (useful if FastF1 cache already warm).
    --fastf1-only    Skip Jolpica fetch (useful if jolpica_raw.csv already exists).
    --year YYYY      Restrict both downloads to a single season.
"""

import argparse
import logging
import os
import sys
import time
import importlib.util
import pandas as pd

# Suppress fastf1's verbose INFO stream; warnings/errors still show.
logging.getLogger("fastf1").setLevel(logging.WARNING)

from config import (SEASONS, JOLPICA_RAW_PATH, CACHE_DIR,
                    JOLPICA_QUALIFYING_PATH, JOLPICA_STANDINGS_PATH)

# ── load Stage 1 helpers (hyphen filename → importlib) ───────────────
_spec = importlib.util.spec_from_file_location(
    "feature_groups",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "feature-groups.py"),
)
_fg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fg)
get_fastf1_pace_features  = _fg.get_fastf1_pace_features
get_jolpica_race_context  = _fg.get_jolpica_race_context
get_jolpica_qualifying    = _fg.get_jolpica_qualifying
get_jolpica_standings     = _fg.get_jolpica_standings


# ─────────────────────────────────────────────────────────────────────
def fetch_jolpica(seasons):
    """
    Download race context for every (year, round) and return a combined DataFrame.
    Empty / error rounds are silently skipped (Jolpica returns nothing for
    rounds that don't exist in a given season).
    """
    all_rows = []
    total = sum(len(list(r)) for r in seasons.values())
    done  = 0

    for year, rounds in seasons.items():
        for r in rounds:
            ctx = get_jolpica_race_context(year, r)
            done += 1
            if not ctx.empty:
                all_rows.append(ctx)
                tag = f"OK  ({len(ctx)} drivers)"
            else:
                tag = "skipped"
            print(f"  Jolpica [{done:3d}/{total}]  {year} R{r:02d}  {tag}", flush=True)
            time.sleep(_JOLPICA_DELAY)

    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


_JOLPICA_DELAY = 1.5   # seconds between requests — Jolpica rate-limits burst requests


def fetch_qualifying(seasons):
    """Download qualifying deltas for every (year, round) and return a combined DataFrame."""
    all_rows = []
    total = sum(len(list(r)) for r in seasons.values())
    done = 0
    for year, rounds in seasons.items():
        for r in rounds:
            df = get_jolpica_qualifying(year, r)
            done += 1
            if not df.empty:
                all_rows.append(df)
                tag = f"OK  ({len(df)} drivers)"
            else:
                tag = "skipped"
            print(f"  Qualifying [{done:3d}/{total}]  {year} R{r:02d}  {tag}", flush=True)
            time.sleep(_JOLPICA_DELAY)
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


def fetch_standings(seasons):
    """Download pre-race championship standings for every (year, round)."""
    all_rows = []
    total = sum(len(list(r)) for r in seasons.values())
    done = 0
    for year, rounds in seasons.items():
        for r in rounds:
            df = get_jolpica_standings(year, r)
            done += 1
            if not df.empty:
                all_rows.append(df)
                tag = f"OK  ({len(df)} drivers)"
            else:
                tag = "skipped (R1 or no data)"
            print(f"  Standings  [{done:3d}/{total}]  {year} R{r:02d}  {tag}", flush=True)
            time.sleep(_JOLPICA_DELAY)
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


def warm_fastf1(seasons):
    """
    Load every race session through the Stage 1 pipeline to populate the local
    FastF1 cache.  Already-cached sessions load from disk in < 1 s each.
    """
    total = sum(len(list(r)) for r in seasons.values())
    done  = ok = 0

    for year, rounds in seasons.items():
        for r in rounds:
            df = get_fastf1_pace_features(year, r)
            done += 1
            if not df.empty:
                ok += 1
                tag = f"OK  ({len(df)} clean laps)"
            else:
                tag = "skipped / no data"
            print(f"  FastF1 [{done:3d}/{total}]  {year} R{r:02d}  {tag}", flush=True)

    return ok, total


# ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jolpica-only", action="store_true")
    parser.add_argument("--fastf1-only",  action="store_true")
    parser.add_argument("--year", type=int, default=None,
                        help="Restrict to a single season (e.g. --year 2023)")
    args = parser.parse_args()

    seasons = SEASONS
    if args.year:
        if args.year not in SEASONS:
            sys.exit(f"Unknown season {args.year}. Valid: {list(SEASONS)}")
        seasons = {args.year: SEASONS[args.year]}

    total_races = sum(len(list(r)) for r in seasons.values())
    season_str  = ", ".join(str(y) for y in seasons)

    print("=" * 62)
    print(f"  F1 DATA COLLECTION  —  {season_str}  (~{total_races} rounds)")
    print("=" * 62)

    # ── 1. Jolpica ────────────────────────────────────────────────────
    if not args.fastf1_only:
        print(f"\n[1/2] Fetching Jolpica race context  →  {JOLPICA_RAW_PATH}")

        existing = pd.DataFrame()
        if os.path.exists(JOLPICA_RAW_PATH):
            existing = pd.read_csv(JOLPICA_RAW_PATH)
            already  = set(zip(existing["Year"], existing["Round"]))
            seasons_jolpica = {
                y: [r for r in rnds if (y, r) not in already]
                for y, rnds in seasons.items()
            }
            skip = total_races - sum(len(v) for v in seasons_jolpica.values())
            if skip:
                print(f"  {skip} rounds already in CSV — downloading the rest only.")
        else:
            seasons_jolpica = seasons

        new_data = fetch_jolpica(seasons_jolpica)

        if not new_data.empty:
            combined = pd.concat([existing, new_data], ignore_index=True) \
                       if not existing.empty else new_data
            combined.to_csv(JOLPICA_RAW_PATH, index=False)
            print(f"  → {JOLPICA_RAW_PATH}  ({len(combined)} total rows)")
        else:
            print("  → No new Jolpica data retrieved.")

    # ── 2. Qualifying ─────────────────────────────────────────────────
    if not args.fastf1_only:
        print(f"\n[2/4] Fetching qualifying times  →  {JOLPICA_QUALIFYING_PATH}")

        existing_q = pd.DataFrame()
        if os.path.exists(JOLPICA_QUALIFYING_PATH):
            existing_q = pd.read_csv(JOLPICA_QUALIFYING_PATH)
            already_q = set(zip(existing_q["Year"], existing_q["Round"]))
            seasons_q = {
                y: [r for r in rnds if (y, r) not in already_q]
                for y, rnds in seasons.items()
            }
            skip_q = total_races - sum(len(v) for v in seasons_q.values())
            if skip_q:
                print(f"  {skip_q} rounds already in CSV — downloading the rest only.")
        else:
            seasons_q = seasons

        new_q = fetch_qualifying(seasons_q)
        if not new_q.empty:
            combined_q = pd.concat([existing_q, new_q], ignore_index=True) \
                         if not existing_q.empty else new_q
            combined_q.to_csv(JOLPICA_QUALIFYING_PATH, index=False)
            print(f"  → {JOLPICA_QUALIFYING_PATH}  ({len(combined_q)} total rows)")
        else:
            print("  → No new qualifying data retrieved.")

    # ── 3. Championship standings ──────────────────────────────────────
    if not args.fastf1_only:
        print(f"\n[3/4] Fetching championship standings  →  {JOLPICA_STANDINGS_PATH}")

        existing_s = pd.DataFrame()
        if os.path.exists(JOLPICA_STANDINGS_PATH):
            existing_s = pd.read_csv(JOLPICA_STANDINGS_PATH)
            already_s = set(zip(existing_s["Year"], existing_s["Round"]))
            seasons_s = {
                y: [r for r in rnds if (y, r) not in already_s]
                for y, rnds in seasons.items()
            }
            skip_s = total_races - sum(len(v) for v in seasons_s.values())
            if skip_s:
                print(f"  {skip_s} rounds already in CSV — downloading the rest only.")
        else:
            seasons_s = seasons

        new_s = fetch_standings(seasons_s)
        if not new_s.empty:
            combined_s = pd.concat([existing_s, new_s], ignore_index=True) \
                         if not existing_s.empty else new_s
            combined_s.to_csv(JOLPICA_STANDINGS_PATH, index=False)
            print(f"  → {JOLPICA_STANDINGS_PATH}  ({len(combined_s)} total rows)")
        else:
            print("  → No new standings data retrieved.")

    # ── 4. FastF1 cache ───────────────────────────────────────────────
    if not args.jolpica_only:
        print(f"\n[4/4] Warming FastF1 cache  →  {CACHE_DIR}/")
        ok, total = warm_fastf1(seasons)
        print(f"  → {ok}/{total} sessions cached")

    print("\n" + "=" * 62)
    print("  Collection done. Run the pipeline:")
    print("    python stage2.py")
    print("    python regressor.py")
    print("    python stage4.py")
    print("=" * 62)


if __name__ == "__main__":
    main()
