import { useQuery } from "@tanstack/react-query";
import { vesselApi } from "../../api/queries";
import { useVesselStore } from "../../store/vesselStore";
import { format } from "date-fns";
import type { RiskLevel } from "../../types";

const RISK_BADGE: Record<RiskLevel, string> = {
  HIGH:   "background:#ef4444;color:#fff",
  MEDIUM: "background:#f59e0b;color:#000",
  LOW:    "background:#22c55e;color:#fff",
};

interface Props {
  mmsi: number;
  onClose: () => void;
}

export function VesselPanel({ mmsi, onClose }: Props) {
  const vessels = useVesselStore((s) => s.vessels);
  const vessel = vessels.get(mmsi);

  const { data: risk } = useQuery({
    queryKey: ["vessel-risk", mmsi],
    queryFn: () => vesselApi.getRisk(mmsi),
    refetchInterval: 60_000,
  });

  if (!vessel) return null;

  const badgeStyle = risk?.risk_level
    ? RISK_BADGE[risk.risk_level as RiskLevel]
    : "background:#6b7280;color:#fff";

  return (
    <div style={panelStyle}>
      <button onClick={onClose} style={closeBtn}>✕</button>

      <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>
        {vessel.name ?? `MMSI ${mmsi}`}
      </h2>
      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 12 }}>
        {vessel.vessel_type_name} · {vessel.flag ?? "Unknown flag"}
      </div>

      {risk && (
        <div style={{ marginBottom: 16 }}>
          <span style={{ ...badgeSpan, cssText: badgeStyle } as any}>
            {risk.risk_level} RISK — {risk.total_score.toFixed(1)}/100
          </span>
          {risk.summary && (
            <p style={{ fontSize: 12, color: "#cbd5e1", marginTop: 8, lineHeight: 1.5 }}>
              {risk.summary}
            </p>
          )}
        </div>
      )}

      <div style={grid}>
        <Stat label="Speed" value={vessel.speed != null ? `${vessel.speed.toFixed(1)} kn` : "—"} />
        <Stat label="Heading" value={vessel.heading != null ? `${vessel.heading.toFixed(0)}°` : "—"} />
        <Stat label="Lat" value={vessel.lat.toFixed(4)} />
        <Stat label="Lon" value={vessel.lon.toFixed(4)} />
        <Stat
          label="Last seen"
          value={format(new Date(vessel.last_seen), "HH:mm:ss")}
        />
      </div>

      {risk && (
        <div style={{ marginTop: 16 }}>
          <div style={sectionTitle}>Risk Breakdown</div>
          <ScoreBar label="ETA Delay" score={risk.eta_score ?? 0} max={40}
            detail={risk.eta_delay_days != null ? `${risk.eta_delay_days.toFixed(1)} days late` : undefined} />
          <ScoreBar label="Congestion" score={risk.congestion_score ?? 0} max={30}
            detail={risk.congestion_pct != null ? `${risk.congestion_pct.toFixed(0)}%` : undefined} />
          <ScoreBar label="Weather" score={risk.weather_score ?? 0} max={30}
            detail={risk.weather_max_wave_m != null ? `${risk.weather_max_wave_m.toFixed(1)}m waves` : undefined} />
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

function ScoreBar({ label, score, max, detail }: { label: string; score: number; max: number; detail?: string }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = pct > 66 ? "#ef4444" : pct > 33 ? "#f59e0b" : "#22c55e";
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
        <span style={{ color: "#94a3b8" }}>{label}</span>
        <span style={{ color: "#e2e8f0" }}>{score.toFixed(1)} / {max}{detail ? ` · ${detail}` : ""}</span>
      </div>
      <div style={{ background: "#1e293b", borderRadius: 4, height: 6 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.5s" }} />
      </div>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  position: "absolute",
  top: 16,
  right: 16,
  width: 300,
  background: "#0f172a",
  border: "1px solid #1e293b",
  borderRadius: 12,
  padding: 20,
  zIndex: 10,
  boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
};

const closeBtn: React.CSSProperties = {
  position: "absolute",
  top: 12,
  right: 12,
  background: "none",
  border: "none",
  color: "#64748b",
  cursor: "pointer",
  fontSize: 14,
};

const badgeSpan: React.CSSProperties = {
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 20,
  fontSize: 11,
  fontWeight: 700,
};

const grid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "10px 16px",
};

const sectionTitle: React.CSSProperties = {
  fontSize: 11,
  textTransform: "uppercase",
  color: "#475569",
  letterSpacing: 1,
  marginBottom: 10,
};
