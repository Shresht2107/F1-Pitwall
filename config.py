# Shared configuration for the F1 Prediction pipeline.
# Import this in collect_data.py, stage2.py, regressor.py, and stage4.py.

SEASONS = {
    2022: range(1, 23),  # 22 races
    2023: range(1, 24),  # 23 races (Las Vegas added)
    2024: range(1, 25),  # 24 races
}

# Regressor is trained on TRAIN_YEARS; TEST_YEAR is the held-out evaluation season.
TRAIN_YEARS = [2022, 2023]
TEST_YEAR   = 2024

CACHE_DIR          = "./fastf1_cache"
JOLPICA_RAW_PATH        = "jolpica_raw.csv"
JOLPICA_QUALIFYING_PATH = "jolpica_qualifying.csv"
JOLPICA_STANDINGS_PATH  = "jolpica_standings.csv"
CIRCUITS_PATH           = "circuits.csv"
STAGE2_OUTPUT      = "stage2_dataset.csv"
PACE_DELTAS_OUTPUT = "pace_deltas.csv"
