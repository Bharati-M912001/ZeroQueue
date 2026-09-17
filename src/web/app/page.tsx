"use client";

import { useEffect, useState } from "react";
import ChatPanel from "../components/ChatPanel";
import IntercomBoot from "../components/IntercomBoot";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function Home() {
  const [health, setHealth] = useState<"ok" | "bad" | "...">("...");
  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => setHealth(r.ok ? "ok" : "bad"))
      .catch(() => setHealth("bad"));
  }, []);

  return (
    <main className="page">
      <div className="header">
        <div>
          <div className="brand">Zero<span>Queue</span></div>
          <div className="tagline">Zero wait. Grounded answers, with receipts.</div>
        </div>
        <div className={`pill ${health === "ok" ? "ok" : health === "bad" ? "bad" : ""}`}>
          {health === "ok" ? "online" : health === "bad" ? "backend offline" : "checking..."}
        </div>
      </div>
      <ChatPanel />
      <IntercomBoot />
    </main>
  );
}
