import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// CI-Schrift aus brands/ai-pioneers.tex: Inter (Fallback Helvetica Neue).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "QVC Discovery · AI Pioneers",
  description:
    "Debug surface für qvc_discovery.py · Google Verifiable Quantum Circuit Compilation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className={inter.variable}>{children}</body>
    </html>
  );
}
