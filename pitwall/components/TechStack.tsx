"use client";

import { useState } from "react";

const CARDS = [
  { icon: "📡", name: "FastF1",           desc: "Lap telemetry & session data" },
  { icon: "🌐", name: "Jolpica-F1 API",   desc: "Race results, qualifying times & championship standings" },
  { icon: "⚡", name: "XGBoost",          desc: "Lap-time regressor + podium classifier" },
  { icon: "🔷", name: "Qdrant",           desc: "Local vector store for RAG retrieval" },
  { icon: "🤖", name: "Ollama / Qwen3:4b",desc: "Local LLM for natural-language generation" },
  { icon: "🧮", name: "nomic-embed-text", desc: "Sentence embeddings for semantic search" },
];

function TechCard({ icon, name, desc }: { icon: string; name: string; desc: string }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      data-interactive
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: "#222228",
        border: `1px solid ${hovered ? "#3e3e46" : "#2e2e36"}`,
        padding: 20,
        textAlign: "left",
        position: "relative",
        overflow: "hidden",
        transition: "border-color 0.2s",
      }}
    >
      <div style={{ fontSize: 22, marginBottom: 10 }}>{icon}</div>
      <div
        style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 14,
          fontWeight: 600,
          color: "#f0f0f0",
          marginBottom: 4,
        }}
      >
        {name}
      </div>
      <div
        style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 12,
          color: "#8a8a9a",
        }}
      >
        {desc}
      </div>
      {/* top accent bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: 2,
          background: "#e8002d",
          opacity: hovered ? 1 : 0,
          transition: "opacity 0.2s",
        }}
      />
    </div>
  );
}

export default function TechStack() {
  return (
    <div style={{ width: "100%", maxWidth: 860, marginBottom: 56 }}>
      <div
        style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 11,
          fontWeight: 600,
          color: "#8a8a9a",
          letterSpacing: "0.2em",
          marginBottom: 20,
          textAlign: "left",
        }}
      >
        TECH STACK
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12,
        }}
      >
        {CARDS.map((c) => (
          <TechCard key={c.name} {...c} />
        ))}
      </div>
    </div>
  );
}
