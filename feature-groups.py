import os
import requests
import pandas as pd
import numpy as np
import fastf1

# 1. SETUP & CACHING
# Create a local cache directory so you don't download gigabytes of telemetry repeatedly
CACHE_DIR = './fastf1_cache'
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)


def get_fastf1_pace_features(year, round_num):
    """
    Pulls lap-by-lap data, filters out laps that don't represent clean
    racing pace, merges weather using merge_asof, and calculates fuel correction.
    """
    print(f"Fetching FastF1 data for {year} Round {round_num}...")
    try:
        session = fastf1.get_session(year, round_num, 'R')
        session.load(laps=True, telemetry=False, weather=True, messages=False)
    except Exception as e:
        print(f"Error loading session: {e}")
        return pd.DataFrame()

    raw_laps = session.laps.copy()
    weather = session.weather_data.copy()

    if raw_laps.empty:
        print(f"No lap data returned for {year} Round {round_num}.")
        return pd.DataFrame()

    # FIX: capture total race distance from the *raw* lap list before any
    # filtering. If we computed this after dropping SC/red-flag-affected
    # laps near the end of the race, we'd underestimate total_laps and
    # throw off the fuel-burn calculation below.
    total_laps = raw_laps['LapNumber'].max()

    laps = raw_laps.copy()
    laps['LapTimeSeconds'] = laps['LapTime'].dt.total_seconds()
    laps = laps.dropna(subset=['LapTimeSeconds']).reset_index(drop=True)

    # ------------------------------------------------------------------
    # FIX: drop laps that don't represent clean tire/fuel-driven pace.
    # Without this, safety car / VSC / red flag laps and in/out laps
    # (slow or fast for reasons that have nothing to do with tire
    # degradation) get treated as if they were normal racing laps.
    #   - TrackStatus == '1'      -> no flag of any kind was active
    #   - PitInTime/PitOutTime    -> both null means not an in-lap/out-lap
    #   - Deleted == False        -> lap time wasn't struck off by stewards
    #   - IsAccurate == True      -> FastF1's own timing-integrity check passed
    # (Newer FastF1 versions also expose convenience wrappers like
    # pick_track_status() / pick_wo_box() that do the same thing.)
    # ------------------------------------------------------------------
    n_before = len(laps)
    clean_mask = (
        (laps['TrackStatus'] == '1') &
        laps['PitInTime'].isna() &
        laps['PitOutTime'].isna() &
        (~laps['Deleted'].fillna(False)) &
        (laps['IsAccurate'].fillna(False))
    )
    laps = laps[clean_mask].reset_index(drop=True)
    n_after = len(laps)
    print(f"  Kept {n_after}/{n_before} laps after removing SC/VSC/red-flag, "
          f"in/out, deleted, and inaccurate laps.")

    if laps.empty:
        print(f"  No clean laps remained for {year} Round {round_num}.")
        return pd.DataFrame()

    # Clean up timestamps for the merge_asof
    laps['TimeSeconds'] = laps['Time'].dt.total_seconds()
    weather['TimeSeconds'] = weather['Time'].dt.total_seconds()

    laps = laps.sort_values('TimeSeconds')
    weather = weather.sort_values('TimeSeconds')

    # Align continuous weather data to discrete laps
    laps_with_weather = pd.merge_asof(
        laps,
        weather[['TimeSeconds', 'TrackTemp', 'AirTemp', 'Rainfall']],
        on='TimeSeconds',
        direction='backward'
    )

    # Fuel correction logic (same approximation as before, now driven by
    # the pre-filtering total_laps captured above)
    FUEL_PENALTY_PER_KG = 0.03
    INITIAL_FUEL_KG = 110.0

    laps_with_weather['EstimatedFuelLeft'] = INITIAL_FUEL_KG * (1 - (laps_with_weather['LapNumber'] / total_laps))
    laps_with_weather['FuelCorrectionDelta'] = laps_with_weather['EstimatedFuelLeft'] * FUEL_PENALTY_PER_KG
    laps_with_weather['FuelCorrectedLapTime'] = laps_with_weather['LapTimeSeconds'] - laps_with_weather['FuelCorrectionDelta']

    strategy_df = laps_with_weather[[
        'Driver', 'LapNumber', 'Stint', 'Compound', 'TyreLife',
        'TrackTemp', 'FuelCorrectedLapTime', 'LapTimeSeconds', 'Rainfall'
    ]].copy()
    strategy_df['Rainfall'] = strategy_df['Rainfall'].fillna(0)

    strategy_df['Year'] = year
    strategy_df['Round'] = round_num

    return strategy_df


