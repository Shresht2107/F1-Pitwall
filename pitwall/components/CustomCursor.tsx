"use client";

import { useEffect, useRef } from "react";

export default function CustomCursor() {
  const hRef = useRef<HTMLDivElement>(null);
  const vRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cx = window.innerWidth / 2;
    let cy = window.innerHeight / 2;
    let tx = cx;
    let ty = cy;
    let rafId: number;

    const lerp = (a: number, b: number, f: number) => a + (b - a) * f;

    const tick = () => {
      cx = lerp(cx, tx, 0.12);
      cy = lerp(cy, ty, 0.12);
      if (hRef.current) { hRef.current.style.left = cx + "px"; hRef.current.style.top = cy + "px"; }
      if (vRef.current) { vRef.current.style.left = cx + "px"; vRef.current.style.top = cy + "px"; }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);

    const onMove = (e: MouseEvent) => { tx = e.clientX; ty = e.clientY; };
    document.addEventListener("mousemove", onMove);

    const onOver = (e: MouseEvent) => {
      const target = e.target as Element;
      const interactive = target.closest("button, a, input, textarea, [data-interactive]");
      const size = interactive ? "22px" : "16px";
      const op = interactive ? "1" : "0.6";
      if (hRef.current) { hRef.current.style.width = size; hRef.current.style.opacity = op; }
      if (vRef.current) { vRef.current.style.height = size; vRef.current.style.opacity = op; }
    };
    document.addEventListener("mouseover", onOver);

    const onClick = (e: MouseEvent) => {
      const r = document.createElement("div");
      r.style.cssText = `position:fixed;left:${e.clientX}px;top:${e.clientY}px;width:40px;height:40px;border-radius:50%;border:1.5px solid #e8002d;pointer-events:none;z-index:9998;animation:rippleOut 0.4s ease-out forwards;`;
      document.body.appendChild(r);
      setTimeout(() => r.remove(), 420);
    };
    document.addEventListener("click", onClick);

    return () => {
      cancelAnimationFrame(rafId);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseover", onOver);
      document.removeEventListener("click", onClick);
    };
  }, []);

  return (
    <>
      <div
        ref={hRef}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: 16,
          height: 2,
          background: "#e8002d",
          opacity: 0.6,
          pointerEvents: "none",
          zIndex: 9999,
          transform: "translate(-50%, -50%)",
          transition: "opacity 0.1s, width 0.15s, height 0.15s",
        }}
      />
      <div
        ref={vRef}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: 2,
          height: 16,
          background: "#e8002d",
          opacity: 0.6,
          pointerEvents: "none",
          zIndex: 9999,
          transform: "translate(-50%, -50%)",
          transition: "opacity 0.1s, width 0.15s, height 0.15s",
        }}
      />
    </>
  );
}
