const points = "0,70 20,58 40,62 60,30 80,40 100,22 120,52 140,28 160,64 180,34 200,46 220,24 240,70";

export function HudWaveform() {
  return (
    <div className="wave-wrap" aria-label="Signal waveform">
      <svg viewBox="0 0 240 80" className="wave-svg" role="img">
        {[0, 20, 40, 60, 80].map((y) => (
          <line key={y} x1="0" y1={y} x2="240" y2={y} className="wave-grid" />
        ))}
        {[0, 40, 80, 120, 160, 200, 240].map((x) => (
          <line key={x} x1={x} y1="0" x2={x} y2="80" className="wave-grid" />
        ))}
        <polyline points={points} className="wave-path" />
      </svg>
    </div>
  );
}
