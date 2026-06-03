import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../../api/queries";
import { format } from "date-fns";
import type { RiskLevel } from "../../types";

const RISK_COLOR: Record<RiskLevel, string> = {
  HIGH: "#ef4444", MEDIUM: "#f59e0b", LOW: "#22c55e",
};

export function HighRiskTable() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["high-risk-shipments"],
    queryFn: () => analyticsApi.highRiskShipments(20),
    refetchInterval: 60_000,
  });

  return (
    <div style={container}>
      <h3 style={title}>Active Risk Alerts</h3>
      {isLoading && <div style={empty}>Loading...</div>}
      {!isLoading && data.length === 0 && (
        <div style={empty}>No high/medium risk shipments</div>
      )}
      <div style={{ overflowY: "auto", maxHeight: 340 }}>
        {data.map((row: any) => (
          <div key={`${row.mmsi}-${row.order_ref}`} style={rowStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>
                {row.vessel_name ?? `MMSI ${row.mmsi}`}
              </span>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                background: RISK_COLOR[row.risk_level as RiskLevel] + "33",
                color: RISK_COLOR[row.risk_level as RiskLevel],
              }}>
                {row.risk_level}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "#94a3b8" }}>
              {row.order_ref} · {row.origin_port} → {row.dest_port}
            </div>
            {row.summary && (
              <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 4, lineHeight: 1.4 }}>
                {row.summary}
              </div>
            )}
            {row.scheduled_eta && (
              <div style={{ fontSize: 10, color: "#475569", marginTop: 4 }}>
                ETA: {format(new Date(row.scheduled_eta), "MMM d, yyyy")}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const container: React.CSSProperties = {
  background: "#0f172a",
  border: "1px solid #1e293b",
  borderRadius: 10,
  padding: 16,
  flex: 1,
  minWidth: 0,
};

const title: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "#94a3b8",
  marginBottom: 12,
  textTransform: "uppercase",
  letterSpacing: 0.5,
};

const rowStyle: React.CSSProperties = {
  padding: "10px 0",
  borderBottom: "1px solid #1e293b",
};

const empty: React.CSSProperties = {
  fontSize: 13,
  color: "#475569",
  padding: "24px 0",
  textAlign: "center",
};
