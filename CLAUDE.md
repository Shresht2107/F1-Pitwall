# F1 Prediction + RAG Project

## Project Goal

Build a multi-stage ML pipeline that predicts F1 race outcomes (podium finish probability) and integrates a RAG (Retrieval-Augmented Generation) layer for natural-language querying of race data. The results are exposed through a live dashboard — **PIT WALL** — built in Next.js, backed by a FastAPI server, with a chat interface powered by a local LLM.

---

## Full Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA COLLECTION                              │
│                                                                     │
│  FastF1 API          Jolpica-F1 API           Static               │
│  (lap telemetry,     (race results,           circuits.csv          │
│   weather, tyre)      qualifying,             (circuit type,        │
│                       standings)               overtaking index)    │
│       │                    │                       │               │
│       ▼                    ▼                       ▼               │
│  fastf1_cache/      jolpica_raw.csv         circuits.csv           │
│  (.ff1pkl files)    jolpica_qualifying.csv                         │
│                     jolpica_standings.csv                           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │  collect_data.py  (Stage 0)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FEATURE ENGINEERING                            │
│                                                                     │
│  feature-groups.py  (Stage 1)                                       │
│  ├── get_fastf1_pace_features()  →  per-lap pace + weather          │
│  ├── get_jolpica_race_context()  →  grid/result/DNF/points          │
│  ├── get_jolpica_qualifying()    →  Q_DeltaToPole per driver        │
│  ├── get_jolpica_standings()     →  championship pos (round-1)      │
│  └── build_rolling_features()   →  3-race rolling windows          │
│                                                                     │
│  stage2.py  (Stage 2)                                               │
│  ├── merge pace + context + qualifying + standings + circuits        │
│  ├── compute Is_Wet_Race from Rainfall                              │
│  └── output: stage2_dataset.csv  (one row per driver per race)      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
┌─────────────────────────┐  ┌────────────────────────────────────────┐
│   STAGE 3 — REGRESSOR   │  │         STAGE 4 — CLASSIFIER          │
│   regressor.py          │  │         stage4.py                     │
│                         │  │                                        │
│  XGBoost lap-time       │  │  XGBoost binary classifier             │
│  regressor trained on   │  │  Target: Is_Podium (P1/P2/P3)         │
│  2022-2023 laps         │  │                                        │
│        │                │  │  FEATURES_BASE:                       │
│        ▼                │  │   GridPosition, Q_DeltaToPole,        │
│  Monte Carlo simulator  │  │   Team_Rolling_Avg_Finish,            │
│  500 runs × strategy    │  │   Driver_Rolling_Avg_Points,          │
│  vs canonical benchmark │  │   Driver_Championship_Pos,            │
│        │                │  │   Constructor_Championship_Pos,       │
│        ▼                │  │   OvertakingIndex, Is_Wet_Race        │
│  pace_deltas.csv        │──▶  FEATURES_FULL: BASE + pace delta     │
│  (Expected_Pace_Delta   │  │                                        │
│   per driver per race)  │  │  Train: 2022-2023 / Test: 2024        │
│                         │  │  Metrics: Log Loss + ROC-AUC          │
└─────────────────────────┘  └────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          RAG PIPELINE                               │
│                                                                     │
│  rag/build_docs.py                                                  │
│  └── stage2_dataset.csv + pace_deltas.csv                          │
│      → 69 prose documents (one per Year/Round)                      │
│      → each doc: podium, DNFs, per-driver stats, circuit context   │
│                                                                     │
│  rag/ingest.py                                                      │
│  └── chunk at 800 chars (100 overlap)                              │
│      → embed with nomic-embed-text via Ollama                       │
│      → upsert into Qdrant collection "f1_rag"  (~420 chunks)       │
│                                                                     │
│  rag/retrieve.py                                                    │
│  └── embed query → extract pre-filters (year, driver, constructor, │
│      circuit) from free text → filtered Qdrant search (top-5)      │
│      → fallback to unfiltered if 0 results                         │
│      NOTE: driver code extraction runs on original-case query to   │
│      avoid matching common English words (e.g. "had" → HAD)        │
│                                                                     │
│  rag/generate.py                                                    │
│  └── build prompt from chunks → call qwen3:4b via Ollama           │
│      → strip </think> tokens → return answer                       │
│                                                                     │
│  rag/cli.py  — interactive terminal REPL                           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DASHBOARD — PIT WALL                         │
│                                                                     │
│  api/server.py  (FastAPI, port 8000)                               │
│  ├── POST /chat  →  retrieve() + generate() → {answer, sources}    │
│  ├── GET  /race?year=Y&round=R                                      │
│  │         →  stage2_dataset.csv + pace_deltas.csv                 │
│  │         →  structured JSON: circuit meta + all 20 drivers       │
│  └── GET  /health                                                   │
│                                                                     │
│  pitwall/  (Next.js, port 3000)                                     │
│  ├── app/api/chat/route.ts    →  proxy to FastAPI /chat            │
│  ├── app/api/race/route.ts    →  proxy to FastAPI /race            │
│  ├── components/RaceContext   →  shared React context for race data │
│  ├── components/Chat          →  sends query → on response,        │
│  │                                reads sources[0] → fetches /race  │
│  │                                → pushes into RaceContext         │
│  ├── components/Ticker        →  scrolling bar: driver pace deltas,│
│  │                                track temp, conditions, podium    │
│  ├── components/StatCards     →  winner's grid/delta/champ/DNFs    │
│  ├── components/CircuitContext→  circuit name, type, overtaking bar │
│  ├── components/TireStrategy  →  canonical stint bars from winner   │
│  └── components/DriverTable   →  all 20 drivers, real stats        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Data & APIs
| Tool | Role |
|------|------|
| **FastF1** | Lap telemetry, tyre compound, weather (TrackTemp, Rainfall) per session |
| **Jolpica-F1 API** | Ergast successor: race results, qualifying times, championship standings |
| **circuits.csv** | Static lookup: 25 circuits × OvertakingIndex (1–10) + CircuitType |

