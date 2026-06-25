"use client";

import { useRace } from "@/components/RaceContext";

function fmt(v: number | null | undefined, decimals = 2, prefix = ""): string {
  if (v == null) return "—";
  return `${prefix}${v.toFixed(decimals)}`;
}

export default function StatCards() {
  const { race, loading } = useRace();

  const winner = race?.drivers.find((d) => d.code === race.winner);

  // P2 driver for qual delta (pole sitter's delta is always 0.000)
  const p2 = race?.drivers.find((d) => d.position === 2);

  const stats = [
    {
      label: "GRID POSITION",
      value: winner ? `P${winner.grid}` : "—",
    },
    {
      label: "STRATEGY DELTA",
      value: winner?.pace_delta != null
        ? `${winner.pace_delta >= 0 ? "+" : ""}${winner.pace_delta.toFixed(1)}s`
        : "—",
    },
    {
      label: "QUAL Δ P2 TO POLE",
      value: p2?.q_delta != null ? `+${p2.q_delta.toFixed(3)}s` : "—",
    },
    {
      label: "CHAMPIONSHIP POS",
      value: winner?.champ_pos != null ? `P${winner.champ_pos}` : "—",
    },
    {
      label: "DNFs",
      value: race ? String(race.drivers.filter((d) => d.is_dnf).length) : "—",
    },
    {
      label: "CONDITIONS",
      value: race ? (race.is_wet ? "WET" : "DRY") : "—",
      badge: true,
      badgeColor: race?.is_wet ? "#3b82f6" : "#22c55e",
    },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 12,
        opacity: loading ? 0.5 : 1,
        transition: "opacity 0.3s",
      }}
    >
      {stats.map((s) => (
        <div
          key={s.label}
          style={{
            background: "#222228",
            border: "1px solid #2e2e36",
            borderLeft: "3px solid #e8002d",
            padding: 16,
          }}
        >
          {"badge" in s && s.badge ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: s.badgeColor ?? "#22c55e",
                  flexShrink: 0,
                }}
              />
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 24,
                  fontWeight: 700,
                  color: "#f0f0f0",
                  lineHeight: 1,
                }}
              >
                {s.value}
              </div>
            </div>
          ) : (
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 28,
                fontWeight: 700,
                color: "#f0f0f0",
                lineHeight: 1,
              }}
            >
              {s.value}
            </div>
          )}
          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 10,
              color: "#8a8a9a",
              marginTop: 6,
              letterSpacing: "0.1em",
            }}
          >
            {s.label}
          </div>
        </div>
      ))}
    </div>
  );
}
