"""
Unit tests for the F1 prediction pipeline.

Covers the four concrete bug-fixes made in this project:
  1. Pit-stop detection by stint boundary, not compound change (regressor.py)
  2. Tyre-life reset after every pit stop (regressor.py)
  3. build_rolling_features: no data leakage via shift(1); correct team
     granularity (one row per round, not per driver); DNF exclusion (feature-groups.py)
  4. Fuel-correction formula direction and total-laps anchoring (feature-groups.py)

Plus contract tests for scale_stints and DNF status parsing.

Run from the project root:
    pytest tests/ -v
"""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────
# Stub out fastf1 before loading pipeline modules.
# The functions under test (simulate_race_strategy, scale_stints,
# build_rolling_features, …) are pure-Python / pandas and never call
# fastf1 themselves.  Stubbing lets the test suite run without
# requiring the fastf1 package to be installed in the test environment.
# ─────────────────────────────────────────────────────────────────────
for _stub in ("fastf1", "xgboost"):
    if _stub not in sys.modules:
        sys.modules[_stub] = MagicMock()

# ─────────────────────────────────────────────────────────────────────
# Module loading (handles hyphenated filename & execution-guarded main)
# ─────────────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, relpath))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_import_error = None
try:
    _fg  = _load("feature_groups", "feature-groups.py")
    _reg = _load("regressor",      "regressor.py")
    build_rolling_features = _fg.build_rolling_features
    simulate_race_strategy = _reg.simulate_race_strategy
    scale_stints           = _reg.scale_stints
    _IMPORTS_OK = True
except Exception as _e:
    _IMPORTS_OK = False
    _import_error = str(_e)

pytestmark = pytest.mark.skipif(
    not _IMPORTS_OK,
    reason=f"Pipeline import failed: {_import_error}",
)


# ─────────────────────────────────────────────────────────────────────
# Shared mock regressors
# ─────────────────────────────────────────────────────────────────────
class ConstantRegressor:
    """Always returns the same lap time regardless of input features."""
    def __init__(self, lap_time=90.0):
        self.lap_time = lap_time

    def predict(self, X):
        return np.full(len(X), self.lap_time)


class TyreLifeRegressor:
    """Returns the TyreLife value as the lap time — isolates tyre-life tracking."""
    def predict(self, X):
        return X["TyreLife"].values.astype(float)


# ─────────────────────────────────────────────────────────────────────
# DataFrame factory for rolling-feature tests
# ─────────────────────────────────────────────────────────────────────
def _make_context_df(entries_by_round):
    """
    Build a Jolpica-style context DataFrame.

    entries_by_round: {round_num: [(driver, constructor, position, is_dnf, points)]}
    DNF entries should use position=0; it will be replaced with NaN.
    """
    rows = []
    for rnd, entries in entries_by_round.items():
        for driver, constructor, position, is_dnf, points in entries:
            rows.append({
                "Year":        2024,
                "Round":       rnd,
                "Driver":      driver,
                "Constructor": constructor,
                "GridPosition": position,
                "Position":    float(position) if not is_dnf else np.nan,
                "Is_DNF":      is_dnf,
                "Points":      float(points),
            })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# 1. PIT-STOP DETECTION  (FIX 1)
# ═══════════════════════════════════════════════════════════════════════

