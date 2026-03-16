"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent } from "react";

export function FilterBar() {
  const params = useSearchParams();
  const router = useRouter();

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const q = new URLSearchParams();

    ["org_id", "indicator_type", "min_severity", "min_credibility", "hours"].forEach((k) => {
      const v = String(formData.get(k) || "").trim();
      if (v) q.set(k, v);
    });

    router.push(`/feed?${q.toString()}`);
  };

  return (
    <form onSubmit={onSubmit} className="hud-panel p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="hud-panel-title">Feed Filters</p>
          <p className="text-sm text-slate-300/72">Tighten the feed by org, type, severity, trust, and recency.</p>
        </div>
        <button className="btn-primary">Refine Feed</button>
      </div>

      <div className="filter-grid">
        <input
          name="org_id"
          defaultValue={params.get("org_id") || ""}
          placeholder="Org ID"
          className="hud-input"
        />
        <input
          name="indicator_type"
          defaultValue={params.get("indicator_type") || ""}
          placeholder="Type"
          className="hud-input"
        />
        <input
          name="min_severity"
          defaultValue={params.get("min_severity") || ""}
          placeholder="Min severity"
          className="hud-input"
        />
        <input
          name="min_credibility"
          defaultValue={params.get("min_credibility") || ""}
          placeholder="Min credibility"
          className="hud-input"
        />
        <input
          name="hours"
          defaultValue={params.get("hours") || ""}
          placeholder="Hours window"
          className="hud-input"
        />
      </div>
    </form>
  );
}
