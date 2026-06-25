# Dynamic Race Analysis — Implementation Plan

## What exists now

Every component in the Race Analysis panel is fully hardcoded:

| Component | What it shows (hardcoded) |
|-----------|--------------------------|
| `StatCards` | P1, +1.4s, 87%, +0.34s, P3, DRY — static strings, never change |
| `CircuitContext` | Circuit de Spa-Francorchamps, PERMANENT, overtaking index 7 |
| `TireStrategy` | S/18 laps · M/19 laps · H/7 laps, "Predicted undercut: Lap 19" |
| `DriverTable` | VER/NOR/PIA/LEC/HAM with fabricated grid/delta/champ/strategy values |

The `Chat` component already calls `/api/chat` and the FastAPI backend already
returns `sources: [{year, round, circuit, score}]` alongside `answer`. Chat
currently throws sources away — they are never stored or acted on.

---

## Requirements

### Data
- `stage2_dataset.csv` has per-driver per-race: `GridPosition`, `Position`,
  `Is_DNF`, `Points`, `Q_DeltaToPole`, `Q_Session`, `Driver_Championship_Pos`,
  `Constructor_Championship_Pos`, `Team_Rolling_Avg_Finish`,
  `Driver_Rolling_Avg_Points`, `OvertakingIndex`, `CircuitType`, `Is_Wet_Race`,
  `Num_Stints`, `Median_FuelCorrectedLapTime`.
- `pace_deltas.csv` has per-driver per-race: `Expected_Pace_Delta`.
- Both CSVs are on disk next to `api/server.py` and can be loaded at startup.
- **Tire stints (S/M/H lap counts)** are NOT in the CSVs — only `Num_Stints` is.
  TireStrategy will show canonical one-stop / two-stop strategy labels based on
  stint count rather than exact per-lap breakdown.

### Backend
- New endpoint: `GET /race?year={Y}&round={R}` — returns structured JSON for
  one race: circuit metadata + all drivers' stats + pace deltas.
- Both CSVs loaded once at startup and kept in memory (DataFrames); no disk I/O
  per request.

### Frontend state management
- A new React context (`RaceContext`) holds the "active race" payload and an
  `isLoading` flag.
- `Chat` is the **producer**: after receiving an AI response, it reads
  `sources[0]` → fetches `/api/race` → pushes result into context.
- `StatCards`, `CircuitContext`, `TireStrategy`, `DriverTable` are
  **consumers**: they read from context instead of hardcoded constants.
- If context is null (page first load, or a query not about a specific race),
  components show a placeholder/skeleton state.

### Chat → `/api/chat` route change
- The Next.js `/api/chat` proxy needs to forward `sources` from the Python
  backend to the client (it currently does — `data` is forwarded as-is, and
  `sources` is already in the Python response).

---

## Step-by-step Plan

### Step 1 — Backend: `/race` endpoint in `api/server.py`

Load `stage2_dataset.csv` and `pace_deltas.csv` into module-level DataFrames
at startup. Add:

```
GET /race?year=2024&round=3
```

Response shape:
```json
{
  "year": 2024,
  "round": 3,
  "circuit": "Australian GP",
  "circuit_type": "permanent",
  "overtaking_index": 6,
  "is_wet": false,
  "winner": "NOR",
  "podium": ["NOR", "SAI", "LEC"],
  "drivers": [
    {
      "code": "NOR",
      "constructor": "mclaren",
      "grid": 1,
      "position": 1,
      "is_dnf": false,
      "points": 25.0,
      "q_delta": 0.0,
      "q_session": "Q3",
      "champ_pos": 3,
      "constructor_champ_pos": 2,
      "team_rolling_avg_finish": 4.3,
      "driver_rolling_avg_pts": 12.1,
      "pace_delta": -0.8,
      "num_stints": 2,
      "median_lap": 90.12
    },
    ...
  ]
}
```

Drivers sorted: finishers by position, then DNFs.

### Step 2 — Frontend: Next.js API proxy for `/race`

Create `pitwall/app/api/race/route.ts`:
- `GET /api/race?year=Y&round=R` → forwards to `http://localhost:8000/race?year=Y&round=R`
- Same CORS boundary pattern as the existing `/api/chat` proxy.

### Step 3 — Frontend: `RaceContext`

Create `pitwall/components/RaceContext.tsx`:
- React context with shape `{ race: RaceData | null, loading: boolean, setRace }`.
- Export a `RaceProvider` wrapper and a `useRace()` hook.
- `RaceData` TypeScript type mirrors the JSON shape from Step 1.

Wrap `DashboardPage` in `<RaceProvider>` in `pitwall/app/dashboard/page.tsx`.

### Step 4 — `Chat.tsx`: emit race context on each AI response

