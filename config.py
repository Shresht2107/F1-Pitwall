import os
from dotenv import load_dotenv

load_dotenv()

# Qdrant
QDRANT_URL     = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

# Groq
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

# Nomic
NOMIC_API_KEY  = os.getenv("NOMIC_API_KEY")

SEASONS = {
    2022: range(1, 23),  # 22 races
    2023: range(1, 24),  # 23 races (Las Vegas added)
    2024: range(1, 25),  # 24 races
}

# Regressor is trained on TRAIN_YEARS; TEST_YEAR is the held-out evaluation season.
TRAIN_YEARS = [2022, 2023]
TEST_YEAR   = 2024

CACHE_DIR               = "./fastf1_cache"
JOLPICA_RAW_PATH        = "jolpica_raw.csv"
JOLPICA_QUALIFYING_PATH = "jolpica_qualifying.csv"
JOLPICA_STANDINGS_PATH  = "jolpica_standings.csv"
CIRCUITS_PATH           = "circuits.csv"
STAGE2_OUTPUT           = "stage2_dataset.csv"
PACE_DELTAS_OUTPUT      = "pace_deltas.csv"
