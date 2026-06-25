import os
import importlib.util
import pandas as pd
import numpy as np
import fastf1
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error

# =====================================================================
# SETUP
# =====================================================================
CACHE_DIR = './fastf1_cache'
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# Import Stage 1 helpers. The filename has a hyphen so importlib is needed.
_spec = importlib.util.spec_from_file_location(
    "feature_groups",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "feature-groups.py")
)
_fg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fg)
get_fastf1_pace_features = _fg.get_fastf1_pace_features

COMPOUND_MAP = {'SOFT': 0, 'MEDIUM': 1, 'HARD': 2}

# Canonical strategy templates defined as (compound_code, laps) stints.
# These are scaled per race in compute_pace_deltas().
CANONICAL_TEMPLATES = [
    [(1, 15), (2, 29)],           # One-stop:  MEDIUM → HARD
    [(0, 10), (1, 17), (2, 17)],  # Two-stop:  SOFT → MEDIUM → HARD
]


# =====================================================================
# STRATEGY HELPERS
# =====================================================================
def get_driver_strategies(year, round_num):
    """
    Extract per-driver tire stint sequences from raw FastF1 lap data.
    Returns ({driver: [(compound_code, laps), ...]}, total_laps).
    """
    try:
        session = fastf1.get_session(year, round_num, 'R')
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps.copy()
        total_laps = int(laps['LapNumber'].max())

        strategies = {}
        for driver, dlaps in laps.groupby('Driver'):
            dlaps = dlaps.sort_values('LapNumber')
            dry = dlaps[dlaps['Compound'].isin(COMPOUND_MAP)]
            if dry.empty:
                continue
            stints = []
            for _, stint_data in dry.groupby('Stint'):
                compound = stint_data['Compound'].mode()[0]
                stints.append((COMPOUND_MAP[compound], len(stint_data)))
            if stints:
                strategies[driver] = stints
        return strategies, total_laps
    except Exception as e:
        print(f"  Skipping strategy extraction for {year} R{round_num}: {e}")
        return {}, 0


def scale_stints(template_stints, total_laps):
    """Scale template stints proportionally to fill total_laps exactly."""
    template_total = sum(n for _, n in template_stints)
    scaled = []
    accumulated = 0
    for i, (compound, laps) in enumerate(template_stints):
        if i == len(template_stints) - 1:
            scaled.append((compound, total_laps - accumulated))
        else:
            n = round(laps * total_laps / template_total)
            scaled.append((compound, n))
            accumulated += n
    return scaled


def simulate_race_strategy(regressor, stints, total_laps, track_temp=35.0,
                            simulations=500, noise_std=0.25):
    """
    Monte Carlo race simulation using a list-of-stints strategy.

    FIX: pit stops are derived from stint boundaries, not compound changes.
    This means same-compound back-to-back stints (e.g. MEDIUM → MEDIUM)
    correctly register a pit stop.

    stints      : [(compound_code, num_laps), ...]
    Returns     : array of total race times, shape (simulations,)
    """
    PIT_STOP_LOSS = 22.0

    # Build per-lap arrays and record which laps begin a new stint (= pit stop lap)
    compound_per_lap = []
    stint_per_lap = []
    tyre_life_per_lap = []
    pit_laps = set()

    for stint_idx, (compound, laps) in enumerate(stints):
        if stint_idx > 0:
            pit_laps.add(len(compound_per_lap) + 1)  # 1-indexed lap of pit stop
        tl = 1
        for _ in range(laps):
            compound_per_lap.append(compound)
            stint_per_lap.append(stint_idx + 1)
            tyre_life_per_lap.append(tl)
            tl += 1

    feature_df = pd.DataFrame({
        'LapNumber':   range(1, total_laps + 1),
        'Stint':       stint_per_lap,
        'CompoundCode': compound_per_lap,
        'TyreLife':    tyre_life_per_lap,
        'TrackTemp':   track_temp,
    })

    # Predict all lap base-times in one call (vectorised — no Python loop needed)
    base_times = regressor.predict(feature_df)
    race_base = float(base_times.sum()) + PIT_STOP_LOSS * len(pit_laps)

    # Race-level noise: sum of total_laps i.i.d. N(0, noise_std²) terms
    race_std = noise_std * np.sqrt(total_laps)
    return np.random.normal(race_base, race_std, simulations)


