import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { orderApi } from "../api/queries";
import { format } from "date-fns";
import type { RiskLevel, ShipmentOrder } from "../types";

const RISK_COLOR: Record<RiskLevel, string> = {
  HIGH: "#ef4444", MEDIUM: "#f59e0b", LOW: "#22c55e",
};

const STATUS_COLOR: Record<string, string> = {
  in_transit: "#38bdf8", arrived: "#22c55e",
  delayed: "#f59e0b", pending: "#818cf8", cancelled: "#475569",
};

type FilterStatus = "all" | "in_transit" | "delayed" | "arrived";
type FilterRisk = "all" | "HIGH" | "MEDIUM" | "LOW";

export function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [riskFilter, setRiskFilter] = useState<FilterRisk>("all");

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ["orders", statusFilter, riskFilter],
    queryFn: () =>
      orderApi.list({
        status: statusFilter === "all" ? undefined : statusFilter,
        risk_level: riskFilter === "all" ? undefined : riskFilter,
        limit: 200,
      }),
    refetchInterval: 60_000,
  });

  return (
    <div style={page}>
      <div style={topBar}>
        <h1 style={pageTitle}>Shipment Orders</h1>
        <div style={filters}>
          <Select
            label="Status"
            value={statusFilter}
            options={[
              { value: "all", label: "All Statuses" },
              { value: "in_transit", label: "In Transit" },
              { value: "delayed", label: "Delayed" },
              { value: "arrived", label: "Arrived" },
            ]}
            onChange={(v) => setStatusFilter(v as FilterStatus)}
          />
          <Select
            label="Risk"
            value={riskFilter}
            options={[
              { value: "all", label: "All Risk" },
              { value: "HIGH", label: "High" },
              { value: "MEDIUM", label: "Medium" },
              { value: "LOW", label: "Low" },
            ]}
            onChange={(v) => setRiskFilter(v as FilterRisk)}
          />
        </div>
      </div>

      <div style={{ overflowX: "auto", flex: 1 }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              {["Order Ref", "Customer", "Vessel", "Route", "Commodity", "Scheduled ETA", "Status", "Risk"].map((h) => (
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={8} style={empty}>Loading shipments...</td></tr>
            )}
            {!isLoading && orders.length === 0 && (
              <tr><td colSpan={8} style={empty}>No orders found</td></tr>
            )}
            {orders.map((o: ShipmentOrder) => (
              <tr key={o.id} style={rowStyle}>
                <td style={td}><span style={{ fontWeight: 600 }}>{o.order_ref}</span></td>
                <td style={td}>{o.customer}</td>
                <td style={td}>{o.vessel_name ?? (o.vessel_mmsi ? `MMSI ${o.vessel_mmsi}` : "—")}</td>
                <td style={td}>
                  <span style={{ fontSize: 11 }}>
                    {o.origin_port_name?.replace("Port of ", "") ?? "?"} →{" "}
                    {o.dest_port_name?.replace("Port of ", "") ?? "?"}
                  </span>
                </td>
                <td style={td}>{o.commodity ?? "—"}</td>
                <td style={td}>
                  {o.scheduled_eta
                    ? format(new Date(o.scheduled_eta), "MMM d, yyyy")
                    : "—"}
                </td>
                <td style={td}>
                  <StatusBadge status={o.status} />
                </td>
                <td style={td}>
                  {o.current_risk_level ? (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                      background: RISK_COLOR[o.current_risk_level as RiskLevel] + "22",
                      color: RISK_COLOR[o.current_risk_level as RiskLevel],
                    }}>
                      {o.current_risk_level} {o.current_risk_score?.toFixed(0)}
                    </span>
                  ) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? "#475569";
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
      background: color + "22", color,
    }}>
      {status.replace("_", " ").toUpperCase()}
    </span>
  );
}

function Select({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#64748b" }}>
      {label}:
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={selectStyle}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

const page: React.CSSProperties = {
  display: "flex", flexDirection: "column", height: "100%", padding: 24, gap: 16,
};

const topBar: React.CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between",
};

const pageTitle: React.CSSProperties = {
  fontSize: 18, fontWeight: 700,
};

const filters: React.CSSProperties = {
  display: "flex", gap: 16,
};

const tableStyle: React.CSSProperties = {
  width: "100%", borderCollapse: "collapse", fontSize: 13,
};

const th: React.CSSProperties = {
  padding: "10px 12px", textAlign: "left", color: "#475569",
  fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5,
  borderBottom: "1px solid #1e293b", whiteSpace: "nowrap",
};

const td: React.CSSProperties = {
  padding: "12px 12px", borderBottom: "1px solid #1e293b",
  color: "#cbd5e1", verticalAlign: "middle",
};

const rowStyle: React.CSSProperties = {
  transition: "background 0.15s",
};

const empty: React.CSSProperties = {
  textAlign: "center", color: "#475569", padding: "40px 0", fontSize: 13,
};

const selectStyle: React.CSSProperties = {
  background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155",
  borderRadius: 6, padding: "4px 8px", fontSize: 12, cursor: "pointer",
};
