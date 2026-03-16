"use client";

import { useState } from "react";

import { runFederation } from "@/lib/api";

export function FederationButton() {
  const [status, setStatus] = useState<string>("");

  const onClick = async () => {
    setStatus("Running federation workflow...");
    try {
      const res = await runFederation();
      setStatus(`Shared ${res.shared_count} eligible intel records.`);
    } catch (e) {
      setStatus(`Failed: ${String(e)}`);
    }
  };

  return (
    <div className="hud-panel p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <p className="hud-panel-title">Federation Relay</p>
          <p className="text-sm text-slate-300/74">
            Share trusted intel across organizations using policy, contributor reputation, and credibility thresholds.
          </p>
          {status ? <p className="status-note">{status}</p> : null}
        </div>
        <button onClick={onClick} className="btn-primary min-w-36">
          Run Federation
        </button>
      </div>
    </div>
  );
}
