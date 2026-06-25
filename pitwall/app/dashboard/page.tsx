"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CircuitBackground from "@/components/CircuitBackground";
import CustomCursor from "@/components/CustomCursor";
import LiveBadge from "@/components/LiveBadge";
import Ticker from "@/components/Ticker";
import StatCards from "@/components/StatCards";
import TireStrategy from "@/components/TireStrategy";
import CircuitContext from "@/components/CircuitContext";
import DriverTable from "@/components/DriverTable";
import Chat from "@/components/Chat";
import { RaceProvider } from "@/components/RaceContext";

export default function DashboardPage() {
  const router = useRouter();
  const [lap, setLap] = useState(1);

  useEffect(() => {
    const t = setInterval(() => setLap((l) => (l >= 44 ? 1 : l + 1)), 1800);
    return () => clearInterval(t);
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <CircuitBackground />
      <CustomCursor />

      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 28px",
          borderBottom: "1px solid #2e2e36",
          flexShrink: 0,
          zIndex: 5,
          background: "#1a1a1f",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <button
            data-interactive
            onClick={() => router.push("/")}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              fontWeight: 600,
              color: "#8a8a9a",
              background: "none",
              border: "none",
              letterSpacing: "0.1em",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14">
              <polyline points="9,2 4,7 9,12" stroke="#8a8a9a" strokeWidth="1.5" fill="none" />
            </svg>
            OVERVIEW
          </button>
          <div style={{ width: 1, height: 20, background: "#2e2e36" }} />
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 14,
              fontWeight: 700,
              color: "#f0f0f0",
              letterSpacing: "0.15em",
            }}
          >
            PIT WALL
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: 10,
                color: "#8a8a9a",
                letterSpacing: "0.15em",
              }}
            >
              LAP
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 22,
                fontWeight: 700,
                color: "#f0f0f0",
                minWidth: 48,
              }}
            >
              {String(lap).padStart(2, "0")}
            </span>
            <span
              style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: 10,
                color: "#8a8a9a",
              }}
            >
              / 44
            </span>
          </div>
          <div style={{ width: 1, height: 20, background: "#2e2e36" }} />
          <LiveBadge />
        </div>
      </div>

      {/* Main content split */}
      <RaceProvider>
      <Ticker />
      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative", zIndex: 1 }}>

        {/* LEFT — Race Analysis (55%) */}
        <div
          style={{
            width: "55%",
            borderRight: "1px solid #2e2e36",
            overflowY: "auto",
            padding: "24px 28px",
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 12,
              fontWeight: 700,
              color: "#f0f0f0",
              letterSpacing: "0.2em",
            }}
          >
            RACE ANALYSIS
          </div>
          <StatCards />
          <CircuitContext />
          <TireStrategy />
          <DriverTable />
        </div>

        {/* RIGHT — Chat (45%) */}
        <Chat />
      </div>
      </RaceProvider>
    </div>
  );
}
