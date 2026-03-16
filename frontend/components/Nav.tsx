import Link from "next/link";

import { SessionPanel } from "@/components/SessionPanel";

const links = [
  { href: "/feed", label: "Feed" },
  { href: "/contributors", label: "Contributors" },
  { href: "/audit", label: "Audit"  },
  { href: "/admin", label: "Admin" }
];

export function Nav() {
  return (
    <header className="hud-topbar">
      <div className="hud-topbar-inner w-full px-4 py-4 sm:px-6 lg:px-8 xl:px-10 2xl:px-12">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="space-y-2">
            <p className="hud-kicker">Federated Threat Intelligence Integrity</p>
            <div className="flex flex-wrap items-end gap-3">
              <h1 className="text-2xl font-semibold leading-none sm:text-3xl">N★RTH STAR</h1>
              <span className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-[10px] uppercase tracking-[0.28em] text-slate-300/88">
                mission-grade control plane
              </span>
            </div>
            <p className="max-w-2xl text-sm text-slate-300/78 sm:text-[15px]">
              Clean federated threat operations with integrity proofs, contributor trust, and live ingest orchestration.
            </p>
          </div>

          <div className="flex flex-col gap-3 xl:items-end">
            <nav className="flex flex-wrap items-center gap-2">
              {links.map((link) => (
                <Link key={link.href} href={link.href} className="hud-nav-btn">
                  {link.label}
                </Link>
              ))}
            </nav>
            <SessionPanel />
          </div>
        </div>
      </div>
    </header>
  );
}
