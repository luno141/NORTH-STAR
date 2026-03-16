import { AdminPoliciesPanel } from "@/components/AdminPoliciesPanel";
import { AdminSourcesPanel } from "@/components/AdminSourcesPanel";
import { LocalTime } from "@/components/LocalTime";
import { ReliabilityPanel } from "@/components/ReliabilityPanel";
import {
  getAdminIngestionRuns,
  getAdminIngestionSources,
  getAdminOverview,
  getAdminPolicies,
  getAdminUsers,
  getSourceReliability
} from "@/lib/api";

export default async function AdminPage() {
  const [overview, users, sources, runs, policies, reliability] = await Promise.all([
    getAdminOverview(),
    getAdminUsers(),
    getAdminIngestionSources(),
    getAdminIngestionRuns(24),
    getAdminPolicies(),
    getSourceReliability()
  ]);

  return (
    <div className="space-y-6">
      <section className="mission-hero hud-panel">
        <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-center">
          <div className="mission-hero__copy">
            <p className="hud-kicker">Operator controls / source scheduling / policy state</p>
            <h2 className="text-4xl font-semibold leading-[0.95] text-white sm:text-5xl">Admin command deck</h2>
            <p className="max-w-2xl text-base leading-7 text-slate-300/76 sm:text-lg">
              Control live feeds, tune share policy, inspect recent source runs, and manage the organization’s operating
              posture from one mission-grade admin surface.
            </p>
            <div className="mission-hero__chips">
              <span className="session-pill">org {overview.org_name}</span>
              <span className="session-pill">ready {overview.ready ? "yes" : "no"}</span>
              <span className="session-pill">runs / 24h {overview.recent_run_count}</span>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="hero-sidecar__panel">
              <span>Sources</span>
              <strong>{overview.source_count}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Source errors</span>
              <strong>{overview.source_error_count}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Critical intel</span>
              <strong>{overview.critical_intel_count}</strong>
            </div>
            <div className="hero-sidecar__panel">
              <span>Avg credibility</span>
              <strong>{overview.avg_credibility}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="hud-metric-strip">
        <div className="hud-metric">
          <p>Users</p>
          <strong>{overview.user_count}</strong>
        </div>
        <div className="hud-metric">
          <p>Contributors</p>
          <strong>{overview.contributor_count}</strong>
        </div>
        <div className="hud-metric">
          <p>Policies</p>
          <strong>{overview.policy_count}</strong>
        </div>
        <div className="hud-metric">
          <p>Intel</p>
          <strong>{overview.active_intel_count}</strong>
        </div>
        <div className="hud-metric">
          <p>Generated</p>
          <strong>
            <LocalTime value={overview.generated_at} />
          </strong>
        </div>
      </section>

      <div className="space-y-6">
        <AdminSourcesPanel sources={sources} runs={runs} />
        <AdminPoliciesPanel policies={policies} />
        <ReliabilityPanel rows={reliability} />
      </div>

      <section className="hud-panel overflow-hidden p-0">
        <div className="hud-table-head">
          <div>
            <p className="hud-panel-title">Organization Users</p>
            <p className="mt-1 text-sm text-slate-300/66">Role, reputation, and rotation state for your tenant.</p>
          </div>
        </div>
        <table className="hud-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Reputation</th>
              <th>Active</th>
              <th>Key Rotated</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.name}</td>
                <td>{user.role}</td>
                <td>{user.reputation}</td>
                <td>{user.is_active ? "yes" : "no"}</td>
                <td>{user.key_rotated_at ? <LocalTime value={user.key_rotated_at} /> : "never"}</td>
                <td>
                  <LocalTime value={user.created_at} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
