"use client";

import { useState } from "react";

import { runIntegrityAnchor, runIntegrityVerify } from "@/lib/api";

export function IntegrityCheck() {
  const [result, setResult] = useState<null | {
    status: string;
    first_broken_index: number | null;
    checked_entries: number;
  }>(null);
  const [loading, setLoading] = useState(false);
  const [anchorStatus, setAnchorStatus] = useState<string>("");

  const onVerify = async () => {
    setLoading(true);
    try {
      const res = await runIntegrityVerify();
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const onAnchor = async () => {
    setAnchorStatus("Anchoring ledger head...");
    try {
      const res = await runIntegrityAnchor();
      if (res.created) {
        setAnchorStatus(`Anchor #${res.anchor_id} created at ledger ${res.up_to_ledger_id}.`);
      } else {
        setAnchorStatus("No new entries required anchoring.");
      }
    } catch (e) {
      setAnchorStatus(`Anchor failed: ${String(e)}`);
    }
  };

  return (
    <div className="hud-panel p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="hud-panel-title">Integrity Verification</p>
          <p className="mt-1 text-sm text-slate-300/72">
            Verify the append-only chain and create fresh anchors against the current ledger head.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={onVerify} className="btn-primary" disabled={loading}>
            {loading ? "Checking..." : "Run Verify"}
          </button>
          <button onClick={onAnchor} className="btn-muted">
            Create Anchor
          </button>
        </div>
      </div>

      {anchorStatus ? <p className="status-note mt-4">{anchorStatus}</p> : null}

      {result ? (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="hud-data-box">
            <span>Status</span>
            <strong>{result.status}</strong>
          </div>
          <div className="hud-data-box">
            <span>Checked Entries</span>
            <strong>{result.checked_entries}</strong>
          </div>
          <div className="hud-data-box">
            <span>First Broken Index</span>
            <strong>{result.first_broken_index ?? "none"}</strong>
          </div>
        </div>
      ) : null}
    </div>
  );
}