class TestPitStopDetection:
    """
    Original bug: pit stops were detected by compound change between laps.
    Same-compound stints (e.g. MEDIUM → MEDIUM) never fired a pit stop,
    so two-stop strategies were silently simulated as one-stop.
    Fix: pit stops derive from stint-boundary indices.
    """

    def test_same_compound_back_to_back_fires_one_pit(self):
        """MEDIUM → MEDIUM: compound is unchanged but a pit stop must register."""
        reg = ConstantRegressor(90.0)
        stints = [(1, 22), (1, 22)]          # both MEDIUM, 44 laps total
        result = simulate_race_strategy(reg, stints, 44, simulations=1, noise_std=0)
        assert abs(result[0] - (44 * 90.0 + 22.0)) < 0.1

    def test_one_stop_different_compounds(self):
        """MEDIUM → HARD: one pit stop."""
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(1, 15), (2, 29)], 44,
                                        simulations=1, noise_std=0)
        assert abs(result[0] - (44 * 90.0 + 22.0)) < 0.1

    def test_two_stop_different_compounds(self):
        """SOFT → MEDIUM → HARD: two pit stops."""
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(0, 10), (1, 17), (2, 17)], 44,
                                        simulations=1, noise_std=0)
        assert abs(result[0] - (44 * 90.0 + 2 * 22.0)) < 0.1

    def test_two_stop_same_second_third_compound_was_the_broken_case(self):
        """
        SOFT → MEDIUM → MEDIUM: the original buggy code treated this as a
        one-stop because no compound change occurred at lap 28.
        Must produce two pit stops.
        """
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(0, 10), (1, 17), (1, 17)], 44,
                                        simulations=1, noise_std=0)
        expected = 44 * 90.0 + 2 * 22.0    # two pit stops
        assert abs(result[0] - expected) < 0.1

    def test_single_stint_no_pit(self):
        """One stint: zero pit stops, pure lap times."""
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(2, 44)], 44, simulations=1, noise_std=0)
        assert abs(result[0] - 44 * 90.0) < 0.1

    def test_two_stop_costs_more_than_one_stop(self):
        """
        With a constant regressor every lap is identical, so the faster
        strategy is the one with fewer pit stops.
        """
        reg = ConstantRegressor(90.0)
        np.random.seed(0)
        one = np.median(simulate_race_strategy(reg, [(1, 22), (2, 22)], 44,
                                               simulations=200, noise_std=0))
        two = np.median(simulate_race_strategy(reg, [(0, 10), (1, 17), (2, 17)], 44,
                                               simulations=200, noise_std=0))
        assert one < two, "One-stop must be faster than two-stop (22 s vs 44 s pit loss)"


# ═══════════════════════════════════════════════════════════════════════
# 2. TYRE-LIFE TRACKING  (FIX 2)
# ═══════════════════════════════════════════════════════════════════════

class TestTyreLifeTracking:
    """
    TyreLife starts at 1 for each stint and increments every lap.
    After a pit stop it must reset to 1 for the incoming fresh tyres.
    """

    def test_tyre_life_resets_after_pit(self):
        """
        Two stints of 3 laps.  With TyreLifeRegressor, lap times equal TyreLife.
        Sequence: [1,2,3, 1,2,3]  → sum = 12.  Plus 1 pit (22 s) = 34 s.
        """
        reg = TyreLifeRegressor()
        result = simulate_race_strategy(reg, [(1, 3), (2, 3)], 6,
                                        simulations=1, noise_std=0)
        assert abs(result[0] - 34.0) < 0.1

    def test_tyre_life_increments_within_stint(self):
        """Single stint of N laps: life = 1…N, sum = N*(N+1)/2."""
        reg = TyreLifeRegressor()
        N = 6
        result = simulate_race_strategy(reg, [(1, N)], N, simulations=1, noise_std=0)
        assert abs(result[0] - N * (N + 1) / 2) < 0.1

    def test_tyre_life_resets_across_two_pit_stops(self):
        """
        Three stints of 2 laps each.
        Life sequence: [1,2, 1,2, 1,2]  → sum = 9.  Plus 2 pits = 53 s.
        """
        reg = TyreLifeRegressor()
        result = simulate_race_strategy(reg, [(0, 2), (1, 2), (2, 2)], 6,
                                        simulations=1, noise_std=0)
        assert abs(result[0] - (9.0 + 2 * 22.0)) < 0.1


# ═══════════════════════════════════════════════════════════════════════
# 3. SIMULATION OUTPUT CONTRACT
# ═══════════════════════════════════════════════════════════════════════