def get_jolpica_race_context(year, round_num):
    """
    Queries the Jolpica-F1 API (Ergast successor) for race context data.
    """
    print(f"Fetching Jolpica-F1 context for {year} Round {round_num}...")
    url = f"https://api.jolpi.ca/ergast/f1/{year}/{round_num}/results.json"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        race_data = data['MRData']['RaceTable']['Races'][0]
        results = race_data['Results']
    except Exception as e:
        print(f"Error calling Jolpica API: {e}")
        return pd.DataFrame()

    context_records = []
    for row in results:
        grid_pos = int(row['grid'])

        # FIX: derive DNF status from the 'status' field instead of guessing
        # from 'position'. Ergast/Jolpica's 'status' is "Finished" or
        # "+N Lap(s)" for classified finishers, and a retirement reason
        # (e.g. "Retired", "Accident", "Engine", "Disqualified") otherwise.
        status = row.get('status', '')
        is_dnf = 0 if (status == 'Finished' or status.startswith('+')) else 1

        # FIX: no more hardcoded fallback of 20. If 'position' genuinely
        # isn't a parseable number, leave it as NaN - Is_DNF (above) is now
        # the explicit signal, and downstream code decides how to treat it,
        # rather than silently injecting a fake "finished 20th".
        position = int(row['position']) if row['position'].isdigit() else np.nan

        record = {
            'Year': year,
            'Round': round_num,
            'Driver': row['Driver']['code'],
            'Constructor': row['Constructor']['constructorId'],
            'GridPosition': grid_pos,
            'Position': position,
            'Is_DNF': is_dnf,
            'Points': float(row['points'])
        }
        context_records.append(record)

    df = pd.DataFrame(context_records)
    return df


