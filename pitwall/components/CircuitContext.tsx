"use client";

import { useRace } from "@/components/RaceContext";

export default function CircuitContext() {
  const { race, loading } = useRace();

  const name   = race?.circuit ?? "Ask about a race to load circuit data";
  const type   = race?.circuit_type?.toUpperCase() ?? "—";
  const index  = race?.overtaking_index ?? null;

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
        CIRCUIT CONTEXT
      </div>

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20 }}>
        {/* Left: name + type badge */}
        <div>
          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 13,
              fontWeight: 600,
              color: race ? "#f0f0f0" : "#4a4a55",
              marginBottom: 8,
            }}
          >
            {name}
          </div>
          {race && (
            <div
              style={{
                display: "inline-block",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                fontWeight: 700,
                color: "#e8002d",
                border: "1px solid #e8002d",
                padding: "2px 8px",
                letterSpacing: "0.1em",
              }}
            >
              {type}
            </div>
          )}
        </div>

        {/* Right: overtaking index */}
        <div style={{ flexShrink: 0, minWidth: 140 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: 6,
            }}
          >
            <span
              style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: 10,
                color: "#8a8a9a",
                letterSpacing: "0.1em",
              }}
            >
              OVERTAKING INDEX
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 14,
                fontWeight: 700,
                color: "#f0f0f0",
              }}
            >
              {index ?? "—"}
              {index != null && <span style={{ fontSize: 10, color: "#8a8a9a" }}>/10</span>}
            </span>
          </div>

          {/* Bar */}
          <div
            style={{
              width: "100%",
              height: 6,
              background: "#2e2e36",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: index != null ? `${index * 10}%` : "0%",
                height: "100%",
                background: `linear-gradient(to right, #e8002d, #ff4d4d)`,
                transition: "width 0.6s ease",
              }}
            />
          </div>

          {/* Tick labels */}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            {[1, 5, 10].map((n) => (
              <span
                key={n}
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  color: "#4a4a55",
                }}
              >
                {n}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
