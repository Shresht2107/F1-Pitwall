import os
import importlib.util
import pandas as pd

from config import (SEASONS, JOLPICA_RAW_PATH, STAGE2_OUTPUT,
                    JOLPICA_QUALIFYING_PATH, JOLPICA_STANDINGS_PATH, CIRCUITS_PATH)

# Static (year, round) → Jolpica circuit_id mapping for 2022-2024.
# Used to join circuits.csv without requiring a re-download of jolpica_raw.csv.
_ROUND_TO_CIRCUIT_ID: dict[tuple[int, int], str] = {
    (2022, 1): "bahrain",      (2022, 2): "jeddah",       (2022, 3): "albert_park",
    (2022, 4): "imola",        (2022, 5): "miami",         (2022, 6): "catalunya",
    (2022, 7): "monaco",       (2022, 8): "baku",          (2022, 9): "villeneuve",
    (2022, 10): "silverstone", (2022, 11): "red_bull_ring",(2022, 12): "paul_ricard",
    (2022, 13): "hungaroring", (2022, 14): "spa",          (2022, 15): "zandvoort",
    (2022, 16): "monza",       (2022, 17): "marina_bay",   (2022, 18): "suzuka",
    (2022, 19): "americas",    (2022, 20): "rodriguez",    (2022, 21): "interlagos",
    (2022, 22): "yas_marina",
    (2023, 1): "bahrain",      (2023, 2): "jeddah",        (2023, 3): "albert_park",
    (2023, 4): "baku",         (2023, 5): "miami",         (2023, 6): "monaco",
    (2023, 7): "catalunya",    (2023, 8): "villeneuve",    (2023, 9): "red_bull_ring",
    (2023, 10): "silverstone", (2023, 11): "hungaroring",  (2023, 12): "spa",
    (2023, 13): "zandvoort",   (2023, 14): "monza",        (2023, 15): "marina_bay",
    (2023, 16): "suzuka",      (2023, 17): "losail",       (2023, 18): "americas",
    (2023, 19): "rodriguez",   (2023, 20): "interlagos",   (2023, 21): "las_vegas",
    (2023, 22): "yas_marina",
    (2024, 1): "bahrain",      (2024, 2): "jeddah",        (2024, 3): "albert_park",
    (2024, 4): "suzuka",       (2024, 5): "shanghai",      (2024, 6): "miami",
    (2024, 7): "imola",        (2024, 8): "monaco",        (2024, 9): "villeneuve",
    (2024, 10): "catalunya",   (2024, 11): "red_bull_ring",(2024, 12): "silverstone",
    (2024, 13): "hungaroring", (2024, 14): "spa",          (2024, 15): "zandvoort",
    (2024, 16): "monza",       (2024, 17): "baku",         (2024, 18): "marina_bay",
    (2024, 19): "americas",    (2024, 20): "rodriguez",    (2024, 21): "interlagos",
    (2024, 22): "las_vegas",   (2024, 23): "losail",       (2024, 24): "yas_marina",
}

# Import Stage 1 helpers (hyphen filename → importlib)
_spec = importlib.util.spec_from_file_location(
    "feature_groups",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "feature-groups.py"),
)
_fg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fg)

get_fastf1_pace_features = _fg.get_fastf1_pace_features
get_jolpica_race_context  = _fg.get_jolpica_race_context
build_rolling_features    = _fg.build_rolling_features


def build_pace_summary(year, rounds):
    """Aggregate FastF1 clean lap data to one row per (Driver, Round, Year)."""
    all_dfs = []
    for r in rounds:
        laps = get_fastf1_pace_features(year, r)
        if laps.empty:
            continue
        # Is_Wet_Race is race-level: any clean lap recorded under rainfall
        is_wet = int(laps['Rainfall'].fillna(0).gt(0).any()) \
            if 'Rainfall' in laps.columns else 0
        summary = (
            laps.groupby("Driver")
            .agg(
                Median_FuelCorrectedLapTime=("FuelCorrectedLapTime", "median"),
                Best_FuelCorrectedLapTime=("FuelCorrectedLapTime",  "min"),
                Num_Stints=("Stint", "nunique"),
                Avg_TrackTemp=("TrackTemp", "mean"),
            )
            .reset_index()
        )
        summary["Year"]       = year
        summary["Round"]      = r
        summary["Is_Wet_Race"] = is_wet
        all_dfs.append(summary)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


