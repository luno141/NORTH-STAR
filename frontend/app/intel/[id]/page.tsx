import { LocalTime } from "@/components/LocalTime";
import { getIntel, getIntelProof, getIntelSimilar } from "@/lib/api";

export default async function IntelDetail({ params }: { params: { id: string } }) {
  const [intel, proof, similar] = await Promise.all([getIntel(params.id), getIntelProof(params.id), getIntelSimilar(params.id)]);

  return (
    <div className="space-y-6">
      <section className="mission-hero hud-panel">
        <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-center">
          <div className="mission-hero__copy">
            <p className="hud-kicker">Forensic detail / model reasoning / chain proof</p>
            <h2 className="text-4xl font-semibold leading-[0.95] text-white sm:text-5xl">Intel dossier #{intel.id}</h2>
            <p className="max-w-2xl text-base leading-7 text-slate-300/76 sm:text-lg">
              A complete view of the indicator, its model reasoning, source context, and append-only integrity chain.
            </p>
            <div className="mission-hero__chips">
              <span className="session-pill">{intel.indicator_type}</span>
              <span className="session-pill">{intel.classification}</span>
              <span className="session-pill">visibility / {intel.visibility}</span>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="hero-sidecar__panel">
              <span>Severity</span>
              <strong>{intel.severity}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Credibility</span>
              <strong>{intel.credibility}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Model confidence</span>
              <strong>{intel.model_confidence}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Proof entries</span>
              <strong>{proof.entries.length}</strong>
            </div>
          </div>
        </div>
      </section>

      <div className="detail-grid">
        <section className="hud-panel p-5 detail-span-2">
          <p className="hud-panel-title">Record Overview</p>
          <div className="detail-meta-grid mt-4">
            <div className="hud-data-box">
              <span>Indicator</span>
              <strong>{intel.indicator_type}</strong>
            </div>
            <div className="hud-data-box">
              <span>Source</span>
              <strong>{intel.source}</strong>
            </div>
            <div className="hud-data-box">
              <span>Observed</span>
              <strong>
                <LocalTime value={intel.timestamp} />
              </strong>
            </div>
            <div className="hud-data-box">
              <span>Ingested</span>
              <strong>
                <LocalTime value={intel.created_at} />
              </strong>
            </div>
          </div>
          <div className="mt-4 rounded-[26px] border border-white/8 bg-white/[0.04] p-5">
            <p className="mb-2 text-[11px] uppercase tracking-[0.22em] text-slate-400/76">Indicator value</p>
            <p className="break-all text-base text-slate-100">{intel.value}</p>
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-[26px] border border-white/8 bg-white/[0.04] p-5">
              <p className="mb-2 text-[11px] uppercase tracking-[0.22em] text-slate-400/76">Context</p>
              <p className="text-sm leading-7 text-slate-300/82">{intel.context_text}</p>
            </div>
            <div className="rounded-[26px] border border-white/8 bg-white/[0.04] p-5">
              <p className="mb-2 text-[11px] uppercase tracking-[0.22em] text-slate-400/76">Evidence</p>
              <p className="break-words text-sm leading-7 text-slate-300/82">{intel.evidence}</p>
            </div>
          </div>
        </section>

        <section className="hud-panel p-5">
          <p className="hud-panel-title">Explanation</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {intel.explanation_terms.length ? (
              intel.explanation_terms.map((term) => (
                <span key={term} className="session-pill">
                  {term}
                </span>
              ))
            ) : (
              <p className="text-sm text-slate-400">No exported explanation terms available.</p>
            )}
          </div>
          <div className="mt-5 space-y-3">
            {Object.entries(intel.predicted_probs).map(([label, probability]) => (
              <div key={label}>
                <div className="mb-1 flex items-center justify-between text-xs uppercase tracking-[0.18em] text-slate-300/70">
                  <span>{label}</span>
                  <span>{(probability * 100).toFixed(1)}%</span>
                </div>
                <div className="hud-bar-track">
                  <div className="hud-bar-fill" style={{ width: `${probability * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="detail-grid">
        <section className="hud-panel p-5 detail-span-2">
          <p className="hud-panel-title">Integrity Chain</p>
          <div className="mt-4 overflow-x-auto">
            <table className="hud-table">
              <thead>
                <tr>
                  <th>Ledger ID</th>
                  <th>Prev Hash</th>
                  <th>Hash</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {proof.entries.map((entry) => (
                  <tr key={entry.ledger_id}>
                    <td>{entry.ledger_id}</td>
                    <td>{entry.prev_hash.slice(0, 18)}...</td>
                    <td>{entry.hash.slice(0, 18)}...</td>
                    <td>
                      <LocalTime value={entry.created_at} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="hud-panel p-5">
          <p className="hud-panel-title">Similar Intel</p>
          <div className="mt-4 space-y-3">
            {similar.length ? (
              similar.map((item) => (
                <div key={item.id} className="rounded-[24px] border border-white/8 bg-white/[0.04] px-4 py-3 text-sm text-slate-300/82">
                  <p className="font-medium text-white">#{item.id} · {item.indicator_type}</p>
                  <p className="mt-1 break-all">{item.value}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-400">distance {item.distance.toFixed(4)}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-400">No nearby indicators found.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