### Machine Learning
| Tool | Role |
|------|------|
| **XGBoost** | Both the lap-time regressor (Stage 3) and podium classifier (Stage 4) |
| **scikit-learn** | Train/test split, evaluation metrics (ROC-AUC, Log Loss) |
| **pandas / numpy** | Feature engineering, rolling windows, data merges |

### RAG & LLM
| Tool | Role |
|------|------|
| **Qdrant** | Local vector store; hosts the `f1_rag` collection (~420 chunks); run via Docker |
| **Ollama** | Local model server for both embedding and generation |
| **nomic-embed-text** | Embedding model: converts text chunks and queries to 768-dim vectors |
| **qwen3:4b** | Generation model: produces answers from retrieved context; supports chain-of-thought via `--think` |
| **langchain-text-splitters** | Chunk prose documents at 800 chars with 100-char overlap |

### Backend & Frontend
| Tool | Role |
|------|------|
| **FastAPI** | Python API server (port 8000): `/chat`, `/race`, `/health` |
| **uvicorn** | ASGI server running FastAPI |
| **Next.js** | Frontend framework (port 3000): dashboard + API proxy routes |
| **React** | UI components; `RaceContext` for shared state across the dashboard |
| **TypeScript** | Typed throughout the frontend |

---

## Models

### XGBoost Lap-Time Regressor (Stage 3)
- **Task**: Predict `FuelCorrectedLapTime` from in-race conditions
- **Features**: `LapNumber`, `Stint`, `CompoundCode` (0=Soft/1=Med/2=Hard), `TyreLife`, `TrackTemp`
- **Train**: 2022–2023 race laps (clean laps only — TrackStatus=1, no in/out laps, not deleted)
- **Eval**: MAE on 2024 held-out laps
- **Used for**: powering the Monte Carlo race strategy simulator