After `fetch("/api/chat")` succeeds and `data.answer` is set:
1. Check `data.sources` — if `sources.length > 0` and `sources[0].year` and
   `sources[0].round` are present:
2. Call `fetch(\`/api/race?year=${sources[0].year}&round=${sources[0].round}\`)`
3. On success, call `setRace(raceData)` from `useRace()`.

This means the panel updates automatically when the user asks about any race.
If the query has no race sources (e.g. "how does the model work?"), context
stays unchanged.

### Step 5 — `StatCards.tsx`: consume context

Replace hardcoded `STATS` array. Read from `useRace()`. Map to:
- **GRID POSITION** — winner's `grid`
- **STRATEGY DELTA** — winner's `pace_delta` formatted as `+X.Xs`
- **PODIUM PROBABILITY** — omit or show `—` (pre-race prediction not stored per race; can add later)
- **QUAL Δ TO POLE** — winner's `q_delta` (will be `0.000` for pole sitter — show P2's delta instead, or label as "Pole Gap P2")
- **CHAMPIONSHIP POS** — winner's `champ_pos`
- **CONDITIONS** — `is_wet ? "WET" : "DRY"`

Show `—` for every stat while `race === null` or `loading === true`.

### Step 6 — `CircuitContext.tsx`: consume context

Replace three hardcoded constants with `race.circuit_type`,
`race.overtaking_index`, and `race.circuit` from context. The overtaking index
bar animation already supports dynamic values via the percentage width.

### Step 7 — `TireStrategy.tsx`: consume context

The CSVs don't contain per-lap stint breakdowns, only `Num_Stints`. Replace
the hardcoded stint bars with a simplified view:
- Show `race.drivers[0].num_stints` stints for the winner
- Assign canonical compound colours: 1 stint = H only, 2 stints = M→H,
  3 stints = S→M→H. Label each bar with the compound letter and "?" for laps.
- Remove "Predicted undercut: Lap 19" (that was fabricated); replace with
  `{num_stints}-stop strategy (winner)`.

If we want exact stint data in the future, we can add a new endpoint that reads
from the FastF1 laps cache (Stage 1 output) — that's a separate task.

### Step 8 — `DriverTable.tsx`: consume context

Replace hardcoded `DRIVERS` array. Map `race.drivers` (all finishers, then
DNFs) to table rows. Column mapping:
- `DRIVER` → `code`
- `GRID` → `grid` formatted as "P{n}"
- `STRATEGY` → `{num_stints}-stop` (placeholder; exact compound sequence not available)
- `Q Δ` → `q_delta` formatted as `+{n.nnn}s`
- `CHAMP` → `champ_pos` formatted as "P{n}"
- `PACE Δ` → `pace_delta` formatted as `{+/-n.ns}`
- `PRED` → remove or replace with actual `position` (post-race result)

Highlight row where `code === race.winner`.
Show skeleton rows (greyed dashes) while `loading === true`.

### Step 9 — `Ticker.tsx` and header lap counter (optional polish)

The "LAP XX / 44" counter in the header is currently a cosmetic animation.
Once race context is set, replace `/ 44` with the actual race lap count
(derivable from `max(drivers[*].num_stints) * avg_stint_len` — approximate, or
just hide it). Low priority.

---

## What this does NOT include (out of scope for this plan)

- Storing or computing per-race **podium probability** from Stage 4 (would need
  to save stage4 predictions per race, not just final metrics).
- Exact **tire stint lap counts** (needs a new endpoint reading FastF1 cache
  laps — feasible but separate task).
- **Driver selection** — showing stats for a specific queried driver rather than
  always the winner. Could be added later by passing a driver code from the
  chat sources.
- **Race selector UI** — a dropdown to pick race manually without querying.
  The plan keeps it query-driven only.

---

## File change summary

| File | Change |
|------|--------|
| `api/server.py` | Add `GET /race` endpoint + load CSVs at startup |
| `pitwall/app/api/race/route.ts` | New: proxy to Python `/race` |
| `pitwall/components/RaceContext.tsx` | New: context + provider + hook |
| `pitwall/app/dashboard/page.tsx` | Wrap children in `<RaceProvider>` |
| `pitwall/components/Chat.tsx` | After AI response, fetch race + call `setRace` |
| `pitwall/components/StatCards.tsx` | Read from `useRace()`, remove hardcoded STATS |
| `pitwall/components/CircuitContext.tsx` | Read from `useRace()`, remove hardcoded constants |
| `pitwall/components/TireStrategy.tsx` | Read from `useRace()`, simplify stint display |
| `pitwall/components/DriverTable.tsx` | Read from `useRace()`, remove hardcoded DRIVERS |
