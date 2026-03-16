import Link from "next/link";

import { FederationButton } from "@/components/FederationButton";
import { FilterBar } from "@/components/FilterBar";
import { HudRadar } from "@/components/HudRadar";
import { LocalTime } from "@/components/LocalTime";
import { ThreatGlobe } from "@/components/ThreatGlobe";
import { ApiFetchError, getFeed } from "@/lib/api";
import { FeedResponse } from "@/lib/types";

type ClassRow = {
  name: string;
  count: number;
};

export default async function FeedPage({
  searchParams
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const query = new URLSearchParams();
  Object.entries(searchParams).forEach(([k, v]) => {
    if (typeof v === "string" && v) query.set(k, v);
  });

  let data: FeedResponse = { items: [], total: 0 };
  let fetchError = "";
  try {
    data = await getFeed(query.toString());
  } catch (error) {
    if (error instanceof ApiFetchError && (error.status === 401 || error.status === 403)) {
      fetchError = "Feed is locked. Start a valid session in the header to load intel.";
    } else {
      fetchError = "Feed request failed. Check backend status, then refresh.";
    }
  }

  const visibleItems = data.items.length;
  const criticalItems = data.items.filter((item) => item.severity >= 80).length;
  const federatedItems = data.items.filter((item) => item.shared_from_org_id).length;
  const avgCredibility = visibleItems
    ? (data.items.reduce((sum, item) => sum + item.credibility, 0) / visibleItems).toFixed(1)
    : "0";
  const avgSeverity = visibleItems
    ? (data.items.reduce((sum, item) => sum + item.severity, 0) / visibleItems).toFixed(1)
    : "0";
  const avgModelConfidence = visibleItems
    ? (data.items.reduce((sum, item) => sum + item.model_confidence, 0) / visibleItems).toFixed(1)
    : "0";

  const classMap = data.items.reduce<Record<string, number>>((acc, item) => {
    acc[item.classification] = (acc[item.classification] || 0) + 1;
    return acc;
  }, {});
  const topClasses: ClassRow[] = Object.entries(classMap)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  const maxClassCount = topClasses.length ? topClasses[0].count : 1;
  const latest = data.items[0];

  return (
    <div className="space-y-6">
      <section className="mission-hero hud-panel">
        <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-center">
          <div className="mission-hero__copy">
            <p className="hud-kicker">Apple-grade clarity / orbital operations language</p>
            <h2 className="text-4xl font-semibold leading-[0.95] text-white sm:text-5xl lg:text-6xl">
              Threat intelligence,
              <br />
              rendered as mission control.
            </h2>
            <p className="max-w-2xl text-base leading-7 text-slate-300/76 sm:text-lg">
              N★RTH STAR ingests live threat feeds, scores credibility and severity, preserves tamper evidence, and
              shares trusted intel across organizations without turning your operators into spreadsheet clerks.
            </p>

            <div className="mission-hero__chips">
              <span className="session-pill">Integrity chain live</span>
              <span className="session-pill">Federation ready</span>
              <span className="session-pill">Vector search active</span>
            </div>

            <div className="mission-stat-row">
              <div className="mission-stat">
                <span>Visible feed</span>
                <strong>{visibleItems}</strong>
              </div>
              <div className="mission-stat">
                <span>Critical queue</span>
                <strong>{criticalItems}</strong>
              </div>
              <div className="mission-stat">
                <span>Federated relays</span>
                <strong>{federatedItems}</strong>
              </div>
              <div className="mission-stat">
                <span>Mean credibility</span>
                <strong>{avgCredibility}</strong>
              </div>
            </div>
          </div>

          <div className="mission-hero__visual">
            <ThreatGlobe />
            <div className="hero-sidecar">
              <div className="hero-sidecar__panel">
                <span>Severity mean</span>
                <strong>{avgSeverity}</strong>
              </div>
              <div className="hero-sidecar__panel">
                <span>Model certainty</span>
                <strong>{avgModelConfidence}</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="hud-metric-strip">
        <div className="hud-metric">
          <p>System State</p>
          <strong>Nominal</strong>
        </div>
        <div className="hud-metric">
          <p>Pipeline</p>
          <strong>{data.total}</strong>
        </div>
        <div className="hud-metric">
          <p>Critical</p>
          <strong>{criticalItems}</strong>
        </div>
        <div className="hud-metric">
          <p>Credibility</p>
          <strong>{avgCredibility}</strong>
        </div>
        <div className="hud-metric">
          <p>Federated</p>
          <strong>{federatedItems}</strong>
        </div>
      </section>

      <section className="hud-grid-layout">
        <div className="hud-panel p-5">
          <p className="hud-panel-title">Orbital Sweep</p>
          <div className="mt-4">
            <HudRadar />
          </div>
        </div>

        <div className="hud-panel p-5">
          <p className="hud-panel-title">Classification Mix</p>
          <div className="mt-4 space-y-3">
            {topClasses.map((row) => (
              <div key={row.name}>
                <div className="mb-1 flex items-center justify-between text-xs uppercase tracking-[0.22em] text-slate-300/70">
                  <span>{row.name}</span>
                  <span>{row.count}</span>
                </div>
                <div className="hud-bar-track">
                  <div className="hud-bar-fill" style={{ width: `${(row.count / maxClassCount) * 100}%` }} />
                </div>
              </div>
            ))}
            {!topClasses.length ? <p className="text-sm text-slate-300/60">No classified records are loaded yet.</p> : null}
          </div>
        </div>

        <div className="hud-panel p-5">
          <p className="hud-panel-title">Latest Intel</p>
          {latest ? (
            <div className="mt-4 space-y-3 text-sm text-slate-200/84">
              <div className="hud-data-box">
                <span>Record ID</span>
                <strong>{latest.id}</strong>
              </div>
              <div className="hud-data-box">
                <span>Class</span>
                <strong>{latest.classification}</strong>
              </div>
              <div className="hud-data-box">
                <span>Observed</span>
                <strong>
                  <LocalTime value={latest.timestamp} />
                </strong>
              </div>
              <div className="rounded-[24px] border border-white/8 bg-white/[0.04] px-4 py-3 text-sm text-slate-300/84">
                <p className="mb-1 text-[11px] uppercase tracking-[0.24em] text-slate-400/80">Indicator</p>
                <p className="truncate" title={latest.value}>
                  {latest.value}
                </p>
              </div>
              <Link href={`/intel/${latest.id}`} className="btn-muted inline-flex w-fit items-center justify-center px-4 py-2 text-xs">
                Open detail view
              </Link>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-300/60">No events loaded.</p>
          )}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <FederationButton />
        <FilterBar />
      </div>

      {fetchError ? <div className="hud-error">{fetchError}</div> : null}

      <section className="hud-panel overflow-hidden p-0">
        <div className="hud-table-head">
          <div>
            <p className="hud-panel-title">Threat Feed</p>
            <p className="mt-1 text-sm text-slate-300/66">Multi-tenant intel with credibility, severity, and timestamped evidence.</p>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-400/80">{data.total} records</p>
        </div>
        <table className="hud-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Org</th>
              <th>Type</th>
              <th>Value</th>
              <th>Class</th>
              <th>Model</th>
              <th>Severity</th>
              <th>Credibility</th>
              <th>Observed</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link href={`/intel/${item.id}`} className="underline decoration-slate-400/50 underline-offset-4 hover:decoration-white">
                    {item.id}
                  </Link>
                </td>
                <td>{item.org_id}</td>
                <td>{item.indicator_type}</td>
                <td className="truncate-cell" title={item.value}>
                  {item.value}
                </td>
                <td>{item.classification}</td>
                <td>{item.model_confidence}</td>
                <td>{item.severity}</td>
                <td>{item.credibility}</td>
                <td>
                  <LocalTime value={item.timestamp} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
