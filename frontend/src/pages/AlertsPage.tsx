import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../api/queries";
import { format } from "date-fns";
import type { RiskLevel } from "../types";

const RISK_COLOR: Record<RiskLevel, string> = {
  HIGH: "#ef4444", MEDIUM: "#f59e0b", LOW: "#22c55e",
};

export function AlertsPage() {
  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ["alert-history"],
    queryFn: () => analyticsApi.alertHistory(100),
    refetchInterval: 30_000,
  });

  return (
    <div style={page}>
      <h1 style={pageTitle}>Alert History</h1>
      <div style={{ overflowX: "auto", flex: 1 }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              {["Time", "Vessel", "Order", "Channel", "Risk Level", "Message", "Delivered"].map((h) => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} style={empty}>Loading alerts...</td></tr>
            )}
            {!isLoading && alerts.length === 0 && (
              <tr><td colSpan={7} style={empty}>No alerts sent yet</td></tr>
            )}
            {alerts.map((a: any) => (
              <tr key={a.id}>
                <td style={td}>{format(new Date(a.sent_at), "MMM d HH:mm")}</td>
                <td style={td}>{a.vessel_name ?? (a.mmsi ? `MMSI ${a.mmsi}` : "—")}</td>
                <td style={td}>{a.order_id?.slice(0, 8) ?? "—"}</td>
                <td style={td}>
                  <span style={{ fontSize: 11, color: "#38bdf8", textTransform: "uppercase" }}>
                    {a.channel}
                  </span>
                </td>
                <td style={td}>
                  {a.risk_level && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                      background: RISK_COLOR[a.risk_level as RiskLevel] + "22",
                      color: RISK_COLOR[a.risk_level as RiskLevel],
                    }}>
                      {a.risk_level}
                    </span>
                  )}
                </td>
                <td style={{ ...td, maxWidth: 400, color: "#94a3b8", fontSize: 11 }}>
                  {a.message}
                </td>
                <td style={td}>
                  <span style={{ color: a.delivered ? "#22c55e" : "#ef4444", fontSize: 12 }}>
                    {a.delivered ? "✓" : "✗"}
                  </span>
                  {a.error && (
                    <span style={{ fontSize: 10, color: "#ef4444", marginLeft: 4 }}>{a.error}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const page: React.CSSProperties = {
  display: "flex", flexDirection: "column", height: "100%", padding: 24, gap: 16,
};

const pageTitle: React.CSSProperties = { fontSize: 18, fontWeight: 700 };

const tableStyle: React.CSSProperties = {
  width: "100%", borderCollapse: "collapse", fontSize: 13,
};

const th: React.CSSProperties = {
  padding: "10px 12px", textAlign: "left", color: "#475569",
  fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5,
  borderBottom: "1px solid #1e293b", whiteSpace: "nowrap",
};

const td: React.CSSProperties = {
  padding: "10px 12px", borderBottom: "1px solid #1e293b",
  color: "#cbd5e1", verticalAlign: "middle",
};

const empty: React.CSSProperties = {
  textAlign: "center", color: "#475569", padding: "40px 0", fontSize: 13,
};
