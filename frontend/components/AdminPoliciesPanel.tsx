"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { updateAdminPolicy } from "@/lib/api";
import { FederationPolicy } from "@/lib/types";

type Props = {
  policies: FederationPolicy[];
};

export function AdminPoliciesPanel({ policies }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [drafts, setDrafts] = useState<Record<number, FederationPolicy>>(
    () => Object.fromEntries(policies.map((policy) => [policy.id, policy]))
  );

  async function save(policyId: number) {
    try {
      setStatus("Saving federation policy...");
      const policy = drafts[policyId];
      await updateAdminPolicy(policyId, {
        enabled: policy.enabled,
        min_credibility: policy.min_credibility,
        min_reputation: policy.min_reputation
      });
      setStatus("Federation policy updated.");
      router.refresh();
    } catch (error) {
      setStatus(`Policy update failed: ${String(error)}`);
    }
  }

  return (
    <section className="hud-panel p-5">
      <div className="mb-4">
        <p className="hud-panel-title">Federation Policies</p>
        <p className="mt-1 text-sm text-slate-300/72">
          Control what your organization is willing to share and the minimum trust required.
        </p>
      </div>
      {status ? <p className="status-note mb-4">{status}</p> : null}
      <div className="space-y-4">
        {policies.map((policy) => {
          const draft = drafts[policy.id];
          return (
            <div key={policy.id} className="subpanel-grid">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-white">Org {policy.from_org_id} → Org {policy.to_org_id}</h3>
                  <span className="session-pill">{draft.enabled ? "enabled" : "paused"}</span>
                </div>
                <p className="mt-2 text-sm text-slate-300/72">
                  Sharing occurs only when contributor reputation and credibility clear the thresholds below.
                </p>
              </div>
              <div className="admin-inline-form">
                <label>
                  <span>Min credibility</span>
                  <input
                    className="hud-input"
                    type="number"
                    step="0.1"
                    value={draft.min_credibility}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [policy.id]: { ...current[policy.id], min_credibility: Number(e.target.value) || 0 }
                      }))
                    }
                  />
                </label>
                <label>
                  <span>Min reputation</span>
                  <input
                    className="hud-input"
                    type="number"
                    step="0.1"
                    value={draft.min_reputation}
                    onChange={(e) =>
                      setDrafts((current) => ({
                        ...current,
                        [policy.id]: { ...current[policy.id], min_reputation: Number(e.target.value) || 0 }
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
                        [policy.id]: { ...current[policy.id], enabled: e.target.checked }
                      }))
                    }
                  />
                </label>
                <button onClick={() => save(policy.id)} className="btn-muted">
                  Save policy
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
