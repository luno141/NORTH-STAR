import { ContributorActions } from "@/components/ContributorActions";
import { getContributors } from "@/lib/api";

export default async function ContributorsPage() {
  const contributors = await getContributors();
  const highTrust = contributors.filter((c) => c.reputation >= 75).length;
  const lowTrust = contributors.filter((c) => c.reputation < 50).length;
  const average = contributors.length
    ? (contributors.reduce((sum, contributor) => sum + contributor.reputation, 0) / contributors.length).toFixed(1)
    : "0";

  return (
    <div className="space-y-6">
      <section className="mission-hero hud-panel">
        <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-center">
          <div className="mission-hero__copy">
            <p className="hud-kicker">Trust governance / analyst feedback / contributor posture</p>
            <h2 className="text-4xl font-semibold leading-[0.95] text-white sm:text-5xl">Contributor trust network</h2>
            <p className="max-w-2xl text-base leading-7 text-slate-300/76 sm:text-lg">
              Analyst actions directly influence contributor reputation, which in turn shapes default visibility and
              credibility scoring across the federated network.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="hero-sidecar__panel">
              <span>Contributors</span>
              <strong>{contributors.length}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>High trust</span>
              <strong>{highTrust}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Avg reputation</span>
              <strong>{average}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="hud-metric-strip">
        <div className="hud-metric">
          <p>High trust</p>
          <strong>{highTrust}</strong>
        </div>
        <div className="hud-metric">
          <p>Low trust</p>
          <strong>{lowTrust}</strong>
        </div>
        <div className="hud-metric">
          <p>Analyst actions</p>
          <strong>Live</strong>
        </div>
        <div className="hud-metric">
          <p>Visibility rule</p>
          <strong>Reputation-based</strong>
        </div>
        <div className="hud-metric">
          <p>Feed influence</p>
          <strong>Enabled</strong>
        </div>
      </section>

      <section className="hud-panel overflow-hidden p-0">
        <div className="hud-table-head">
          <div>
            <p className="hud-panel-title">Contributor Registry</p>
            <p className="mt-1 text-sm text-slate-300/66">Approve, upvote, or flag contributors against a specific intel record.</p>
          </div>
        </div>
        <table className="hud-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Org</th>
              <th>Reputation</th>
              <th>Trust Band</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {contributors.map((contributor) => (
              <tr key={contributor.id}>
                <td>{contributor.id}</td>
                <td>{contributor.name}</td>
                <td>{contributor.org_id}</td>
                <td>{contributor.reputation}</td>
                <td>
                  {contributor.reputation >= 75
                    ? "federated"
                    : contributor.reputation >= 40
                      ? "org"
                      : "private"}
                </td>
                <td>
                  <ContributorActions contributorId={contributor.id} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