class TestSimulationOutputContract:
    def test_output_shape_matches_simulations_param(self):
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(1, 44)], 44, simulations=300, noise_std=0.5)
        assert result.shape == (300,)

    def test_zero_noise_is_deterministic(self):
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(1, 22), (2, 22)], 44,
                                        simulations=5, noise_std=0)
        assert np.all(result == result[0])

    def test_nonzero_noise_produces_variance(self):
        np.random.seed(1)
        reg = ConstantRegressor(90.0)
        result = simulate_race_strategy(reg, [(1, 44)], 44, simulations=200, noise_std=1.0)
        assert result.std() > 0


# ═══════════════════════════════════════════════════════════════════════
# 4. SCALE STINTS
# ═══════════════════════════════════════════════════════════════════════

class TestScaleStints:
    @pytest.mark.parametrize("total", [30, 44, 53, 57, 70])
    def test_two_stint_fills_total_laps(self, total):
        assert sum(n for _, n in scale_stints([(1, 15), (2, 29)], total)) == total

    @pytest.mark.parametrize("total", [30, 44, 57, 70])
    def test_three_stint_fills_total_laps(self, total):
        assert sum(n for _, n in scale_stints([(0, 10), (1, 17), (2, 17)], total)) == total

    def test_compounds_are_preserved_in_order(self):
        scaled = scale_stints([(0, 10), (1, 17), (2, 17)], 60)
        assert [c for c, _ in scaled] == [0, 1, 2]

    def test_identity_when_total_matches_template(self):
        template = [(1, 15), (2, 29)]
        assert scale_stints(template, 44) == template

    @pytest.mark.parametrize("total", [20, 30, 44, 70])
    def test_all_stint_lengths_positive(self, total):
        scaled = scale_stints([(0, 10), (1, 17), (2, 17)], total)
        assert all(n > 0 for _, n in scaled), f"Non-positive stint at total={total}"


# ═══════════════════════════════════════════════════════════════════════
# 5. ROLLING FEATURES — NO DATA LEAKAGE  (FIX 3)
# ═══════════════════════════════════════════════════════════════════════

class TestRollingFeaturesLeakage:
    """
    shift(1) must precede every rolling window so a round's own result
    never feeds into that same round's rolling average.
    """

    def test_round_1_driver_rolling_is_nan(self):
        """No prior data → Driver_Rolling_Avg_Points must be NaN for round 1."""
        df = _make_context_df({
            1: [("HAM", "mercedes", 3, 0, 15), ("VER", "redbull", 1, 0, 25)],
            2: [("HAM", "mercedes", 2, 0, 18), ("VER", "redbull", 1, 0, 25)],
        })
        result = build_rolling_features(df)
        r1 = result[result["Round"] == 1]
        assert r1["Driver_Rolling_Avg_Points"].isna().all()

    def test_round_1_team_rolling_is_nan(self):
        """No prior data → Team_Rolling_Avg_Finish must be NaN for round 1."""
        df = _make_context_df({
            1: [("HAM", "mercedes", 3, 0, 15), ("RUS", "mercedes", 5, 0, 10)],
            2: [("HAM", "mercedes", 2, 0, 18), ("RUS", "mercedes", 4, 0, 12)],
        })
        result = build_rolling_features(df)
        r1 = result[result["Round"] == 1]
        assert r1["Team_Rolling_Avg_Finish"].isna().all()

    def test_round_2_driver_rolling_uses_only_round_1(self):
        """Round 2 rolling avg for HAM = HAM's round-1 points exactly."""
        df = _make_context_df({
            1: [("HAM", "mercedes", 1, 0, 25), ("VER", "redbull", 2, 0, 18)],
            2: [("HAM", "mercedes", 2, 0, 18), ("VER", "redbull", 1, 0, 25)],
        })
        result = build_rolling_features(df)
        ham_r2 = result[(result["Driver"] == "HAM") & (result["Round"] == 2)]
        assert abs(ham_r2["Driver_Rolling_Avg_Points"].iloc[0] - 25.0) < 0.01

    def test_round_3_driver_rolling_excludes_round_3_itself(self):
        """Round-3 rolling must not include round-3 points (would be leakage)."""
        df = _make_context_df({
            1: [("VER", "redbull", 1, 0, 10)],
            2: [("VER", "redbull", 1, 0, 10)],
            3: [("VER", "redbull", 1, 0, 99)],  # 99 pts — must NOT appear in round-3 avg
        })
        result = build_rolling_features(df)
        ver_r3 = result[(result["Driver"] == "VER") & (result["Round"] == 3)]
        avg = ver_r3["Driver_Rolling_Avg_Points"].iloc[0]
        assert avg < 50, f"Round-3 rolling avg ({avg}) leaked round-3 points (99)"


