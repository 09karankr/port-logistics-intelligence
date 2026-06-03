import { PortPerformanceChart } from "../components/Analytics/PortPerformanceChart";
import { LaneRiskChart } from "../components/Analytics/LaneRiskChart";

export function AnalyticsPage() {
  return (
    <div style={page}>
      <h1 style={pageTitle}>Analytics</h1>
      <div style={row}>
        <PortPerformanceChart />
      </div>
      <div style={row}>
        <LaneRiskChart />
      </div>
    </div>
  );
}

const page: React.CSSProperties = {
  padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", gap: 20,
};

const pageTitle: React.CSSProperties = {
  fontSize: 18, fontWeight: 700,
};

const row: React.CSSProperties = {
  display: "flex", gap: 20,
};
