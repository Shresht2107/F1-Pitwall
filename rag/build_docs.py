"""
Convert stage2_dataset.csv + pace_deltas.csv into per-race prose documents
suitable for chunking and embedding.

Each document covers one (Year, Round) and describes all drivers in finishing
order.  Metadata carried alongside: year, round, driver_codes, constructor_ids.
"""

from __future__ import annotations

import csv
import math
import os
from collections import defaultdict
from typing import Any

_DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE2_CSV = os.path.join(_DATA_DIR, "stage2_dataset.csv")
DELTAS_CSV = os.path.join(_DATA_DIR, "pace_deltas.csv")

# Jolpica round-number → circuit name for the seasons we have.
# Covers 2022-2024; rounds not listed fall back to "Round N".
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


def _fmt(val: Any, decimals: int = 1) -> str:
    try:
        f = float(val)
        if math.isnan(f):
            return "n/a"
        return f"{f:.{decimals}f}"
    except (TypeError, ValueError):
        return "n/a"


def _load_csv(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def build_documents() -> list[tuple[str, dict]]:
    """
    Returns a list of (text, metadata) tuples — one per (Year, Round).

    metadata keys: year (int), round (int), drivers (list[str]), constructors (list[str])
    """
    stage2_rows = _load_csv(STAGE2_CSV)
    delta_rows = _load_csv(DELTAS_CSV)

    # Build pace-delta lookup: (year, round, driver) → delta_seconds
    deltas: dict[tuple, float] = {}
    for row in delta_rows:
        key = (int(row["Year"]), int(row["Round"]), row["Driver"])
        try:
            deltas[key] = float(row["Expected_Pace_Delta"])
        except ValueError:
            pass

    # Group stage2 rows by (Year, Round)
    races: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in stage2_rows:
        races[(int(row["Year"]), int(row["Round"]))].append(row)

    documents: list[tuple[str, dict]] = []

    for (year, rnd), drivers in sorted(races.items()):
        circuit = _CIRCUIT_NAMES.get((year, rnd), f"Round {rnd}")

        # Sort: finishers by position, DNFs at the end
        finishers = [d for d in drivers if d["Is_DNF"] == "0" and d["Position"].strip()]
        dnf_drivers = [d for d in drivers if d["Is_DNF"] == "1"]

        try:
            finishers.sort(key=lambda d: int(float(d["Position"])))
        except (ValueError, KeyError):
            pass

        podium_parts = []
        for d in finishers[:3]:
            podium_parts.append(f"{d['Driver']} P{int(float(d['Position']))}")
        podium_str = ", ".join(podium_parts) if podium_parts else "unknown"

        winner = finishers[0] if finishers else None
        winner_str = (
            f"{winner['Driver']} ({winner['Constructor']}) from grid P{winner['GridPosition']}"
            if winner else "unknown"
        )

        dnf_count = len(dnf_drivers)
        dnf_str = (
            ", ".join(d["Driver"] for d in dnf_drivers) if dnf_drivers else "none"
        )

        # ── race-level context (new enrichment fields) ────────────────
        # Use the first finisher row to read race-level constants
        sample = (finishers + dnf_drivers)[0] if (finishers or dnf_drivers) else {}

        circuit_type = sample.get("CircuitType", "")
        overtaking   = sample.get("OvertakingIndex", "")
        is_wet       = sample.get("Is_Wet_Race", "0")
        circuit_ctx  = ""
        if circuit_type and overtaking not in ("", "n/a"):
            circuit_ctx = (f"Circuit: {circuit_type}, overtaking index "
                           f"{_fmt(overtaking, 0)}/10.")
        wet_ctx = "Wet/mixed-conditions race." if str(is_wet).strip() == "1" else ""

        lines = [
            f"[RACE: {year} Round {rnd} — {circuit}]",
        ]
        if circuit_ctx:
            lines.append(circuit_ctx)
        if wet_ctx:
            lines.append(wet_ctx)
        lines += [
            f"Winner: {winner_str}.",
            f"Podium: {podium_str}.",
            f"DNFs ({dnf_count}): {dnf_str}.",
            "",
            "Finishing order:",
        ]

        for d in finishers:
            pos = int(float(d["Position"]))
            delta_key = (year, rnd, d["Driver"])
            delta_val = deltas.get(delta_key)
            delta_str = f"{delta_val:+.1f}s vs optimal" if delta_val is not None else "n/a"

            lap_str    = _fmt(d.get("Median_FuelCorrectedLapTime", ""), 2)
            team_avg   = _fmt(d.get("Team_Rolling_Avg_Finish", ""), 1)
            drv_pts    = _fmt(d.get("Driver_Rolling_Avg_Points", ""), 1)
            track_temp = _fmt(d.get("Avg_TrackTemp", ""), 1)
            stints = d.get("Num_Stints", "n/a")
            try:
                stints = int(float(stints))
            except (ValueError, TypeError):
                stints = "n/a"

            # Qualifying and championship context (may be n/a if not yet fetched)
            q_delta = _fmt(d.get("Q_DeltaToPole", ""), 3)
            q_session = d.get("Q_Session", "")
            q_str = (f"quali {q_delta}s off pole ({q_session})"
                     if q_delta != "n/a" and q_session else "quali n/a")

            champ_pos = d.get("Driver_Championship_Pos", "")
            con_pos   = d.get("Constructor_Championship_Pos", "")
            champ_str = ""
            if champ_pos not in ("", "nan", "n/a"):
                champ_str = f"champ P{_fmt(champ_pos, 0)}"
                if con_pos not in ("", "nan", "n/a"):
                    champ_str += f"/constructor P{_fmt(con_pos, 0)}"

            extra = ", ".join(filter(None, [q_str, champ_str]))

            lines.append(
                f"P{pos} {d['Driver']} ({d['Constructor']}) — "
                f"grid P{d['GridPosition']}, {d['Points']}pts, "
                f"team rolling avg finish {team_avg}, "
                f"driver rolling avg pts {drv_pts}, "
                f"median lap {lap_str}s, "
                f"{stints} stints, track temp {track_temp}°C, "
                f"pace delta {delta_str}"
                + (f", {extra}." if extra else ".")
            )

        for d in dnf_drivers:
            lines.append(
                f"DNF {d['Driver']} ({d['Constructor']}) — grid P{d['GridPosition']}."
            )

        text = "\n".join(lines)

        metadata = {
            "year": year,
            "round": rnd,
            "circuit": circuit,
            "drivers": [d["Driver"] for d in drivers],
            "constructors": list({d["Constructor"] for d in drivers}),
        }

        documents.append((text, metadata))

    return documents


if __name__ == "__main__":
    docs = build_documents()
    print(f"Built {len(docs)} race documents.\n")
    # Print a sample
    text, meta = docs[0]
    print(f"Sample — {meta}")
    print(text)
    print("\n--- char length:", len(text))