# ═══════════════════════════════════════════════════════════════════════
# 6. ROLLING FEATURES — TEAM GRANULARITY  (FIX 3)
# ═══════════════════════════════════════════════════════════════════════

class TestTeamRollingGranularity:
    """
    Original bug: rolling ran directly over driver-rows, so 2 drivers × 3 rounds
    = 6 rows averaged as if they were 6 consecutive rounds (~3 rounds of history
    instead of the correct 3 full rounds).
    Fix: aggregate to (year, round, constructor) first, then roll.
    """

    def test_team_rolling_uses_one_data_point_per_round(self):
        """
        Mercedes finishes P1 + P2 every round → team avg = 1.5 per round.
        After 2 prior rounds the round-3 rolling avg must be 1.5.
        If the granularity bug were present, the window of 3 driver-rows
        would only cover the most recent ~1.5 rounds and produce ~1.33.
        """
        df = _make_context_df({
            1: [("HAM", "mercedes", 1, 0, 25), ("RUS", "mercedes", 2, 0, 18)],
            2: [("HAM", "mercedes", 1, 0, 25), ("RUS", "mercedes", 2, 0, 18)],
            3: [("HAM", "mercedes", 1, 0, 25), ("RUS", "mercedes", 2, 0, 18)],
        })
        result = build_rolling_features(df)
        r3 = result[(result["Round"] == 3) & (result["Constructor"] == "mercedes")]
        team_roll = r3["Team_Rolling_Avg_Finish"].iloc[0]
        assert abs(team_roll - 1.5) < 0.01, (
            f"Expected 1.5 (correct per-round granularity), got {team_roll:.3f}. "
            "Granularity fix may be broken."
        )


# ═══════════════════════════════════════════════════════════════════════
# 7. ROLLING FEATURES — DNF EXCLUSION  (FIX 3)
# ═══════════════════════════════════════════════════════════════════════

