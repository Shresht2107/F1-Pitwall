"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { useRace } from "@/components/RaceContext";

type Role = "user" | "assistant" | "thinking";

interface Message {
  id: string;
  role: Role;
  text: string;
}

function UserBubble({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", animation: "fadeIn 0.3s ease" }}>
      <div
        style={{
          background: "#2a2a35",
          padding: "12px 16px",
          maxWidth: "80%",
          fontFamily: "'Inter', sans-serif",
          fontSize: 13,
          color: "#f0f0f0",
          lineHeight: 1.5,
        }}
      >
        {text}
      </div>
    </div>
  );
}

function ThinkingBubble() {
  const [dots, setDots] = useState(1);
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d % 3) + 1), 400);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ display: "flex", justifyContent: "flex-start", animation: "fadeIn 0.3s ease" }}>
      <div style={{ borderLeft: "2px solid #e8002d", padding: "12px 16px" }}>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: "#e8002d",
            fontWeight: 700,
            letterSpacing: "0.1em",
            marginBottom: 6,
          }}
        >
          PIT WALL AI · RETRIEVING...
        </div>
        <div
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: 13,
            color: "#8a8a9a",
          }}
        >
          Querying Qdrant vector store{".".repeat(dots)}
        </div>
      </div>
    </div>
  );
}

function AssistantBubble({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start", animation: "fadeIn 0.3s ease" }}>
      <div
        style={{
          borderLeft: "2px solid #e8002d",
          padding: "12px 16px",
          maxWidth: "88%",
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: "#e8002d",
            fontWeight: 700,
            letterSpacing: "0.1em",
            marginBottom: 8,
          }}
        >
          PIT WALL AI · RAG RESPONSE
        </div>
        <div
          style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: 13,
            color: "#f0f0f0",
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
}

const INITIAL: Message[] = [
  { id: "0", role: "user",      text: "What strategy did Verstappen run at the 2023 Belgian GP?" },
  { id: "1", role: "assistant", text: `At the 2023 Belgian GP (Spa-Francorchamps), Verstappen ran a two-stop strategy:\n\nSTINT 1 ── MEDIUM · Laps 1–13\nSTINT 2 ── HARD · Laps 14–32\nSTINT 3 ── MEDIUM · Laps 33–44\n\nFastest lap: 1:46.771 (Lap 34). Won by +22.3s ahead of Pérez. Retrieved from 3 source chunks (similarity ≥ 0.89).` },
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>(INITIAL);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const { setRace, setLoading: setRaceLoading } = useRace();

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/health`).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg: Message = { id: Date.now().toString(), role: "user", text };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: data.answer ?? "No response received.",
      };
      setMessages((m) => [...m, aiMsg]);

      // If the response is anchored to a specific race, update the Race Analysis panel
      const src = data.sources?.[0];
      if (src?.year && src?.round) {
        setRaceLoading(true);
        try {
          const raceRes = await fetch(`/api/race?year=${src.year}&round=${src.round}`);
          if (raceRes.ok) {
            const raceData = await raceRes.json();
            setRace(raceData);
          }
        } finally {
          setRaceLoading(false);
        }
      }
    } catch (err) {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: `Error reaching PIT WALL backend. Make sure Ollama and Qdrant are running locally.\n\n${err}`,
      };
      setMessages((m) => [...m, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div
      style={{
        width: "45%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: "1px solid #2e2e36",
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexShrink: 0,
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
          PIT WALL CHAT
        </div>
        <div
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: "#22c55e",
            animation: "pulseGreen 2s ease-in-out infinite",
          }}
        />
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px 24px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {messages.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} text={m.text} />
          ) : (
            <AssistantBubble key={m.id} text={m.text} />
          )
        )}
        {loading && <ThinkingBubble />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          borderTop: "1px solid #2e2e36",
          padding: "16px 24px",
          flexShrink: 0,
          background: "#1a1a1f",
        }}
      >
        <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about any race, driver, strategy, or result..."
            style={{
              flex: 1,
              background: "#222228",
              border: "1px solid #2e2e36",
              color: "#f0f0f0",
              fontFamily: "'Inter', sans-serif",
              fontSize: 13,
              padding: "12px 14px",
              resize: "none",
              outline: "none",
              lineHeight: 1.5,
            }}
          />
          <button
            data-interactive
            onClick={send}
            disabled={loading}
            style={{
              background: loading ? "#6b0014" : "#e8002d",
              border: "none",
              color: "#fff",
              padding: "0 18px",
              fontFamily: "'Inter', sans-serif",
              fontSize: 18,
              borderRadius: 0,
              flexShrink: 0,
              transition: "background 0.2s",
            }}
          >
            →
          </button>
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: "#8a8a9a",
            letterSpacing: "0.08em",
          }}
        >
          Powered by Qwen3-32b · nomic-embed-text-v1.5 · Qdrant Cloud
        </div>
      </div>
    </div>
  );
}
