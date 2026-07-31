# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Python pipeline (run from project root)
```bash
# Full pipeline from scratch
/opt/anaconda3/bin/python3 run_pipeline.py

# Resume from a specific stage
/opt/anaconda3/bin/python3 run_pipeline.py --from-stage 2   # skip data collection
/opt/anaconda3/bin/python3 run_pipeline.py --from-stage 3   # skip to regressor

# Individual stages
/opt/anaconda3/bin/python3 collect_data.py       # stage 0: fetch Jolpica + FastF1
/opt/anaconda3/bin/python3 stage2.py             # stage 2: assemble dataset
/opt/anaconda3/bin/python3 regressor.py          # stage 3: train regressor + pace deltas
/opt/anaconda3/bin/python3 stage4.py             # stage 4: podium classifier

# RAG
/opt/anaconda3/bin/python3 -m rag.ingest --recreate   # rebuild Qdrant collection
/opt/anaconda3/bin/python3 rag/cli.py                 # interactive RAG CLI

# FastAPI backend
uvicorn api.server:app --reload --port 8000

# Tests
pytest tests/ -v
```

### Next.js frontend (run from `pitwall/`)
```bash
npm run dev      # local dev server on :3000
npm run build    # production build
eslint           # lint
```

## Architecture

This is a multi-stage ML pipeline feeding a RAG-backed dashboard.

### Data flow
```
Jolpica API + FastF1 cache
    ↓  collect_data.py  →  jolpica_raw.csv, jolpica_qualifying.csv, jolpica_standings.csv
    ↓  stage2.py        →  stage2_dataset.csv  (per-driver-per-race features)
    ↓  regressor.py     →  pace_deltas.csv     (XGBoost lap-time regressor + Monte Carlo)
    ↓  stage4.py        →  podium classifier   (trained on stage2 + pace_deltas)
    ↓  rag/ingest.py    →  Qdrant Cloud        (prose docs chunked + embedded via Nomic)
```

### Backend: `api/server.py`
FastAPI with two routes:
- `POST /chat` — calls `rag/retrieve.py` (Qdrant vector search) then `rag/generate.py` (Groq/qwen3-32b)
- `GET /race?year=&round=` — serves structured driver data from `stage2_dataset.csv` + `pace_deltas.csv`

All secrets (Qdrant, Groq, Nomic) flow through `config.py` which reads `.env` via `python-dotenv`.

### Frontend: `pitwall/`
Next.js app. The dashboard lives at `/dashboard`. Key data flow:
- User sends a chat message → `Chat.tsx` calls Next.js proxy route `POST /api/chat`
- Next.js proxy (`pitwall/app/api/chat/route.ts`) forwards to the FastAPI backend at `NEXT_PUBLIC_API_URL`
- The RAG response includes `sources[0].year/round` — Chat then fetches `GET /api/race` and pushes the result into `RaceContext`
- All left-panel components (`StatCards`, `TireStrategy`, `DriverTable`, `CircuitContext`) are purely consumers of `RaceContext` — they contain no fetch logic of their own

### RAG document structure (`rag/build_docs.py`)
One prose document per race (Year, Round). Structure: race header (winner, podium, DNFs, circuit metadata, winner strategy) followed by one line per driver in finishing order. Chunked at 800 chars / 100 overlap before embedding. The header is always chunk 0; non-winner driver detail lines fall in later chunks — queries about specific non-winner drivers may miss their chunk if `top_k` is too low.

### DNF classification
`Is_DNF` in `jolpica_raw.csv` is derived from Jolpica's `status` string in `feature-groups.py`: anything not in `{'Finished', 'Lapped'}` or starting with `+` is flagged DNF=1. `stage2.py` re-derives this from the `Status` column (if present) with an expanded allow-list that also passes `"Not Classified"` as non-DNF.

### Deployed stack
| Component  | Service |
|------------|---------|
| Frontend   | Vercel (`pitwall/`) |
| Backend    | Render (`api/server.py`) |
| Vector DB  | Qdrant Cloud |
| LLM        | Groq — `qwen/qwen3-32b` |
| Embeddings | Nomic Atlas — `nomic-embed-text-v1.5` (768-dim) |

The Next.js API routes act as a proxy so the browser never calls the Render backend directly. `NEXT_PUBLIC_API_URL` in `pitwall/.env.local` controls which backend the proxy targets.