def compute_pace_deltas(regressor, seasons, simulations=500):
    """
    For every (year, round, driver) across all provided seasons: simulate the
    driver's actual race strategy and compare against the best canonical strategy.

    Expected_Pace_Delta = driver_strategy_median - optimal_canonical_median

    Negative  → driver's strategy is faster than the canonical benchmark (good)
    Positive  → driver's strategy is slower                               (bad)

    seasons: dict  {year: iterable_of_round_numbers}
    """
    records = []
    for year, rounds in seasons.items():
        for round_num in rounds:
            print(f"  Pace deltas — {year} R{round_num:02d}...", flush=True)
            strategies, total_laps = get_driver_strategies(year, round_num)
            if not strategies or total_laps == 0:
                continue

            pace_df = get_fastf1_pace_features(year, round_num)
            track_temp = float(pace_df['TrackTemp'].mean()) if not pace_df.empty else 35.0

            # Optimal canonical benchmark for this race distance
            canonical_medians = []
            for template in CANONICAL_TEMPLATES:
                stints = scale_stints(template, total_laps)
                results = simulate_race_strategy(regressor, stints, total_laps,
                                                 track_temp, simulations)
                canonical_medians.append(float(np.median(results)))
            optimal = min(canonical_medians)

            # Per-driver delta
            for driver, stints in strategies.items():
                current_total = sum(n for _, n in stints)
                if current_total != total_laps and stints:
                    stints = list(stints)
                    diff = total_laps - current_total
                    stints[-1] = (stints[-1][0], max(1, stints[-1][1] + diff))

                results = simulate_race_strategy(regressor, stints, total_laps,
                                                 track_temp, simulations)
                delta = float(np.median(results)) - optimal
                records.append({
                    'Year': year, 'Round': round_num,
                    'Driver': driver, 'Expected_Pace_Delta': delta,
                })

    return pd.DataFrame(records)


if __name__ == "__main__":
    from config import SEASONS, TRAIN_YEARS, TEST_YEAR, PACE_DELTAS_OUTPUT

    features = ['LapNumber', 'Stint', 'CompoundCode', 'TyreLife', 'TrackTemp']
    target   = 'FuelCorrectedLapTime'

    # =====================================================================
    # 1. LOAD TRAINING DATA  (TRAIN_YEARS only — clean separation from TEST_YEAR)
    # =====================================================================
    print("=== STAGE 3: LAP-TIME REGRESSOR  (2022–2024) ===")
    print(f"Loading lap data for training seasons {TRAIN_YEARS}...")

    train_dfs = []
    for year in TRAIN_YEARS:
        for r in SEASONS[year]:
            df = get_fastf1_pace_features(year, r)
            if not df.empty:
                train_dfs.append(df)

    train_master = pd.concat(train_dfs, ignore_index=True)
    train_master = train_master[train_master['Compound'].isin(COMPOUND_MAP)]
    train_master['CompoundCode'] = train_master['Compound'].map(COMPOUND_MAP)
    train_master = train_master.dropna(subset=['TrackTemp', 'FuelCorrectedLapTime'])

    print(f"Training set: {len(train_master)} clean laps  |  "
          f"{train_master['Year'].nunique()} seasons  |  "
          f"{train_master['Round'].nunique()} rounds")

    # =====================================================================
    # 2. LOAD EVAL DATA  (TEST_YEAR — never touches training)
    # =====================================================================
    print(f"\nLoading held-out evaluation data for {TEST_YEAR}...")
    eval_dfs = []
    for r in SEASONS[TEST_YEAR]:
        df = get_fastf1_pace_features(TEST_YEAR, r)
        if not df.empty:
            eval_dfs.append(df)

    eval_master = pd.concat(eval_dfs, ignore_index=True) if eval_dfs else pd.DataFrame()
    if not eval_master.empty:
        eval_master = eval_master[eval_master['Compound'].isin(COMPOUND_MAP)]
        eval_master['CompoundCode'] = eval_master['Compound'].map(COMPOUND_MAP)
        eval_master = eval_master.dropna(subset=['TrackTemp', 'FuelCorrectedLapTime'])
        print(f"Eval set:     {len(eval_master)} clean laps  |  "
              f"{eval_master['Round'].nunique()} rounds")

    # =====================================================================
    # 3. TRAIN REGRESSOR
    # =====================================================================
    print("\nTraining XGBoost Lap-Time Regressor...")
    regressor = XGBRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=5,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
    )
    regressor.fit(train_master[features], train_master[target])

    if not eval_master.empty:
        mae = mean_absolute_error(eval_master[target], regressor.predict(eval_master[features]))
        print(f"MAE on {TEST_YEAR} (held-out): {mae:.4f} seconds")

    # =====================================================================
    # 4. COMPUTE PER-DRIVER EXPECTED PACE DELTA ACROSS ALL SEASONS
    # =====================================================================
    print(f"\nRunning Monte Carlo simulations across all seasons...")
    pace_deltas = compute_pace_deltas(regressor, SEASONS)

    pace_deltas.to_csv(PACE_DELTAS_OUTPUT, index=False)
    print(f"\nSaved {len(pace_deltas)} driver-race rows to '{PACE_DELTAS_OUTPUT}'")
    print(f"Seasons covered: {sorted(pace_deltas['Year'].unique())}")
    print(pace_deltas.head(10).to_string(index=False))
