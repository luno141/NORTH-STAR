import { IntegrityCheck } from "@/components/IntegrityCheck";
import { LocalTime } from "@/components/LocalTime";
import { getIntegrityAnchors } from "@/lib/api";

export default async function AuditPage() {
  const anchors = await getIntegrityAnchors(12);

  return (
    <div className="space-y-6">
      <section className="mission-hero hud-panel">
        <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-center">
          <div className="mission-hero__copy">
            <p className="hud-kicker">Hash chain verification / anchor history / audit posture</p>
            <h2 className="text-4xl font-semibold leading-[0.95] text-white sm:text-5xl">Integrity command view</h2>
            <p className="max-w-2xl text-base leading-7 text-slate-300/76 sm:text-lg">
              Inspect the append-only ledger, create fresh anchors, and confirm that the intelligence chain has not been
              silently altered.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="hero-sidecar__panel">
              <span>Anchors</span>
              <strong>{anchors.length}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Latest anchor</span>
              <strong>{anchors[0]?.up_to_ledger_id ?? 0}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Chain posture</span>
              <strong>{anchors.length ? "Tracked" : "Idle"}</strong>
            </div>
          </div>
        </div>
      </section>

      <IntegrityCheck />

      <section className="hud-panel overflow-hidden p-0">
        <div className="hud-table-head">
          <div>
            <p className="hud-panel-title">Anchor History</p>
            <p className="mt-1 text-sm text-slate-300/66">Recent cryptographic checkpoints for the append-only ledger.</p>
          </div>
        </div>
        <table className="hud-table">
          <thead>
            <tr>
              <th>Anchor ID</th>
              <th>Up To Ledger</th>
              <th>Head Hash</th>
              <th>Anchor Hash</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {anchors.map((anchor) => (
              <tr key={anchor.id}>
                <td>{anchor.id}</td>
                <td>{anchor.up_to_ledger_id}</td>
                <td>{anchor.head_hash.slice(0, 18)}...</td>
                <td>{anchor.anchor_hash.slice(0, 18)}...</td>
                <td>
                  <LocalTime value={anchor.created_at} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