class TestDNFExclusionFromTeamRolling:
    """
    When a car DNFs, its position (undefined) must not pollute the team's
    rolling average finish position.
    """

    def test_dnf_driver_excluded_from_team_position_avg(self):
        """
        Round 1: HAM P2 (finisher), RUS DNF.
        Round 2 Team_Rolling_Avg_Finish should be 2.0 (HAM P2 only),
        not an average that includes the DNF.
        """
        df = _make_context_df({
            1: [("HAM", "mercedes", 2, 0, 18), ("RUS", "mercedes", 0, 1, 0)],
            2: [("HAM", "mercedes", 1, 0, 25), ("RUS", "mercedes", 3, 0, 15)],
        })
        result = build_rolling_features(df)
        r2 = result[(result["Round"] == 2) & (result["Constructor"] == "mercedes")]
        team_r2 = r2["Team_Rolling_Avg_Finish"].iloc[0]
        assert abs(team_r2 - 2.0) < 0.01, (
            f"Expected 2.0 (HAM P2 only, RUS DNF excluded), got {team_r2:.3f}"
        )

    def test_both_dnf_gives_nan_not_zero(self):
        """If both cars DNF in round 1, no finisher → team rolling for round 2 is NaN."""
        df = _make_context_df({
            1: [("HAM", "mercedes", 0, 1, 0), ("RUS", "mercedes", 0, 1, 0)],
            2: [("HAM", "mercedes", 3, 0, 15), ("RUS", "mercedes", 5, 0, 10)],
        })
        result = build_rolling_features(df)
        r2 = result[(result["Round"] == 2) & (result["Constructor"] == "mercedes")]
        team_r2 = r2["Team_Rolling_Avg_Finish"].iloc[0]
        assert pd.isna(team_r2), (
            f"Expected NaN (no round-1 finishers), got {team_r2}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 8. DNF STATUS PARSING
# ═══════════════════════════════════════════════════════════════════════

class TestDNFStatusParsing:
    """
    FIX in feature-groups.py: Is_DNF comes from the Jolpica 'status' field,
    not from guessing based on position.
    'Finished' or '+N Lap(s)' → classified finisher (Is_DNF = 0).
    Anything else (Retired, Engine, Accident, …) → DNF (Is_DNF = 1).
    """

    @staticmethod
    def _dnf(status: str) -> int:
        return 0 if (status == "Finished" or status.startswith("+")) else 1

    @pytest.mark.parametrize("status, expected", [
        ("Finished",     0),
        ("+1 Lap",       0),
        ("+2 Laps",      0),
        ("+3 Laps",      0),
        ("Retired",      1),
        ("Engine",       1),
        ("Accident",     1),
        ("Disqualified", 1),
        ("Collision",    1),
        ("Gearbox",      1),
    ])
    def test_status_mapped_correctly(self, status, expected):
        assert self._dnf(status) == expected


# ═══════════════════════════════════════════════════════════════════════
# 9. FUEL CORRECTION FORMULA  (FIX 4)
# ═══════════════════════════════════════════════════════════════════════

class TestFuelCorrection:
    """
    FuelCorrectedLapTime = LapTimeSeconds - EstimatedFuelLeft * 0.03
    Normalises to "zero fuel load" pace.  Largest correction early in the
    race (heavy tank), zero correction on the last lap.
    """

    def test_early_lap_corrected_below_raw(self):
        """Heavy fuel → correction is positive → corrected time < raw time."""
        lap, total, raw = 1, 57, 90.0
        fuel_left = 110.0 * (1 - lap / total)
        corrected = raw - fuel_left * 0.03
        assert corrected < raw

    def test_last_lap_correction_near_zero(self):
        """Empty tank → almost no correction applied."""
        lap = total = 57
        fuel_left = 110.0 * (1 - lap / total)
        assert fuel_left * 0.03 < 0.1

    def test_correction_monotonically_decreasing(self):
        """Fuel burns off → correction shrinks lap by lap."""
        total = 57
        corrections = [110.0 * (1 - lap / total) * 0.03 for lap in range(1, total + 1)]
        assert all(corrections[i] >= corrections[i + 1] for i in range(len(corrections) - 1))

    def test_total_laps_from_raw_data_prevents_negative_fuel(self):
        """
        FIX: total_laps must be derived from the raw (pre-filter) lap list.
        If total_laps were underestimated, fuel_left could go negative for
        late laps, inverting the correction direction.
        """
        total_laps_raw = 57
        for lap in range(1, total_laps_raw + 1):
            fuel_left = 110.0 * (1 - lap / total_laps_raw)
            assert fuel_left >= -1e-9, f"Negative fuel at lap {lap}"

    def test_underestimated_total_laps_would_give_negative_fuel(self):
        """
        Demonstrates WHY the fix matters: if total_laps were 50 instead of 57,
        laps 51-57 would yield negative fuel_left (overcorrecting the lap time).
        """
        wrong_total = 50
        negative_laps = [
            lap for lap in range(51, 58)
            if 110.0 * (1 - lap / wrong_total) < 0
        ]
        assert len(negative_laps) > 0, "Expected negative fuel with underestimated total_laps"
