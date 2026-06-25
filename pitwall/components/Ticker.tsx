"use client";

import { useRace } from "@/components/RaceContext";

const PLACEHOLDER = [
  { text: "PIT WALL — RACE ANALYSIS SYSTEM", highlight: true },
  { text: "ASK A QUESTION IN THE CHAT TO LOAD RACE DATA", highlight: false },
  { text: "POWERED BY QDRANT · NOMIC-EMBED-TEXT · QWEN3:4B", highlight: false },
  { text: "2022 – 2024 SEASONS · 69 RACES · XGBOOST CLASSIFIER", highlight: true },
];

export default function Ticker() {
  const { race } = useRace();

  let items: { text: string; highlight: boolean }[];

  if (!race) {
    items = PLACEHOLDER;
  } else {
    const finishers = race.drivers.filter((d) => !d.is_dnf);
    const dnfs = race.drivers.filter((d) => d.is_dnf);

    const driverItems = finishers.map((d) => ({
      text: `P${d.position}  ${d.code}  ${
        d.pace_delta != null
          ? `${d.pace_delta >= 0 ? "+" : ""}${d.pace_delta.toFixed(1)}s`
          : "—"
      }`,
      highlight: d.code === race.winner,
    }));

    const podiumText = race.podium.length > 0
      ? `PODIUM  ${race.podium.map((c, i) => `P${i + 1} ${c}`).join("  ·  ")}`
      : null;

    const conditionsText = [
      race.avg_track_temp != null ? `TRACK ${race.avg_track_temp.toFixed(0)}°C` : null,
      race.is_wet ? "WET" : "DRY",
    ]
      .filter(Boolean)
      .join("  ·  ");

    const circuitText = [
      race.circuit_type?.toUpperCase(),
      race.overtaking_index != null ? `OI ${race.overtaking_index}/10` : null,
    ]
      .filter(Boolean)
      .join("  ·  ");

    const dnfText =
      dnfs.length > 0 ? `DNF  ${dnfs.map((d) => d.code).join("  ")}` : null;

    items = [
      { text: `${race.year}  R${race.round}  —  ${race.circuit.toUpperCase()}`, highlight: true },
      ...driverItems,
      ...(dnfText ? [{ text: dnfText, highlight: false }] : []),
      { text: conditionsText, highlight: true },
      { text: circuitText, highlight: false },
      ...(podiumText ? [{ text: podiumText, highlight: true }] : []),
    ];
  }

  const content = [...items, ...items];
  const duration = Math.max(20, items.length * 3);

  return (
    <div
      style={{
        background: "#222228",
        borderBottom: "1px solid #2e2e36",
        overflow: "hidden",
        height: 28,
        flexShrink: 0,
      }}
    >
      <div
        key={race ? `${race.year}-${race.round}` : "placeholder"}
        style={{
          display: "flex",
          alignItems: "center",
          whiteSpace: "nowrap",
          animation: `tickerScroll ${duration}s linear infinite`,
          height: "100%",
        }}
      >
        {content.map((item, i) => (
          <span
            key={i}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: item.highlight ? "#e8002d" : "#8a8a9a",
              padding: "0 32px",
              borderRight: "1px solid #2e2e36",
            }}
          >
            {item.text}
          </span>
        ))}
      </div>
    </div>
  );
}
