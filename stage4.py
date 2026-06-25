import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
import warnings
warnings.filterwarnings('ignore')

from config import STAGE2_OUTPUT, PACE_DELTAS_OUTPUT, TEST_YEAR

# =====================================================================
# 1. LOAD REAL DATA FROM STAGE 2 + STAGE 3
# =====================================================================
print("Loading Stage 2 dataset and Stage 3 pace deltas...")

try:
    stage2      = pd.read_csv(STAGE2_OUTPUT)
    pace_deltas = pd.read_csv(PACE_DELTAS_OUTPUT)
except FileNotFoundError as e:
    raise SystemExit(
        f"\nMissing upstream file: {e}\n"
        "Run the pipeline in order:\n"
        "  python stage2.py\n"
        "  python regressor.py\n"
        "  python stage4.py\n"
    )

df = stage2.merge(pace_deltas, on=['Year', 'Round', 'Driver'], how='inner')

# =====================================================================
# 2. TARGET & FEATURE PREP
# =====================================================================
# New features are pre-race available and may be NaN for round 1 (standings) or
# missing qualifying rounds. XGBoost handles NaN natively so we only enforce
# non-null on the target columns and the Monte Carlo delta.
FEATURES_BASE = [
    'GridPosition', 'Q_DeltaToPole',
    'Team_Rolling_Avg_Finish', 'Driver_Rolling_Avg_Points',
    'Driver_Championship_Pos', 'Constructor_Championship_Pos',
    'OvertakingIndex', 'Is_Wet_Race',
]
FEATURES_FULL = FEATURES_BASE + ['Expected_Pace_Delta']

# Keep only columns that actually exist (graceful degradation if enrichment
# hasn't been run yet — falls back to whichever features are present).
FEATURES_BASE = [f for f in FEATURES_BASE if f in df.columns]
FEATURES_FULL = [f for f in FEATURES_FULL if f in df.columns]

# Exclude DNFs (no finish → no podium signal)
df = df[df['Is_DNF'] == 0].copy()
df = df.dropna(subset=['Position', 'Is_DNF', 'Expected_Pace_Delta']
               if 'Expected_Pace_Delta' in df.columns
               else ['Position', 'Is_DNF'])

df['Is_Podium'] = (df['Position'] <= 3).astype(int)

seasons_in_data = sorted(df['Year'].unique())
print(f"\nDataset: {len(df)} rows | seasons {seasons_in_data} | "
      f"podium rate: {df['Is_Podium'].mean():.1%}")

# =====================================================================
# 3. YEAR-BASED TRAIN / TEST SPLIT
#    Train on every season before TEST_YEAR; test on TEST_YEAR.
#    This is the correct temporal split for a multi-season dataset.
# =====================================================================
train_df = df[df['Year'] < TEST_YEAR]
test_df  = df[df['Year'] == TEST_YEAR]

print(f"\nTrain: {len(train_df)} rows ({sorted(train_df['Year'].unique())})")
print(f"Test : {len(test_df)} rows ({TEST_YEAR})")

y_train = train_df['Is_Podium']
y_test  = test_df['Is_Podium']

if y_test.nunique() < 2:
    raise SystemExit(
        "Test set has only one class — add more rounds to get a valid evaluation."
    )

# =====================================================================
# 4. BASELINE MODEL (position + team / driver form; no strategy)
# =====================================================================
print("\n--- BASELINE MODEL ---")
clf_baseline = XGBClassifier(
    n_estimators=50, max_depth=3, eval_metric='logloss', random_state=42
)
clf_baseline.fit(train_df[FEATURES_BASE], y_train)

baseline_probs = clf_baseline.predict_proba(test_df[FEATURES_BASE])[:, 1]
baseline_preds = (baseline_probs >= 0.5).astype(int)

baseline_acc  = accuracy_score(y_test, baseline_preds)
baseline_loss = log_loss(y_test, baseline_probs)
baseline_auc  = roc_auc_score(y_test, baseline_probs)

print(f"Accuracy : {baseline_acc:.4f}")
print(f"Log Loss : {baseline_loss:.4f}  (lower = better)")
print(f"ROC-AUC  : {baseline_auc:.4f}  (higher = better)")

# =====================================================================
# 5. FULL MODEL (adds Expected_Pace_Delta from Stage 3 Monte Carlo)
# =====================================================================
print("\n--- FULL MODEL (+ Stage 3 Expected_Pace_Delta) ---")
clf_full = XGBClassifier(
    n_estimators=50, max_depth=3, eval_metric='logloss', random_state=42
)
clf_full.fit(train_df[FEATURES_FULL], y_train)

full_probs = clf_full.predict_proba(test_df[FEATURES_FULL])[:, 1]
full_preds = (full_probs >= 0.5).astype(int)

full_acc  = accuracy_score(y_test, full_preds)
full_loss = log_loss(y_test, full_probs)
full_auc  = roc_auc_score(y_test, full_probs)

print(f"Accuracy : {full_acc:.4f}")
print(f"Log Loss : {full_loss:.4f}")
print(f"ROC-AUC  : {full_auc:.4f}")

# =====================================================================
# 6. LIFT FROM MONTE CARLO STRATEGY FEATURE
# =====================================================================
logloss_lift = ((baseline_loss - full_loss) / baseline_loss) * 100
auc_lift     = ((full_auc - baseline_auc) / baseline_auc) * 100

print("\n" + "=" * 52)
print("LIFT FROM MONTE CARLO STRATEGY FEATURE")
print("=" * 52)
print(f"Log Loss improvement : {logloss_lift:+.1f}%")
print(f"ROC-AUC  improvement : {auc_lift:+.1f}%")

# =====================================================================
# 7. SANITY CHECK: top predicted podium probabilities on test round
# =====================================================================
test_display = test_df[['Driver', 'GridPosition', 'Expected_Pace_Delta']].copy()
test_display['Podium_Prob'] = full_probs
test_display['Actual_Podium'] = y_test.values
print(f"\nTop predictions for {TEST_YEAR} (full season sample):")
print(
    test_display.sort_values('Podium_Prob', ascending=False)
    .head(15)
    .to_string(index=False)
)
