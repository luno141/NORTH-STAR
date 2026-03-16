const NODES = [
  { left: "16%", top: "28%", delay: "0s" },
  { left: "24%", top: "64%", delay: "1.2s" },
  { left: "39%", top: "18%", delay: "0.7s" },
  { left: "47%", top: "72%", delay: "1.8s" },
  { left: "61%", top: "33%", delay: "0.35s" },
  { left: "73%", top: "55%", delay: "1.55s" },
  { left: "80%", top: "26%", delay: "0.95s" }
];

export function ThreatGlobe() {
  return (
    <div className="orbital-core" aria-label="Orbital threat model">
      <div className="orbital-core__halo orbital-core__halo--outer" />
      <div className="orbital-core__halo orbital-core__halo--inner" />
      <div className="orbital-core__ring orbital-core__ring--one" />
      <div className="orbital-core__ring orbital-core__ring--two" />
      <div className="orbital-core__ring orbital-core__ring--three" />
      <div className="orbital-core__orbit orbital-core__orbit--a" />
      <div className="orbital-core__orbit orbital-core__orbit--b" />
      <div className="orbital-core__orbit orbital-core__orbit--c" />

      <div className="orbital-core__sphere">
        <div className="orbital-core__shine" />
        <div className="orbital-core__latitude orbital-core__latitude--top" />
        <div className="orbital-core__latitude orbital-core__latitude--mid" />
        <div className="orbital-core__latitude orbital-core__latitude--bottom" />
        <div className="orbital-core__longitude orbital-core__longitude--left" />
        <div className="orbital-core__longitude orbital-core__longitude--center" />
        <div className="orbital-core__longitude orbital-core__longitude--right" />
        <span className="orbital-core__continent orbital-core__continent--north-america" />
        <span className="orbital-core__continent orbital-core__continent--europe" />
        <span className="orbital-core__continent orbital-core__continent--asia" />
        <span className="orbital-core__continent orbital-core__continent--south-america" />
        <span className="orbital-core__continent orbital-core__continent--africa" />
        {NODES.map((node) => (
          <span
            key={`${node.left}-${node.top}`}
            className="orbital-core__node"
            style={{ animationDelay: node.delay, left: node.left, top: node.top }}
          />
        ))}
      </div>

      <div className="orbital-core__caption">
        <p>Orbital Threat Model</p>
        <span>global trust, motion, and relay field</span>
      </div>
    </div>
  );
}
