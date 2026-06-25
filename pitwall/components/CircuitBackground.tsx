"use client";

export default function CircuitBackground() {
  return (
    <>
      <svg
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: 0,
        }}
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
      >
        <path
          d="M200,700 L200,600 Q200,560 240,540 L320,500 Q380,470 400,420 L410,340 Q415,280 460,250 L560,200 Q620,175 680,180 L800,190 Q880,195 940,230 L1020,280 Q1080,320 1100,390 L1110,460 Q1115,520 1080,560 L1020,600 Q960,640 900,650 L780,660 Q700,665 660,700 L640,740 Q620,780 580,790 L460,800 Q380,805 340,780 L280,750 Q240,730 200,700 Z"
          fill="none"
          stroke="#2a2a35"
          strokeWidth="1.5"
          strokeDasharray="2400"
          style={{ animation: "drawCircuit 8s linear infinite" }}
        />
        <path
          d="M460,480 L500,440 Q530,410 570,400 L650,390 Q710,385 750,420 L790,460 Q820,490 810,530 L790,570 Q770,600 730,610 L650,615 Q590,615 550,585 L510,555 Q478,530 460,505 L460,480 Z"
          fill="none"
          stroke="#2a2a35"
          strokeWidth="1"
          strokeDasharray="1800"
          style={{ animation: "drawCircuit2 12s linear infinite reverse" }}
        />
        <line x1="700" y1="180" x2="700" y2="80" stroke="#2a2a35" strokeWidth="1" strokeDasharray="6,6" />
        <line x1="1100" y1="390" x2="1260" y2="390" stroke="#2a2a35" strokeWidth="1" strokeDasharray="6,6" />
        <line x1="200" y1="700" x2="80" y2="700" stroke="#2a2a35" strokeWidth="1" strokeDasharray="6,6" />
      </svg>

      {/* Drifting blobs */}
      <div
        style={{
          position: "fixed",
          top: "10%",
          left: "15%",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: "radial-gradient(circle, #3a0810 0%, transparent 70%)",
          opacity: 0.08,
          pointerEvents: "none",
          zIndex: 0,
          animation: "blobDrift1 20s ease-in-out infinite",
        }}
      />
      <div
        style={{
          position: "fixed",
          bottom: "5%",
          right: "10%",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, #080f2e 0%, transparent 70%)",
          opacity: 0.08,
          pointerEvents: "none",
          zIndex: 0,
          animation: "blobDrift2 20s ease-in-out infinite",
        }}
      />
    </>
  );
}
