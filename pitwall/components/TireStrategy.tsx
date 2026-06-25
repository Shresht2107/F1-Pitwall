"use client";

import { useState } from "react";
import { useRace } from "@/components/RaceContext";

// Canonical compound sequences by stint count
const COMPOUND_SEQUENCES: Record<number, { compound: string; bg: string }[]> = {
  1: [{ compound: "H", bg: "#4a4a55" }],
  2: [{ compound: "M", bg: "#8b7a1a" }, { compound: "H", bg: "#4a4a55" }],
  3: [{ compound: "S", bg: "#8b1a1a" }, { compound: "M", bg: "#8b7a1a" }, { compound: "H", bg: "#4a4a55" }],
  4: [{ compound: "S", bg: "#8b1a1a" }, { compound: "M", bg: "#8b7a1a" }, { compound: "M", bg: "#8b7a1a" }, { compound: "H", bg: "#4a4a55" }],
};

const LEGEND = [
  { label: "Soft",   bg: "#8b1a1a" },
  { label: "Medium", bg: "#8b7a1a" },
  { label: "Hard",   bg: "#4a4a55" },
];

export default function TireStrategy() {
  const [hovered, setHovered] = useState<number | null>(null);
  const { race, loading } = useRace();

  const winner = race?.drivers.find((d) => d.code === race.winner);
  const numStints = winner?.num_stints ?? null;
  const stints = numStints != null
    ? (COMPOUND_SEQUENCES[numStints] ?? COMPOUND_SEQUENCES[3])
    : null;

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
        }}
      >
        TIRE STRATEGY — WINNER
      </div>

      {stints ? (
        <>
          <div
            style={{
              display: "flex",
              gap: 0,
              height: 36,
              overflow: "hidden",
              marginBottom: 12,
            }}
          >
            {stints.map((s, i) => (
              <div
                key={i}
                data-interactive
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  flex: 1,
                  background: s.bg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRight: i < stints.length - 1 ? "2px solid #1a1a1f" : undefined,
                  opacity: hovered === i ? 0.75 : 1,
                  transition: "opacity 0.2s",
                }}
              >
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12,
                    fontWeight: 700,
                    color: "#f0f0f0",
                  }}
                >
                  {s.compound}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 20 }}>
            {LEGEND.map((l) => (
              <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 10, height: 10, background: l.bg }} />
                <span
                  style={{
                    fontFamily: "'Inter', sans-serif",
                    fontSize: 11,
                    color: "#8a8a9a",
                  }}
                >
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
              {numStints != null ? `${numStints - 1}-stop strategy` : ""}
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
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: "#4a4a55",
            }}
          >
            Ask about a race to see strategy
          </span>
        </div>
      )}
    </div>
  );
}
