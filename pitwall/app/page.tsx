"use client";

import { useRouter } from "next/navigation";
import CircuitBackground from "@/components/CircuitBackground";
import CustomCursor from "@/components/CustomCursor";
import LiveBadge from "@/components/LiveBadge";
import TechStack from "@/components/TechStack";
import PipelineArch from "@/components/PipelineArch";

export default function LandingPage() {
  const router = useRouter();

  return (
    <div style={{ position: "fixed", inset: 0, overflow: "hidden" }}>
      <CircuitBackground />
      <CustomCursor />

      {/* Speed stripe */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100%",
          height: 3,
          background: "#e8002d",
          zIndex: 1000,
        }}
      />

      {/* Scrollable landing content */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          overflowY: "auto",
          overflowX: "hidden",
          zIndex: 1,
          paddingBottom: 60,
        }}
      >
        {/* Top nav */}
        <div
          style={{
            position: "sticky",
            top: 0,
            left: 0,
            width: "100%",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "20px 48px",
            zIndex: 10,
            background: "linear-gradient(to bottom, #1a1a1f 80%, transparent)",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 16,
                fontWeight: 700,
                color: "#f0f0f0",
                letterSpacing: "0.2em",
              }}
            >
              PIT WALL
            </span>
            <div style={{ width: "100%", height: 2, background: "#e8002d" }} />
          </div>
          <LiveBadge />
        </div>

        {/* Hero */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            padding: "48px 48px 40px",
            animation: "fadeIn 0.8s ease both",
          }}
        >
          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 11,
              fontWeight: 600,
              color: "#8a8a9a",
              letterSpacing: "0.2em",
              marginBottom: 20,
            }}
          >
            F1 MACHINE LEARNING + RAG SYSTEM
          </div>

          <h1
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: "clamp(48px, 7vw, 88px)",
              fontWeight: 900,
              lineHeight: 0.95,
              color: "#f0f0f0",
              letterSpacing: "-0.02em",
              marginBottom: 24,
            }}
          >
            RACE PREDICTION
            <br />
            <span style={{ color: "#f0f0f0" }}>&amp; PIT WALL CHAT</span>
          </h1>

          <p
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 14,
              fontWeight: 400,
              color: "#8a8a9a",
              maxWidth: 640,
              lineHeight: 1.7,
              marginBottom: 48,
            }}
          >
            A two-stage ML pipeline combining tire-degradation regression and
            race-outcome classification, augmented with a retrieval-based natural
            language interface over historical F1 race data.
          </p>

          <TechStack />
          <PipelineArch />

          <button
            data-interactive
            onClick={() => router.push("/dashboard")}
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.2em",
              color: "#fff",
              background: "#e8002d",
              border: "none",
              padding: "18px 48px",
              borderRadius: 0,
              marginBottom: 20,
            }}
          >
            ENTER DASHBOARD →
          </button>

          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 11,
              color: "#8a8a9a",
              letterSpacing: "0.05em",
            }}
          >
            Trained on 2022–2024 seasons · 69 race rounds · XGBoost + Monte Carlo simulation
          </div>
        </div>
      </div>
    </div>
  );
}
