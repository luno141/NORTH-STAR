const BLIPS = [
  { left: "28%", top: "36%", delay: "0s" },
  { left: "68%", top: "24%", delay: "1.1s" },
  { left: "73%", top: "62%", delay: "1.7s" },
  { left: "40%", top: "74%", delay: "0.55s" }
];

const RINGS = [72, 120, 168, 216];

export function HudRadar() {
  return (
    <div className="mission-radar" aria-label="Threat radar">
      <div className="mission-radar__meta">
        <span className="session-pill">southern relay</span>
        <span className="session-pill">tracking / 04 contacts</span>
      </div>

      <div className="mission-radar__scope">
        <div className="mission-radar__grid" />
        {RINGS.map((size) => (
          <div key={size} className="mission-radar__ring" style={{ height: size, width: size }} />
        ))}
        <div className="mission-radar__axis mission-radar__axis--x" />
        <div className="mission-radar__axis mission-radar__axis--y" />
        <div className="mission-radar__sweep" />
        <div className="mission-radar__center" />
        {BLIPS.map((blip) => (
          <span
            key={`${blip.left}-${blip.top}`}
            className="mission-radar__blip"
            style={{ animationDelay: blip.delay, left: blip.left, top: blip.top }}
          />
        ))}
      </div>

      <div className="mission-radar__footer">
        <div>
          <span>Depth</span>
          <strong>600</strong>
        </div>
        <div>
          <span>Wind</span>
          <strong>54.3</strong>
        </div>
        <div>
          <span>Mode</span>
          <strong>Live</strong>
        </div>
      </div>
    </div>
  );
}
