import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../../api/queries";

export function FleetSummaryBar() {
  const { data } = useQuery({
    queryKey: ["fleet-summary"],
    queryFn: analyticsApi.fleetSummary,
    refetchInterval: 30_000,
  });

  const stats = [
    { label: "Active Vessels",    value: data?.active_vessels ?? "—",    color: "#38bdf8" },
    { label: "Orders In Transit", value: data?.orders_in_transit ?? "—", color: "#818cf8" },
    { label: "High Risk",         value: data?.high_risk_count ?? "—",   color: "#ef4444" },
    { label: "Medium Risk",       value: data?.medium_risk_count ?? "—", color: "#f59e0b" },
    { label: "Alerts (24h)",      value: data?.alerts_24h ?? "—",        color: "#a78bfa" },
  ];

  return (
    <div style={barStyle}>
      {stats.map((s) => (
        <div key={s.label} style={statStyle}>
          <div style={{ fontSize: 22, fontWeight: 700, color: s.color }}>{s.value}</div>
          <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>{s.label}</div>
        </div>
      ))}
    </div>
  );
}

const barStyle: React.CSSProperties = {
  display: "flex",
  gap: 0,
  background: "#0f172a",
  borderBottom: "1px solid #1e293b",
  padding: "10px 24px",
};

const statStyle: React.CSSProperties = {
  flex: 1,
  textAlign: "center",
  borderRight: "1px solid #1e293b",
  padding: "0 16px",
};