if __name__ == "__main__":
    print("=== STAGE 2: DATASET ASSEMBLY  (2022–2024) ===")

    # ── 1. Jolpica context + rolling features ─────────────────────────
    if os.path.exists(JOLPICA_RAW_PATH):
        print(f"\nLoading Jolpica context from '{JOLPICA_RAW_PATH}'...")
        context_raw = pd.read_csv(JOLPICA_RAW_PATH)
    else:
        print("\nFetching Jolpica context (run collect_data.py first for speed)...")
        all_ctx = []
        for year, rounds in SEASONS.items():
            for r in rounds:
                ctx = get_jolpica_race_context(year, r)
                if not ctx.empty:
                    all_ctx.append(ctx)
        if not all_ctx:
            raise RuntimeError("No Jolpica data retrieved.")
        context_raw = pd.concat(all_ctx, ignore_index=True)

    print(f"  {len(context_raw)} Jolpica rows across "
          f"{context_raw['Year'].nunique()} seasons, "
          f"{context_raw['Round'].nunique()} unique rounds")

    context_df = build_rolling_features(context_raw)

    # ── 2. FastF1 race-level pace summary ─────────────────────────────
    print("\nAggregating FastF1 pace features per driver per round...")
    all_pace = []
    for year, rounds in SEASONS.items():
        pace = build_pace_summary(year, list(rounds))
        if not pace.empty:
            all_pace.append(pace)

    if not all_pace:
        raise RuntimeError("No FastF1 data found. Run collect_data.py first.")

    pace_summary = pd.concat(all_pace, ignore_index=True)
    print(f"  {len(pace_summary)} pace-summary rows")

    # ── 3. Qualifying delta to pole ───────────────────────────────────
    if os.path.exists(JOLPICA_QUALIFYING_PATH):
        print(f"\nMerging qualifying data from '{JOLPICA_QUALIFYING_PATH}'...")
        qualifying_df = pd.read_csv(JOLPICA_QUALIFYING_PATH)
        print(f"  {len(qualifying_df)} qualifying rows")
    else:
        print(f"\nNo qualifying CSV found at '{JOLPICA_QUALIFYING_PATH}' — run collect_data.py.")
        qualifying_df = pd.DataFrame()

    # ── 4. Pre-race championship standings ────────────────────────────
    if os.path.exists(JOLPICA_STANDINGS_PATH):
        print(f"\nMerging standings data from '{JOLPICA_STANDINGS_PATH}'...")
        standings_df = pd.read_csv(JOLPICA_STANDINGS_PATH)
        print(f"  {len(standings_df)} standings rows")
    else:
        print(f"\nNo standings CSV found at '{JOLPICA_STANDINGS_PATH}' — run collect_data.py.")
        standings_df = pd.DataFrame()

    # ── 5. Circuit lookup ─────────────────────────────────────────────
    if os.path.exists(CIRCUITS_PATH):
        print(f"\nMerging circuit data from '{CIRCUITS_PATH}'...")
        circuits_df = pd.read_csv(CIRCUITS_PATH)
    else:
        print(f"\nNo circuits CSV found at '{CIRCUITS_PATH}'.")
        circuits_df = pd.DataFrame()

    # ── 6. Assemble ───────────────────────────────────────────────────
    dataset = context_df.merge(pace_summary, on=["Year", "Round", "Driver"], how="left")

    if not qualifying_df.empty:
        dataset = dataset.merge(
            qualifying_df[["Year", "Round", "Driver", "Q_DeltaToPole", "Q_Session"]],
            on=["Year", "Round", "Driver"], how="left",
        )

    if not standings_df.empty:
        dataset = dataset.merge(
            standings_df[["Year", "Round", "Driver",
                          "Driver_Championship_Pos", "Driver_Championship_Pts",
                          "Constructor_Championship_Pos"]],
            on=["Year", "Round", "Driver"], how="left",
        )

    if not circuits_df.empty:
        dataset["CircuitId"] = dataset.apply(
            lambda r: _ROUND_TO_CIRCUIT_ID.get((int(r["Year"]), int(r["Round"]))), axis=1
        )
        dataset = dataset.merge(
            circuits_df[["circuit_id", "CircuitType", "OvertakingIndex"]],
            left_on="CircuitId", right_on="circuit_id", how="left",
        ).drop(columns=["circuit_id"])

    dataset.to_csv(STAGE2_OUTPUT, index=False)

    print(f"\nSaved {len(dataset)} rows to '{STAGE2_OUTPUT}'")
    print(f"Seasons: {sorted(dataset['Year'].unique())}")
    print(f"Rounds per season: "
          + ", ".join(f"{y}→{dataset[dataset['Year']==y]['Round'].nunique()}"
                      for y in sorted(dataset['Year'].unique())))

    preview_cols = [
        c for c in [
            "Year", "Round", "Driver", "Constructor", "GridPosition", "Position",
            "Is_DNF", "Team_Rolling_Avg_Finish", "Driver_Rolling_Avg_Points",
            "Q_DeltaToPole", "Driver_Championship_Pos", "OvertakingIndex",
            "Is_Wet_Race", "Median_FuelCorrectedLapTime", "Num_Stints",
        ] if c in dataset.columns
    ]
    print("\nSample (first 10 rows):")
    print(dataset[preview_cols].head(10).to_string(index=False))
