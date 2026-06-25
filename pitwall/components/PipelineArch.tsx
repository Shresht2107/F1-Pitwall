const STAGES = [
  {
    id: "S0",
    lines: ["DATA", "COLLECTION"],
    sub: "FastF1 + Jolpica",
    feeds: ["results", "qualifying", "standings"],
    dashed: false,
  },
  {
    id: "S1",
    lines: ["FEATURE", "ENGINEERING"],
    sub: "Pace · rolling · qual · standings",
    feeds: [],
    dashed: false,
  },
  {
    id: "S2",
    lines: ["DATASET", "ASSEMBLY"],
    sub: "Merge + circuits + wet flag",
    feeds: ["circuits.csv"],
    dashed: false,
  },
  {
    id: "S3",
    lines: ["PODIUM", "CLASSIFIER"],
    sub: "XGBoost + Monte Carlo",
    feeds: [],
    dashed: false,
  },
  {
    id: "S4",
    lines: ["RAG", "Q&A"],
    sub: "Qdrant + Qwen3",
    feeds: [],
    dashed: true,
  },
];

const FEED_COLORS: Record<string, string> = {
  results:     "#3a3a44",
  qualifying:  "#3a3a44",
  standings:   "#3a3a44",
  "circuits.csv": "#2e2e36",
};

function Arrow() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        paddingTop: 40,
        flexShrink: 0,
        width: 24,
      }}
    >
      <svg width="24" height="12" viewBox="0 0 24 12">
        <line x1="0" y1="6" x2="20" y2="6" stroke="#2e2e36" strokeWidth="1.5" />
        <polygon points="18,2 24,6 18,10" fill="#2e2e36" />
      </svg>
    </div>
  );
}

export default function PipelineArch() {
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
        PIPELINE ARCHITECTURE
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 0,
          overflowX: "auto",
          paddingBottom: 8,
        }}
      >
        {STAGES.map((s, i) => (
          <div key={s.id} style={{ display: "contents" }}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                flex: 1,
                minWidth: 120,
              }}
            >
              {/* Stage ID */}
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#e8002d",
                  marginBottom: 6,
                  letterSpacing: "0.1em",
                }}
              >
                {s.id}
              </div>

              {/* Stage box */}
              <div
                style={{
                  background: "#222228",
                  border: s.dashed ? "2px dashed #2e2e36" : "1px solid #2e2e36",
                  padding: "12px 10px",
                  width: "100%",
                  textAlign: "center",
                }}
              >
                {s.lines.map((l) => (
                  <div
                    key={l}
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#f0f0f0",
                      letterSpacing: "0.1em",
                    }}
                  >
                    {l}
                  </div>
                ))}
                <div
                  style={{
                    fontFamily: "'Inter', sans-serif",
                    fontSize: 10,
                    color: "#8a8a9a",
                    marginTop: 6,
                    lineHeight: 1.4,
                  }}
                >
                  {s.sub}
                </div>
              </div>

              {/* Feed pills below box */}
              {s.feeds.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    marginTop: 8,
                    width: "100%",
                  }}
                >
                  {s.feeds.map((f) => (
                    <div
                      key={f}
                      style={{
                        background: FEED_COLORS[f] ?? "#2e2e36",
                        border: "1px solid #3e3e46",
                        padding: "3px 6px",
                        textAlign: "center",
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 9,
                        color: "#8a8a9a",
                        letterSpacing: "0.05em",
                      }}
                    >
                      {f}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {i < STAGES.length - 1 && <Arrow />}
          </div>
        ))}
      </div>
    </div>
  );
}