def get_jolpica_qualifying(year, round_num):
    """
    Fetches Q1/Q2/Q3 times for every driver from the Jolpica qualifying endpoint.
    Returns Q_DeltaToPole = driver's best time (highest session reached) minus
    pole time in seconds.  Drivers knocked out in Q1/Q2 naturally carry a larger
    delta, which is a meaningful signal rather than noise.
    Returns an empty DataFrame on any API or parse error.
    """
    url = f"https://api.jolpi.ca/ergast/f1/{year}/{round_num}/qualifying.json"
    try:
        response = requests.get(url, timeout=10)
        if not response.content:
            return pd.DataFrame()
        data = response.json()
        quali_results = data['MRData']['RaceTable']['Races'][0]['QualifyingResults']
    except Exception as e:
        print(f"  Qualifying fetch error {year} R{round_num}: {e}")
        return pd.DataFrame()

    def _parse_laptime(t):
        """Convert 'M:SS.mmm' or 'SS.mmm' string to float seconds."""
        if not t or not t.strip():
            return None
        t = t.strip()
        try:
            if ':' in t:
                m, s = t.split(':', 1)
                return int(m) * 60 + float(s)
            return float(t)
        except ValueError:
            return None

    records = []
    for row in quali_results:
        best_s, q_session = None, None
        for session in ('Q3', 'Q2', 'Q1'):
            t = _parse_laptime(row.get(session, ''))
            if t is not None:
                best_s = t
                q_session = session
                break
        if best_s is None:
            continue
        records.append({
            'Year': year,
            'Round': round_num,
            'Driver': row['Driver']['code'],
            'Q_BestTime_s': best_s,
            'Q_Session': q_session,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    pole_time = df['Q_BestTime_s'].min()
    df['Q_DeltaToPole'] = df['Q_BestTime_s'] - pole_time
    return df[['Year', 'Round', 'Driver', 'Q_DeltaToPole', 'Q_Session']]


def get_jolpica_standings(year, round_num):
    """
    Returns championship standings going INTO round_num, i.e. after round_num-1.
    Makes two API calls: driverstandings + constructorstandings.
    Returns an empty DataFrame for round 1 (no prior standings available).

    Columns: Year, Round, Driver, Driver_Championship_Pos, Driver_Championship_Pts,
             Constructor_Championship_Pos
    """
    if round_num == 1:
        return pd.DataFrame()

    prev = round_num - 1

    # ── constructor standings ─────────────────────────────────────────
    constructor_pos: dict[str, int] = {}
    try:
        url = f"https://api.jolpi.ca/ergast/f1/{year}/{prev}/constructorstandings.json"
        resp = requests.get(url, timeout=10)
        if resp.content:
            lists = resp.json()['MRData']['StandingsTable']['StandingsLists']
            if lists:
                for row in lists[0]['ConstructorStandings']:
                    constructor_pos[row['Constructor']['constructorId']] = int(row.get('position', 0))
    except Exception as e:
        print(f"  Constructor standings error {year} R{round_num}: {e}")

    # ── driver standings ──────────────────────────────────────────────
    records = []
    try:
        url = f"https://api.jolpi.ca/ergast/f1/{year}/{prev}/driverstandings.json"
        resp = requests.get(url, timeout=10)
        if resp.content:
            lists = resp.json()['MRData']['StandingsTable']['StandingsLists']
            if lists:
                for row in lists[0]['DriverStandings']:
                    constructor_id = row['Constructors'][0]['constructorId'] \
                        if row.get('Constructors') else None
                    records.append({
                        'Year': year,
                        'Round': round_num,
                        'Driver': row['Driver']['code'],
                        'Driver_Championship_Pos': int(row.get('position', 0)),
                        'Driver_Championship_Pts': float(row.get('points', 0)),
                        'Constructor_Championship_Pos': constructor_pos.get(constructor_id, np.nan),
                    })
    except Exception as e:
        print(f"  Driver standings error {year} R{round_num}: {e}")

    return pd.DataFrame(records) if records else pd.DataFrame()


def build_rolling_features(historical_df):
    """
    Computes rolling momentum metrics across multiple races without leaking data.
    """
    if historical_df.empty:
        return historical_df

    # Sort chronologically to prevent data leakage in windows
    historical_df = historical_df.sort_values(['Year', 'Round']).reset_index(drop=True)

    # ------------------------------------------------------------------
    # FIX: Team_Rolling_Avg_Finish granularity.
    # Jolpica returns one row per *driver*, so each constructor has 2 rows
    # per round. Rolling directly on historical_df with window=3 averaged
    # the last 3 driver-ROWS (~1.5 rounds), not the last 3 races. Aggregate
    # to one row per (Year, Round, Constructor) first, using only rows
    # where the car actually finished (Is_DNF == 0) - a round where both
    # cars retired shouldn't be averaged in as if it were a finish.
    # ------------------------------------------------------------------
    finishers = historical_df[historical_df['Is_DNF'] == 0]

    team_round_avg = (
        finishers.groupby(['Year', 'Round', 'Constructor'], as_index=False)['Position']
        .mean()
        .rename(columns={'Position': 'Team_Round_Avg_Position'})
        .sort_values(['Year', 'Round'])
        .reset_index(drop=True)
    )

    team_round_avg['Team_Rolling_Avg_Finish'] = (
        team_round_avg.groupby('Constructor')['Team_Round_Avg_Position']
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
    )

    historical_df = historical_df.merge(
        team_round_avg[['Year', 'Round', 'Constructor', 'Team_Rolling_Avg_Finish']],
        on=['Year', 'Round', 'Constructor'],
        how='left'
    )

    # Bonus, using the same Is_DNF flag and the same leak-safe shift-then-roll
    # pattern: a team's recent reliability. Not explicitly requested, but a
    # natural way to "treat DNFs separately" rather than just excluding them.
    team_dnf_rate = (
        historical_df.groupby(['Year', 'Round', 'Constructor'], as_index=False)['Is_DNF']
        .mean()
        .rename(columns={'Is_DNF': 'Team_Round_DNF_Rate'})
        .sort_values(['Year', 'Round'])
        .reset_index(drop=True)
    )
    team_dnf_rate['Team_Rolling_DNF_Rate'] = (
        team_dnf_rate.groupby('Constructor')['Team_Round_DNF_Rate']
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
    )
    historical_df = historical_df.merge(
        team_dnf_rate[['Year', 'Round', 'Constructor', 'Team_Rolling_DNF_Rate']],
        on=['Year', 'Round', 'Constructor'],
        how='left'
    )

    # Driver's rolling average points: already 1 row per driver per round,
    # so no granularity fix needed here. DNFs naturally contribute 0 points.
    historical_df['Driver_Rolling_Avg_Points'] = historical_df.groupby('Driver')['Points']\
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())

    return historical_df


# ==========================================
# PIPELINE EXECUTION EXAMPLE
# ==========================================
if __name__ == "__main__":
    YEAR = 2024

    # 1. FastF1 pace features for a single race - check the "Kept X/Y laps"
    # line in the output to confirm the new clean-lap filter is working.
    ROUND_FOR_PACE_CHECK = 14  # Belgian GP
    pace_features = get_fastf1_pace_features(YEAR, ROUND_FOR_PACE_CHECK)

    print("\n--- STAGE 1: TIRE & PACE FEATURES (FASTF1) ---")
    print(pace_features.head())

    # 2. Jolpica context across several consecutive rounds, so the rolling
    # features actually have history to look back on - this is what lets
    # you verify the Team_Rolling_Avg_Finish granularity fix.
    ROUNDS_TO_PULL = [1, 2, 3, 4, 5]
    all_context = []
    for r in ROUNDS_TO_PULL:
        round_context = get_jolpica_race_context(YEAR, r)
        if not round_context.empty:
            all_context.append(round_context)

    if all_context:
        context_features = pd.concat(all_context, ignore_index=True)
        context_features = build_rolling_features(context_features)

        print("\n--- STAGE 1: RACE CONTEXT FEATURES (JOLPICA) ---")
        cols_to_show = [
            'Year', 'Round', 'Driver', 'Constructor', 'GridPosition', 'Position',
            'Is_DNF', 'Team_Rolling_Avg_Finish', 'Team_Rolling_DNF_Rate', 'Driver_Rolling_Avg_Points'
        ]
        print(context_features[cols_to_show].sort_values(['Constructor', 'Round']).to_string(index=False))
    else:
        print("No Jolpica context data was retrieved.")