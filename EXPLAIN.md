# EXPLAIN.md

Technical reference for the F1 PIT WALL project: architecture, tech stack, and data/model pipeline.

## 1. System Overview

PIT WALL is a full-stack, ML/RAG hybrid system for Formula 1 race analytics. It combines a supervised learning pipeline (regression + classification over historical telemetry and results) with a retrieval-augmented generation (RAG) layer for natural-language Q&A, surfaced through a Next.js dashboard.

```
Jolpica-F1 API + FastF1 telemetry cache
        │
        ▼  ETL (collect_data.py)
jolpica_raw.csv · jolpica_qualifying.csv · jolpica_standings.csv · circuits.csv
        │
        ▼  feature engineering (stage2.py, feature-groups.py)
stage2_dataset.csv  (per-driver-per-race feature matrix)
        │
        ▼  XGBoost regression + Monte Carlo simulation (regressor.py)
pace_deltas.csv  (Expected_Pace_Delta per driver/race)
        │
        ▼  XGBoost classification (stage4.py)
podium probability model
        │
        ▼  document synthesis + chunking + embedding (rag/build_docs.py, rag/ingest.py)
Qdrant Cloud vector collection (f1_rag, 768-dim, cosine)
        │
        ▼  retrieval (rag/retrieve.py) + generation (rag/generate.py)
FastAPI (api/server.py) ──► Next.js proxy routes ──► React dashboard (pitwall/)
```

## 2. Tech Stack

### Backend / ML
| Layer | Technology |
|---|---|
| Language | Python 3 |
| ML framework | XGBoost (`XGBRegressor`, `XGBClassifier`), scikit-learn (metrics: MAE, accuracy, log-loss, ROC-AUC) |
| Data manipulation | pandas, numpy |
| Telemetry ingestion | FastF1 (lap-by-lap timing, tyre compounds, session data), local disk cache (`fastf1_cache/`) |
| Race/results ingestion | Jolpica-F1 REST API (Ergast-compatible F1 historical data) |
| API layer | FastAPI + Uvicorn (ASGI), Pydantic request/response models |
| Vector database | Qdrant Cloud (managed, cosine-similarity HNSW index) |
| Embedding model | Nomic Atlas `nomic-embed-text-v1.5` (768-dim), via `nomic` SDK, `search_document`/`search_query` task-type asymmetric embeddings |
| Text chunking | LangChain `RecursiveCharacterTextSplitter` (800 chars / 100 overlap, hierarchical separators) |
| LLM inference | Groq-hosted `qwen/qwen3-32b` (via `groq` SDK), optional chain-of-thought via `/think` directive |
| Config/secrets | `python-dotenv` reading `.env`, centralized in `config.py` |

### Frontend
| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router), React 19, TypeScript |
| Styling | Tailwind CSS v4 (`@tailwindcss/postcss`) |
| State/data flow | React Context (`RaceContext`) as the single source of truth for dashboard components |
| E2E testing | Playwright |
| Linting | ESLint 9 (`eslint-config-next`) |

### Deployment
| Component | Service |
|---|---|
| Frontend | Vercel |
| Backend (FastAPI) | Render |
| Vector DB | Qdrant Cloud |
| LLM inference | Groq (OpenAI-compatible chat completion API) |
| Embeddings | Nomic Atlas (hosted inference, no local GPU) |

The Next.js API routes (`pitwall/app/api/*`) act as a server-side proxy layer — the browser never calls the Render-hosted FastAPI backend directly, avoiding CORS/credential exposure and centralizing the `NEXT_PUBLIC_API_URL` target.

## 3. Data Pipeline (ETL + Feature Engineering)

**Stage 0 — Collection (`collect_data.py`)**: Pulls per-season race results, qualifying, and championship standings from the Jolpica-F1 API for 2022–2024 (`SEASONS` in `config.py`), cross-referenced with FastF1 session objects for lap-level telemetry (compound, stint length, sector times, track temperature). Output: `jolpica_raw.csv`, `jolpica_qualifying.csv`, `jolpica_standings.csv`.

**DNF classification (`feature-groups.py`)**: `Is_DNF` is derived from Jolpica's `status` string — anything outside `{'Finished', 'Lapped'}` or prefixed with `+` (lapped-N-times notation) is flagged as a retirement. `stage2.py` re-derives this independently from the `Status` column with an expanded allow-list that also treats `"Not Classified"` as a non-DNF, guarding against upstream schema drift.

**Stage 2 — Feature assembly (`stage2.py`)**: Joins raw results with rolling-window aggregates and derives the model-ready feature matrix (`stage2_dataset.csv`), including:
- `GridPosition`, `Q_DeltaToPole` (qualifying gap to pole)
- `Team_Rolling_Avg_Finish`, `Driver_Rolling_Avg_Points` (exponential/rolling form indicators)
- `Driver_Championship_Pos`, `Constructor_Championship_Pos` (standings entering the race)
- `OvertakingIndex` (circuit-specific overtaking difficulty), `Is_Wet_Race`, `CircuitType`
- `Num_Stints`, `Strategy_Summary`, `Median_FuelCorrectedLapTime`

**Stage 3 — Pace regression + Monte Carlo simulation (`regressor.py`)**: An `XGBRegressor` is trained on fuel-corrected median lap times from FastF1 telemetry, using tyre compound and track temperature as primary regressors. Two canonical strategy templates are defined as compound/stint-length sequences:
- One-stop: MEDIUM(15 laps) → HARD(29 laps)
- Two-stop: SOFT(10) → MEDIUM(17) → HARD(17)

