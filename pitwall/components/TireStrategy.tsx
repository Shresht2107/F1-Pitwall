"use client";

import { useState } from "react";
import { useRace } from "@/components/RaceContext";

const COMPOUND_META: Record<string, { label: string; bg: string }> = {
  S: { label: "Soft",         bg: "#8b1a1a" },
  M: { label: "Medium",       bg: "#8b7a1a" },
  H: { label: "Hard",         bg: "#4a4a55" },
  I: { label: "Inter",        bg: "#1a5c1a" },
  W: { label: "Wet",          bg: "#1a3a8b" },
  "?": { label: "Unknown",    bg: "#3a3a45" },
};

// Fallback canonical sequences when we have a stint count but no summary string
const CANONICAL: Record<number, string> = {
  1: "H:1",
  2: "M:1,H:1",
  3: "S:1,M:1,H:1",
  4: "S:1,M:1,M:1,H:1",
};

interface Stint {
  code: string;
  laps: number;
  bg: string;
  label: string;
}

function parseStrategy(summary: string): Stint[] {
  return summary.split(",").map((seg) => {
    const [code, laps] = seg.trim().split(":");
    const meta = COMPOUND_META[code?.toUpperCase()] ?? COMPOUND_META["?"];
    return { code: code?.toUpperCase() ?? "?", laps: parseInt(laps, 10) || 1, ...meta };
  });
}

export default function TireStrategy() {
  const [hovered, setHovered] = useState<number | null>(null);
  const { race, loading } = useRace();

  const winner = race?.drivers.find((d) => d.code === race.winner);

  const strategySummary =
    winner?.strategy_summary ??
    (winner?.num_stints != null ? CANONICAL[winner.num_stints] ?? CANONICAL[3] : null);

  const stints: Stint[] | null = strategySummary ? parseStrategy(strategySummary) : null;
  const totalLaps = stints ? stints.reduce((s, t) => s + t.laps, 0) : 0;
  const isReal = !!winner?.strategy_summary;

  // Unique compounds for legend
  const legendCompounds: Stint[] = stints
    ? [...new Map(stints.map((s) => [s.code, s])).values()]
    : (Object.entries(COMPOUND_META).slice(0, 3).map(([code, meta]) => ({ code, laps: 0, ...meta })));

  return (
    <div
      style={{
        background: "#222228",
        border: "1px solid #2e2e36",
        padding: 20,
        opacity: loading ? 0.5 : 1,
        transition: "opacity 0.3s",
      }}
    >
      <div
        style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 11,
          fontWeight: 700,
          color: "#8a8a9a",
          letterSpacing: "0.2em",
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        TIRE STRATEGY — WINNER
        {stints && !isReal && (
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: "#4a4a55", fontWeight: 400 }}>
            CANONICAL ESTIMATE
          </span>
        )}
      </div>

      {stints ? (
        <>
          <div style={{ display: "flex", gap: 0, height: 36, overflow: "hidden", marginBottom: 12 }}>
            {stints.map((s, i) => (
              <div
                key={i}
                data-interactive
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  flex: s.laps,
                  background: s.bg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRight: i < stints.length - 1 ? "2px solid #1a1a1f" : undefined,
                  opacity: hovered === i ? 0.75 : 1,
                  transition: "opacity 0.2s",
                  overflow: "hidden",
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#f0f0f0",
                    whiteSpace: "nowrap",
                    padding: "0 4px",
                  }}
                >
                  {isReal ? `${s.code} · ${s.laps}` : s.code}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            {legendCompounds.map((l) => (
              <div key={l.code} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 10, height: 10, background: l.bg, flexShrink: 0 }} />
                <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, color: "#8a8a9a" }}>
                  {l.label}
                </span>
              </div>
            ))}
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                color: "#8a8a9a",
                marginLeft: "auto",
              }}
            >
              {stints.length - 1}-stop · {isReal ? `${totalLaps} laps` : `${stints.length} stints`}
            </span>
          </div>
        </>
      ) : (
        <div
          style={{
            height: 36,
            background: "#1e1e24",
            display: "flex",
            alignItems: "center",
            paddingLeft: 16,
            marginBottom: 12,
          }}
        >
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#4a4a55" }}>
            Ask about a race to see strategy
          </span>
        </div>
      )}
    </div>
  );
}
