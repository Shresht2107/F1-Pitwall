export default function LiveBadge() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        border: "1px solid #2e2e36",
        padding: "5px 12px",
      }}
    >
      <div
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: "#e8002d",
          animation: "pulseLive 1.2s ease-in-out infinite",
        }}
      />
      <span
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          fontWeight: 700,
          color: "#e8002d",
          letterSpacing: "0.15em",
        }}
      >
        LIVE
      </span>
    </div>
  );
}
