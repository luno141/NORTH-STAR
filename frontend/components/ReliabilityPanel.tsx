"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { updateSourceReliability } from "@/lib/api";
import { SourceReliabilityRow } from "@/lib/types";

type Props = {
  rows: SourceReliabilityRow[];
};

export function ReliabilityPanel({ rows }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [drafts, setDrafts] = useState<Record<number, SourceReliabilityRow>>(
    () => Object.fromEntries(rows.map((row) => [row.id, row]))
  );

  async function save(id: number) {
    try {
      setStatus("Saving source trust settings...");
      const row = drafts[id];
      await updateSourceReliability(id, {
        reliability: row.reliability,
        weight: row.weight,
        enabled: row.enabled,
        notes: row.notes
      });
      setStatus("Source trust updated.");
      router.refresh();
    } catch (error) {
      setStatus(`Update failed: ${String(error)}`);
    }
  }

  return (
    <section className="hud-panel p-5">
      <div className="mb-4">
        <p className="hud-panel-title">Source Trust</p>
        <p className="mt-1 text-sm text-slate-300/72">
          Curate baseline trust and weighting for feed families before model scoring is applied.
        </p>
      </div>
      {status ? <p className="status-note mb-4">{status}</p> : null}
      <div className="space-y-4">
        {rows.map((row) => {
          const draft = drafts[row.id];
          return (
            <div key={row.id} className="subpanel-grid">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-white">{row.pattern}</h3>
                  <span className="session-pill">{draft.enabled ? "active" : "disabled"}</span>
                </div>
                <p className="mt-2 text-sm text-slate-300/72">{draft.notes || "No operator note."}</p>
              </div>
              <div className="admin-inline-form">
                <label>
                  <span>Reliability</span>
                  <input
                    className="hud-input"
                    type="number"
                    step="0.1"
                    value={draft.reliability}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [row.id]: { ...current[row.id], reliability: Number(e.target.value) || 0 }
                      }))
                    }
                  />
                </label>
                <label>
                  <span>Weight</span>
                  <input
                    className="hud-input"
                    type="number"
                    step="0.01"
                    value={draft.weight}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [row.id]: { ...current[row.id], weight: Number(e.target.value) || 0 }
                      }))
                    }
                  />
                </label>
                <label className="toggle-wrap">
                  <span>Enabled</span>
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [row.id]: { ...current[row.id], enabled: e.target.checked }
                      }))
                    }
                  />
                </label>
                <button onClick={() => save(row.id)} className="btn-muted">
                  Save trust
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
