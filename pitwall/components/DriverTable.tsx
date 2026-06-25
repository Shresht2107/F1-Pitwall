"use client";

import { useRace } from "@/components/RaceContext";

const HEADERS = [
  { label: "POS",     align: "center" as const, pad: "10px 10px" },
  { label: "DRIVER",  align: "left"   as const, pad: "10px 12px" },
  { label: "GRID",    align: "center" as const, pad: "10px 8px"  },
  { label: "STINTS",  align: "center" as const, pad: "10px 8px"  },
  { label: "Q Δ",     align: "right"  as const, pad: "10px 8px"  },
  { label: "CHAMP",   align: "center" as const, pad: "10px 8px"  },
  { label: "PACE Δ",  align: "right"  as const, pad: "10px 12px" },
];

function fmt(v: number | null, decimals: number, sign = false): string {
  if (v == null) return "—";
  const s = v.toFixed(decimals);
  return sign && v > 0 ? `+${s}` : s;
}

// Skeleton rows shown while loading
function SkeletonRow({ i }: { i: number }) {
  return (
    <tr style={{ background: i % 2 === 0 ? "#222228" : "#1e1e24" }}>
      {HEADERS.map((h) => (
        <td key={h.label} style={{ padding: h.pad, textAlign: h.align }}>
          <div
            style={{
              height: 12,
              width: "60%",
              background: "#2e2e36",
              margin: "0 auto",
              borderRadius: 2,
            }}
          />
        </td>
      ))}
    </tr>
  );
}

export default function DriverTable() {
  const { race, loading } = useRace();

  return (
    <div style={{ background: "#222228", border: "1px solid #2e2e36" }}>
      <div style={{ padding: "14px 16px", borderBottom: "1px solid #2e2e36", display: "flex", alignItems: "baseline", gap: 12 }}>
        <div
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: 11,
            fontWeight: 700,
            color: "#8a8a9a",
            letterSpacing: "0.2em",
          }}
        >
          DRIVER COMPARISON
        </div>
        {race && (
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: "#4a4a55",
            }}
          >
            {race.year} · {race.circuit}
          </div>
        )}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#1e1e24" }}>
            {HEADERS.map((h) => (
              <th
                key={h.label}
                style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: 9,
                  fontWeight: 600,
                  color: "#8a8a9a",
                  letterSpacing: "0.1em",
                  padding: h.pad,
                  textAlign: h.align,
                  whiteSpace: "nowrap",
                }}
              >
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading && !race
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} i={i} />)
            : race?.drivers.map((d, i) => {
                const isWinner = d.code === race.winner;
                const posLabel = d.is_dnf ? "DNF" : d.position != null ? `P${d.position}` : "—";
                const stintLabel = d.num_stints != null ? `${d.num_stints - 1}-stop` : "—";
                const paceDelta = d.pace_delta != null
                  ? `${d.pace_delta >= 0 ? "+" : ""}${d.pace_delta.toFixed(1)}s`
                  : "—";

                return (
                  <tr
                    key={d.code}
                    style={{
                      background: i % 2 === 0 ? "#222228" : "#1e1e24",
                      boxShadow: isWinner ? "inset 3px 0 0 #e8002d" : undefined,
                      opacity: d.is_dnf ? 0.5 : 1,
                    }}
                  >
                    <td
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                        color: d.is_dnf ? "#8a8a9a" : "#f0f0f0",
                        padding: "10px 10px",
                        textAlign: "center",
                        fontWeight: isWinner ? 700 : undefined,
                      }}
                    >
                      {posLabel}
                    </td>
                    <td
                      style={{
                        fontFamily: "'Inter', sans-serif",
                        fontSize: 13,
                        fontWeight: 600,
                        color: isWinner ? "#e8002d" : "#f0f0f0",
                        padding: "10px 12px",
                      }}
                    >
                      {d.code}
                    </td>
                    <td
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                        color: "#f0f0f0",
                        padding: "10px 8px",
                        textAlign: "center",
                      }}
                    >
                      {d.grid != null ? `P${d.grid}` : "—"}
                    </td>
                    <td
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 10,
                        color: "#8a8a9a",
                        padding: "10px 8px",
                        textAlign: "center",
                      }}
                    >
                      {stintLabel}
                    </td>
                    <td
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                        color: "#8a8a9a",
                        padding: "10px 8px",
                        textAlign: "right",
                      }}
                    >
                      {d.q_delta != null ? `+${d.q_delta.toFixed(3)}s` : "—"}
                    </td>
                    <td
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                        color: "#f0f0f0",
                        padding: "10px 8px",
                        textAlign: "center",
                      }}
                    >
                      {d.champ_pos != null ? `P${d.champ_pos}` : "—"}
                    </td>
                    <td
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                        color: d.pace_delta != null && d.pace_delta < 0 ? "#22c55e" : "#f0f0f0",
                        padding: "10px 12px",
                        textAlign: "right",
                      }}
                    >
                      {paceDelta}
                    </td>
                  </tr>
                );
              }) ?? (
              <tr>
                <td
                  colSpan={HEADERS.length}
                  style={{
                    padding: "24px 16px",
                    textAlign: "center",
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11,
                    color: "#4a4a55",
                  }}
                >
                  Ask about a race to see driver data
                </td>
              </tr>
            )}
        </tbody>
      </table>
    </div>
  );
}
