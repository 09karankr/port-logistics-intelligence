import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../../api/queries";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export function LaneRiskChart() {
  const { data = [] } = useQuery({
    queryKey: ["lane-risk"],
    queryFn: () => analyticsApi.laneRisk(12),
  });

  const chartData = data.map((r: any) => ({
    lane: `${r.origin?.replace("Port of ", "")} → ${r.destination?.replace("Port of ", "")}`,
    month: MONTH_NAMES[(r.month ?? 1) - 1],
    monthNum: r.month,
    score: parseFloat((r.avg_risk_score ?? 0).toFixed(1)),
    count: r.shipment_count,
  }));

  const lanes = [...new Set(chartData.map((d: any) => d.lane))].slice(0, 10);

  return (
    <div style={container}>
      <h3 style={title}>Shipping Lane Risk by Month</h3>
      {data.length === 0 ? (
        <div style={empty}>No lane data yet — risk scores accumulate over time</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={th}>Lane</th>
                {MONTH_NAMES.map((m) => <th key={m} style={th}>{m}</th>)}
              </tr>
            </thead>
            <tbody>
              {lanes.map((lane) => (
                <tr key={String(lane)}>
                  <td style={td}>{String(lane)}</td>
                  {MONTH_NAMES.map((_, i) => {
                    const cell = chartData.find(
                      (d: any) => d.lane === lane && d.monthNum === i + 1
                    );
                    const score = cell?.score ?? null;
                    const bg = score == null ? "transparent"
                      : score > 70 ? "#ef444433"
                      : score > 40 ? "#f59e0b33"
                      : "#22c55e22";
                    const color = score == null ? "#1e293b"
                      : score > 70 ? "#ef4444"
                      : score > 40 ? "#f59e0b"
                      : "#22c55e";
                    return (
                      <td key={i} style={{ ...td, background: bg, color, textAlign: "center" }}>
                        {score != null ? score.toFixed(0) : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const container: React.CSSProperties = {
  background: "#0f172a",
  border: "1px solid #1e293b",
  borderRadius: 10,
  padding: 16,
};

const title: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "#94a3b8",
  marginBottom: 12,
  textTransform: "uppercase",
  letterSpacing: 0.5,
};

const empty: React.CSSProperties = {
  fontSize: 13,
  color: "#475569",
  textAlign: "center",
  padding: "32px 0",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 11,
};

const th: React.CSSProperties = {
  padding: "6px 8px",
  color: "#475569",
  fontWeight: 500,
  textAlign: "left",
  borderBottom: "1px solid #1e293b",
  whiteSpace: "nowrap",
};

const td: React.CSSProperties = {
  padding: "6px 8px",
  borderBottom: "1px solid #0f172a",
  whiteSpace: "nowrap",
  color: "#94a3b8",
  fontSize: 11,
};
