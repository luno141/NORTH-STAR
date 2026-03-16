"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { runAdminSource, runDueAdminSources, updateAdminIngestionSource } from "@/lib/api";
import { IngestionRun, IngestionSource } from "@/lib/types";

type Props = {
  sources: IngestionSource[];
  runs: IngestionRun[];
};

export function AdminSourcesPanel({ sources, runs }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState<string>("");
  const [drafts, setDrafts] = useState<Record<number, { interval_minutes: number; max_rows: number; enabled: boolean }>>(
    () =>
      Object.fromEntries(
        sources.map((source) => [
          source.id,
          {
            interval_minutes: source.interval_minutes,
            max_rows: source.max_rows,
            enabled: source.enabled
          }
        ])
      )
  );

  const runMap = useMemo(() => {
    const map = new Map<number, IngestionRun[]>();
    runs.forEach((run) => {
      const next = map.get(run.source_id) || [];
      next.push(run);
      map.set(run.source_id, next);
    });
    return map;
  }, [runs]);

  async function save(id: number) {
    try {
      setStatus("Saving source configuration...");
      await updateAdminIngestionSource(id, drafts[id]);
      setStatus("Source configuration updated.");
      router.refresh();
    } catch (error) {
      setStatus(`Save failed: ${String(error)}`);
    }
  }

  async function runSource(id: number) {
    try {
      setStatus("Queueing source run...");
      await runAdminSource(id);
      setStatus("Source run queued.");
      router.refresh();
    } catch (error) {
      setStatus(`Run failed: ${String(error)}`);
    }
  }

  async function runDue() {
    try {
      setStatus("Queueing due sources...");
      const res = await runDueAdminSources();
      setStatus(`Queued ${res.due_count} due source(s).`);
      router.refresh();
    } catch (error) {
      setStatus(`Queue failed: ${String(error)}`);
    }
  }

  return (
    <section className="hud-panel p-5">
      <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="hud-panel-title">Live Sources</p>
          <p className="mt-1 text-sm text-slate-300/72">
            Control scheduler cadence, per-source volume, and real-time source execution.
          </p>
        </div>
        <button onClick={runDue} className="btn-primary">
          Run Due Sources
        </button>
      </div>

      {status ? <p className="status-note mb-4">{status}</p> : null}

      <div className="space-y-4">
        {sources.map((source) => {
          const recentRuns = (runMap.get(source.id) || []).slice(0, 3);
          const draft = drafts[source.id];
          return (
            <div key={source.id} className="subpanel-grid">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-white">{source.name}</h3>
                  <span className="session-pill">{source.source_kind}</span>
                  <span className="session-pill">{source.last_status}</span>
                </div>
                <p className="text-sm text-slate-300/72">
                  Last created: {source.last_created_count} / Last success: {source.last_success_at || "never"}
                </p>
                {source.last_error ? <p className="text-sm text-rose-200/80">{source.last_error}</p> : null}
              </div>

              <div className="admin-inline-form">
                <label>
                  <span>Interval min</span>
                  <input
                    className="hud-input"
                    type="number"
                    value={draft.interval_minutes}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [source.id]: { ...current[source.id], interval_minutes: Number(e.target.value) || 1 }
                      }))
                    }
                  />
                </label>
                <label>
                  <span>Max rows</span>
                  <input
                    className="hud-input"
                    type="number"
                    value={draft.max_rows}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [source.id]: { ...current[source.id], max_rows: Number(e.target.value) || 1 }
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
                        [source.id]: { ...current[source.id], enabled: e.target.checked }
                      }))
                    }
                  />
                </label>
                <button onClick={() => save(source.id)} className="btn-muted">
                  Save
                </button>
                <button onClick={() => runSource(source.id)} className="btn-info">
                  Run now
                </button>
              </div>

              <div className="admin-mini-table">
                <p className="hud-panel-title">Recent Runs</p>
                {recentRuns.length ? (
                  <div className="space-y-2">
                    {recentRuns.map((run) => (
                      <div key={run.id} className="rounded-[20px] border border-white/8 bg-white/[0.035] px-4 py-3 text-sm text-slate-300/82">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="session-pill">{run.status}</span>
                          <span className="text-xs text-slate-400">{run.trigger}</span>
                        </div>
                        <p className="mt-2">Created: {run.created_count}</p>
                        <p className="text-xs text-slate-400">Started: {run.started_at}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">No runs recorded yet.</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
