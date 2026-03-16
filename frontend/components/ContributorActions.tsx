"use client";

import { useState } from "react";

import { contributorAction } from "@/lib/api";

export function ContributorActions({ contributorId }: { contributorId: number }) {
  const [intelId, setIntelId] = useState<string>("");
  const [result, setResult] = useState<string>("");

  async function send(action: "approve" | "upvote" | "flag") {
    if (!intelId) {
      setResult("Provide an intel ID first.");
      return;
    }
    try {
      const res = await contributorAction({
        contributor_id: contributorId,
        intel_id: Number(intelId),
        action
      });
      setResult(`Reputation ${res.new_reputation} / delta ${res.delta}`);
    } catch (e) {
      setResult(`Failed: ${String(e)}`);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={intelId}
          onChange={(e) => setIntelId(e.target.value)}
          placeholder="Intel ID"
          className="hud-input w-28 px-3 py-2 text-xs"
        />
        <button onClick={() => send("approve")} className="btn-success">
          Approve
        </button>
        <button onClick={() => send("upvote")} className="btn-info">
          Upvote
        </button>
        <button onClick={() => send("flag")} className="btn-danger">
          Flag FP
        </button>
      </div>
      {result ? <p className="text-xs text-slate-300/72">{result}</p> : null}
    </div>
  );
}