### Monte Carlo Race Simulator (Stage 3)
- Not a learned model — a stochastic simulator built on top of the regressor
- 500 runs per strategy, σ=0.25s lap noise, 22s pit stop loss
- Canonical benchmarks: one-stop M→H and two-stop S→M→H scaled to race distance
- **Output**: `Expected_Pace_Delta` = driver's strategy median total time − optimal benchmark median (negative = faster)

### XGBoost Podium Classifier (Stage 4)
- **Task**: Binary classification — `Is_Podium` (finished P1/P2/P3)
- **FEATURES_BASE**: `GridPosition`, `Q_DeltaToPole`, `Team_Rolling_Avg_Finish`, `Driver_Rolling_Avg_Points`, `Driver_Championship_Pos`, `Constructor_Championship_Pos`, `OvertakingIndex`, `Is_Wet_Race`
- **FEATURES_FULL**: FEATURES_BASE + `Expected_Pace_Delta`
- **Train**: 2022–2023 / **Test**: 2024 (temporal split — no leakage)
- **Metrics**: Log Loss + ROC-AUC; reports lift from adding Stage 3 delta
- XGBoost handles NaN natively — round-1 standings (no prior round) left as NaN safely

### nomic-embed-text (RAG)
- 768-dimensional dense embeddings
- Used at ingest time (chunk → vector) and at query time (query → vector)
- Served locally via Ollama

### qwen3:4b (RAG)
- 4-billion parameter instruction-tuned model
- Receives a RAG prompt: top-5 retrieved chunks + user question
- Supports `think=True` for chain-of-thought reasoning (strips `</think>` from output)
- Served locally via Ollama

---

## Key Design Decisions

**Fuel correction**: `FuelCorrectedLapTime = LapTime − (EstimatedFuelLeft × 0.03s/kg)` normalises all laps to zero-fuel pace, making cross-stint and cross-driver comparisons meaningful.

**Rolling features use shift-then-roll**: All rolling windows (`Team_Rolling_Avg_Finish`, `Driver_Rolling_Avg_Points`) are computed with `.shift(1)` before `.rolling()` to prevent the current race from leaking into its own feature.

**Standings fetched at round-1**: Championship positions are always fetched for the round before the current one (Jolpica `/{year}/{round-1}/driverstandings`). Round 1 returns NaN — XGBoost handles this natively.

**RAG filter extraction uses original-case query**: Driver codes (VER, HAM, etc.) are extracted only from explicitly uppercase tokens in the query. Using `.upper()` caused common words like "had" to match the driver code HAD (Hadjar), injecting a spurious filter and triggering the unfiltered fallback.

**Dashboard data flow**: Chat → `/api/chat` → FastAPI → RAG → `{answer, sources}`. The frontend reads `sources[0].{year, round}`, fetches `/api/race`, and pushes the result into `RaceContext`. All four panel components and the Ticker are consumers of this shared context — a single query updates the entire dashboard.

---

## Running the Project

### Prerequisites
```bash
# Qdrant (vector store)
docker run -p 6333:6333 qdrant/qdrant

# Ollama models
ollama pull nomic-embed-text
ollama pull qwen3:4b
```

### ML Pipeline
```bash
python collect_data.py          # Stage 0: download data (incremental)
python stage2.py                # Stage 2: build stage2_dataset.csv
python regressor.py             # Stage 3: build pace_deltas.csv
python stage4.py                # Stage 4: train + evaluate classifier

# Or run everything at once:
python run_pipeline.py
python run_pipeline.py --skip-download   # skip collect_data if cache warm
python run_pipeline.py --from-stage 3   # resume from regressor
```