`simulate_race_strategy()` runs a Monte Carlo simulation (`np.random.normal(race_base, race_std, n_simulations)`) over the regressor's predicted lap-time distribution to estimate a race-time distribution per driver/strategy combination. The gap between actual strategy outcome and the optimal simulated strategy becomes `Expected_Pace_Delta`, persisted to `pace_deltas.csv`. Training/evaluation uses a temporal split — `TRAIN_YEARS = [2022, 2023]`, `TEST_YEAR = 2024` — to avoid look-ahead leakage.

**Stage 4 — Podium classification (`stage4.py`)**: An `XGBClassifier` predicts `Is_Podium` (`Position <= 3`, DNFs excluded) from the Stage 2 feature set plus `Expected_Pace_Delta` from Stage 3 (`FEATURES_FULL`). Evaluated via accuracy, log-loss, and ROC-AUC on the held-out `TEST_YEAR`. XGBoost's native NaN handling allows pre-race features to remain sparse (e.g., no rolling average exists for Round 1).

## 4. RAG Subsystem

**Document synthesis (`rag/build_docs.py`)**: Generates one prose document per (Year, Round) — a race header (winner, podium, DNF count, circuit metadata, winner's strategy) followed by one line per driver in finishing order. This is a deliberate denormalization: converting structured tabular rows into narrative text suitable for dense embedding.

**Chunking (`rag/ingest.py`)**: `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)` with separator priority `["\n\n", "\n", ". ", " ", ""]`. The race header reliably lands in chunk 0; driver-detail lines for non-winners fall progressively later, which caps retrieval recall for queries about mid-grid or backmarker drivers if `top_k` is set too low (documented root-cause investigation in `PLAN.md`).

**Embedding**: Nomic `nomic-embed-text-v1.5`, 768-dim, asymmetric task types (`search_document` at ingest time, `search_query` at retrieval time) — this asymmetry is a Nomic-specific optimization where query and document embeddings are trained under different objectives to improve retrieval precision.

**Vector store (Qdrant Cloud)**: Collection `f1_rag`, cosine distance. Explicit payload indexes on `year` (integer), `drivers`/`constructors`/`circuit` (keyword) enable metadata pre-filtering ahead of/alongside dense vector search — Qdrant Cloud requires these indexes to be created explicitly for filtered queries to be efficient.

**Retrieval (`rag/retrieve.py`)**: Embeds the query, optionally extracts structured filters (driver code, constructor alias, circuit keyword) via regex/lookup tables from the raw query text, and applies them as a Qdrant `Filter` (`MatchValue`/`MatchAny`) alongside the vector search — a hybrid sparse-filter + dense-retrieval approach.

**Generation (`rag/generate.py`)**: Constructs a system-prompted context-grounded request to `qwen/qwen3-32b` via the Groq inference API. The system prompt enforces topical scope-limiting (F1-only), prompt-injection resistance (explicit instruction to treat user turns as questions, not commands), and a citation-style output format (stints, deltas, positions). Chain-of-thought is gated behind an explicit `/think` directive and a `think: bool` request flag, stripped from the final response before it reaches the client.

## 5. API Layer (`api/server.py`)

FastAPI app with CORS restricted to the known frontend origins (`localhost:3000`, the Vercel deployment, and `*.vercel.app` for preview deploys).

- `POST /chat` — `{query, top_k, think}` → runs `retrieve()` then `generate()`, returns `{answer, sources}` where each source carries year/round/circuit/score provenance for frontend cross-linking.
- `GET /race?year=&round=` — serves a denormalized per-race, per-driver JSON payload assembled from `stage2_dataset.csv` (joined with `pace_deltas.csv` on `[Year, Round, Driver]`), including grid/finish position, qualifying delta, championship standings, pace delta, and strategy summary. NaN-safe coercion helpers (`_safe_float`, `_safe_int`) guard against `json` serialization errors from pandas NaNs.
- `GET /health` — liveness probe for the Render deployment.

## 6. Frontend Architecture (`pitwall/`)

Next.js App Router structure:
- `/dashboard` — the primary UI surface.
- `RaceContext` — a single React Context populated by the chat flow; all visual components (`StatCards`, `DriverTable`, `TireStrategy`, `CircuitContext`) are pure consumers with no independent fetch logic, enforcing a unidirectional data flow: **user query → RAG answer → structured `/race` fetch → context → rendered components.**
- `app/api/chat/route.ts`, `app/api/race/route.ts` — server-side proxy routes forwarding to the FastAPI backend, keeping `NEXT_PUBLIC_API_URL` and any backend credentials off the client.
- Styling via Tailwind CSS v4 utility classes; component-level custom cursor and circuit-background visualizations (`CustomCursor.tsx`, `CircuitBackground.tsx`) for the dashboard's motorsport theming.

## 7. Key Design Decisions Worth Knowing

- **Temporal train/test split** (2022–2023 train, 2024 test) rather than random split — prevents leakage from season-long form correlation and mirrors real deployment (predicting an unseen season).
- **Two-stage supervised pipeline** (regression → classification) rather than a single end-to-end model — the pace regressor's Monte Carlo output (`Expected_Pace_Delta`) is engineered as a *feature* for the podium classifier, isolating "how fast was the car" from "did it finish on the podium."
- **Denormalization before embedding** — the RAG layer intentionally converts tabular race data into prose *specifically* to make it embeddable/retrievable by a text embedding model, trading structured-query precision for natural-language flexibility.
- **Asymmetric embedding task types** (`search_document` vs `search_query`) — a detail specific to Nomic's model family; using the wrong task type at either ingest or query time degrades retrieval quality silently (no error, just worse cosine alignment).
- **Proxy-pattern frontend** — Next.js API routes never expose the Render backend URL or any backend secrets to the browser bundle.
