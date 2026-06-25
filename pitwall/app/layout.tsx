import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PIT WALL — F1 Race Prediction & RAG",
  description: "XGBoost race prediction + Qdrant RAG chatbot over F1 telemetry data",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full">{children}</body>
    </html>
  );
}
