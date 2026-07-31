# PIT WALL

A full-stack ML/RAG hybrid system for Formula 1 race analytics. It combines a supervised
learning pipeline (regression + classification over historical results and telemetry) with a
retrieval-augmented generation (RAG) layer for natural-language Q&A, surfaced through a
Next.js dashboard.

**Live demo:** https://f1-pitwall-beta.vercel.app/dashboard
*(backend is on Render's free tier — the first request after idle may take 30–50s to wake up)*

## What it does

Ask a question about any Formula 1 race from the 2022–2024 seasons — results, tyre
strategy, DNFs, qualifying gaps, championship standings — and PIT WALL answers in natural
language, then loads the matching race into the dashboard: grid/finish positions, per-driver
tyre stints, pace deltas vs. optimal strategy, and circuit context.

## Architecture

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

See [EXPLAIN.md](EXPLAIN.md) for the full technical writeup (data pipeline, RAG design
decisions, API contracts) and [CLAUDE.md](CLAUDE.md) for local dev commands.

## Tech stack

| Layer | Technology |
|---|---|
| ML | XGBoost, scikit-learn, pandas, numpy |
| Telemetry / results | FastF1, Jolpica-F1 API |
| API | FastAPI + Uvicorn |
| Vector DB | Qdrant Cloud |
| Embeddings | Nomic Atlas `nomic-embed-text-v1.5` |
| LLM | Groq-hosted `qwen/qwen3.6-27b` |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4 |
| Deployment | Vercel (frontend) · Render (backend) |

## Running locally

**Backend**
```bash
pip install -r requirements.txt
```
Create a `.env` file in the project root with:
```
QDRANT_URL=...
QDRANT_API_KEY=...
GROQ_API_KEY=...
NOMIC_API_KEY=...
```
```bash
uvicorn api.server:app --reload --port 8000
```

**Frontend**
```bash
cd pitwall
npm install
npm run dev   # http://localhost:3000/dashboard
```

**Regenerating the ML pipeline from scratch**
```bash
python run_pipeline.py
```

**Tests**
```bash
pytest tests/ -v
```

Full deployment instructions (Qdrant Cloud, Groq, Nomic, Render, Vercel setup) are in
[DEPLOY.md](DEPLOY.md).
