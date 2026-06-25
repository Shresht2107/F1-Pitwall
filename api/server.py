"""
Thin FastAPI wrapper around the RAG pipeline.
Exposes POST /chat and GET /race so the Next.js frontend can call them.

Run from the project root:
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import math
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.retrieve import retrieve
from rag.generate import generate

app = FastAPI(title="PIT WALL RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Load CSVs once at startup ─────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_stage2 = pd.read_csv(os.path.join(_ROOT, "stage2_dataset.csv"))
_deltas = pd.read_csv(os.path.join(_ROOT, "pace_deltas.csv"))

# Friendly circuit names for the (year, round) pairs we have
_CIRCUIT_NAMES: dict[tuple[int, int], str] = {
    (2022, 1): "Bahrain GP", (2022, 2): "Saudi Arabian GP", (2022, 3): "Australian GP",
    (2022, 4): "Emilia Romagna GP", (2022, 5): "Miami GP", (2022, 6): "Spanish GP",
    (2022, 7): "Monaco GP", (2022, 8): "Azerbaijan GP", (2022, 9): "Canadian GP",
    (2022, 10): "British GP", (2022, 11): "Austrian GP", (2022, 12): "French GP",
    (2022, 13): "Hungarian GP", (2022, 14): "Belgian GP", (2022, 15): "Dutch GP",
    (2022, 16): "Italian GP", (2022, 17): "Singapore GP", (2022, 18): "Japanese GP",
    (2022, 19): "United States GP", (2022, 20): "Mexico City GP",
    (2022, 21): "São Paulo GP", (2022, 22): "Abu Dhabi GP",
    (2023, 1): "Bahrain GP", (2023, 2): "Saudi Arabian GP", (2023, 3): "Australian GP",
    (2023, 4): "Azerbaijan GP", (2023, 5): "Miami GP", (2023, 6): "Monaco GP",
    (2023, 7): "Spanish GP", (2023, 8): "Canadian GP", (2023, 9): "Austrian GP",
    (2023, 10): "British GP", (2023, 11): "Hungarian GP", (2023, 12): "Belgian GP",
    (2023, 13): "Dutch GP", (2023, 14): "Italian GP", (2023, 15): "Singapore GP",
    (2023, 16): "Japanese GP", (2023, 17): "Qatar GP", (2023, 18): "United States GP",
    (2023, 19): "Mexico City GP", (2023, 20): "São Paulo GP",
    (2023, 21): "Las Vegas GP", (2023, 22): "Abu Dhabi GP",
    (2024, 1): "Bahrain GP", (2024, 2): "Saudi Arabian GP", (2024, 3): "Australian GP",
    (2024, 4): "Japanese GP", (2024, 5): "Chinese GP", (2024, 6): "Miami GP",
    (2024, 7): "Emilia Romagna GP", (2024, 8): "Monaco GP", (2024, 9): "Canadian GP",
    (2024, 10): "Spanish GP", (2024, 11): "Austrian GP", (2024, 12): "British GP",
    (2024, 13): "Hungarian GP", (2024, 14): "Belgian GP", (2024, 15): "Dutch GP",
    (2024, 16): "Italian GP", (2024, 17): "Azerbaijan GP", (2024, 18): "Singapore GP",
    (2024, 19): "United States GP", (2024, 20): "Mexico City GP",
    (2024, 21): "São Paulo GP", (2024, 22): "Las Vegas GP",
    (2024, 23): "Qatar GP", (2024, 24): "Abu Dhabi GP",
}


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    f = _safe_float(val)
    return int(f) if f is not None else None


# ── Models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
    think: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


# ── Routes ────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    chunks = retrieve(req.query, top_k=req.top_k)
    answer = generate(req.query, chunks, think=req.think)
    sources = [
        {"year": c["year"], "round": c["round"], "circuit": c["circuit"], "score": c["score"]}
        for c in chunks
    ]
    return ChatResponse(answer=answer, sources=sources)


@app.get("/race")
def race(year: int = Query(...), round: int = Query(...)) -> dict:
    race_rows = _stage2[(_stage2["Year"] == year) & (_stage2["Round"] == round)].copy()
    if race_rows.empty:
        raise HTTPException(status_code=404, detail=f"No data for {year} R{round}")

    delta_rows = _deltas[(_deltas["Year"] == year) & (_deltas["Round"] == round)].set_index("Driver")

    # Race-level fields from the first row (they're the same for every driver)
    sample = race_rows.iloc[0]
    circuit_name  = _CIRCUIT_NAMES.get((year, round), f"Round {round}")
    circuit_type  = str(sample.get("CircuitType", "")).capitalize()
    overtaking    = _safe_int(sample.get("OvertakingIndex"))
    is_wet        = bool(_safe_int(sample.get("Is_Wet_Race")) == 1)
    avg_track_temp = _safe_float(sample.get("Avg_TrackTemp"))

    # Sort: finishers by position, then DNFs
    finishers = race_rows[race_rows["Is_DNF"] == 0].copy()
    dnfs      = race_rows[race_rows["Is_DNF"] == 1].copy()
    try:
        finishers = finishers.sort_values("Position")
    except Exception:
        pass

    drivers_out = []
    for _, row in pd.concat([finishers, dnfs], ignore_index=True).iterrows():
        code = str(row["Driver"])
        pace_delta = _safe_float(delta_rows.at[code, "Expected_Pace_Delta"]) \
            if code in delta_rows.index else None
        drivers_out.append({
            "code":                   code,
            "constructor":            str(row.get("Constructor", "")),
            "grid":                   _safe_int(row.get("GridPosition")),
            "position":               _safe_int(row.get("Position")),
            "is_dnf":                 bool(int(row.get("Is_DNF", 0))),
            "points":                 _safe_float(row.get("Points")),
            "q_delta":                _safe_float(row.get("Q_DeltaToPole")),
            "q_session":              str(row.get("Q_Session", "")) or None,
            "champ_pos":              _safe_int(row.get("Driver_Championship_Pos")),
            "constructor_champ_pos":  _safe_int(row.get("Constructor_Championship_Pos")),
            "team_rolling_avg_finish":_safe_float(row.get("Team_Rolling_Avg_Finish")),
            "driver_rolling_avg_pts": _safe_float(row.get("Driver_Rolling_Avg_Points")),
            "pace_delta":             pace_delta,
            "num_stints":             _safe_int(row.get("Num_Stints")),
            "median_lap":             _safe_float(row.get("Median_FuelCorrectedLapTime")),
        })

    podium = [d["code"] for d in drivers_out if d["position"] and d["position"] <= 3]
    winner = drivers_out[0]["code"] if drivers_out and not drivers_out[0]["is_dnf"] else None

    return {
        "year":             year,
        "round":            round,
        "circuit":          circuit_name,
        "circuit_type":     circuit_type,
        "overtaking_index": overtaking,
        "is_wet":           is_wet,
        "avg_track_temp":   avg_track_temp,
        "winner":           winner,
        "podium":           podium,
        "drivers":          drivers_out,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