### RAG Ingest
```bash
/opt/anaconda3/bin/python3 -m rag.ingest            # first-time ingest
/opt/anaconda3/bin/python3 -m rag.ingest --recreate # rebuild collection
/opt/anaconda3/bin/python3 -m rag.cli               # terminal Q&A
/opt/anaconda3/bin/python3 -m rag.cli --think       # chain-of-thought
```

### Dashboard (PIT WALL)
```bash
# Terminal 1 — FastAPI backend
/opt/anaconda3/bin/uvicorn api.server:app --reload --port 8000

# Terminal 2 — Next.js frontend
cd pitwall && npm run dev
# → http://localhost:3000/dashboard
```

---

## Data Notes

- `fastf1_cache/` — do not delete; stores downloaded `.ff1pkl` session files; makes subsequent runs instant
- `jolpica_raw.csv` — 1359 rows; incremental (skips already-fetched rounds)
- `jolpica_qualifying.csv` — per-driver Q1/Q2/Q3 times; incremental
- `jolpica_standings.csv` — pre-race championship snapshot; incremental; NaN for round 1
- `circuits.csv` — 25 static rows covering all 2022–2024 venues
- `stage2_dataset.csv` — one row per driver per race; ~1350 rows; master feature table
- `pace_deltas.csv` — one row per driver per race; `Expected_Pace_Delta` in seconds (total race, not per-lap)
- Compound codes in regressor: 0=SOFT, 1=MEDIUM, 2=HARD; wet/intermediate compounds filtered out
- Data coverage: 2022 (22 rounds), 2023 (23 rounds), 2024 (24 rounds) = 69 races
- `config.py` is the single source of truth for season ranges, file paths, and train/test year split
- Jolpica rate limit: 1.5s delay between requests (`_JOLPICA_DELAY`); burst requests cause ~60–70% empty responses

---

## Key Files

```
collect_data.py              Stage 0: download orchestrator (race results, qualifying, standings)
feature-groups.py            Stage 1: FastF1 pace features + Jolpica fetchers + rolling features
stage2.py                    Stage 2: merge all sources → stage2_dataset.csv
regressor.py                 Stage 3: XGBoost lap-time regressor + Monte Carlo simulator → pace_deltas.csv
stage4.py                    Stage 4: XGBoost podium classifier
run_pipeline.py              Pipeline runner with streaming output + summary table
config.py                    Single source of truth: paths, season ranges, train/test split
circuits.csv                 Static circuit lookup: OvertakingIndex + CircuitType
jolpica_raw.csv              Cached race results
jolpica_qualifying.csv       Cached qualifying times
jolpica_standings.csv        Cached pre-race standings
stage2_dataset.csv           Master enriched feature table (output of Stage 2)
pace_deltas.csv              Expected_Pace_Delta per driver per race (output of Stage 3)

rag/
  build_docs.py              CSV → 69 prose race documents with full per-driver context
  ingest.py                  Embed + upsert chunks into Qdrant
  retrieve.py                Vector search with payload pre-filtering + unfiltered fallback
  generate.py                qwen3:4b RAG generation via Ollama
  cli.py                     Interactive terminal Q&A REPL

api/
  server.py                  FastAPI: POST /chat, GET /race, GET /health

pitwall/
  app/api/chat/route.ts      Next.js proxy → FastAPI /chat
  app/api/race/route.ts      Next.js proxy → FastAPI /race
  app/dashboard/page.tsx     Dashboard layout + RaceProvider wrapper
  components/RaceContext.tsx  Shared React context (RaceData + loading state)
  components/Chat.tsx        Chat UI + race context producer
  components/Ticker.tsx      Scrolling ticker: driver deltas, conditions, podium
  components/StatCards.tsx   6 stat cards: grid, delta, qual gap, champ pos, DNFs, conditions
  components/CircuitContext.tsx  Circuit name, type badge, overtaking index bar
  components/TireStrategy.tsx   Canonical stint bars from winner's stint count
  components/DriverTable.tsx    Full 20-driver table with real stats
```
