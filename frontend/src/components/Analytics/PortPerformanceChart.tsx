import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../../api/queries";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell,
} from "recharts";

export function PortPerformanceChart() {
  const { data = [] } = useQuery({
    queryKey: ["port-performance"],
    queryFn: () => analyticsApi.portPerformance(90),
  });

  const chartData = data.slice(0, 12).map((p: any) => ({
    name: p.port_name.replace("Port of ", ""),
    avg: parseFloat((p.avg_congestion_pct ?? 0).toFixed(1)),
    peak: parseFloat((p.peak_congestion_pct ?? 0).toFixed(1)),
  }));

  return (
    <div style={container}>
      <h3 style={title}>Port Congestion (90-day avg)</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="name"
            tick={{ fill: "#64748b", fontSize: 10 }}
            angle={-35}
            textAnchor="end"
          />
          <YAxis tick={{ fill: "#64748b", fontSize: 10 }} domain={[0, 100]} unit="%" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
            labelStyle={{ color: "#e2e8f0", fontSize: 12 }}
            itemStyle={{ color: "#94a3b8", fontSize: 11 }}
            formatter={(v: number) => [`${v}%`]}
          />
          <Bar dataKey="avg" name="Avg Congestion" radius={[4, 4, 0, 0]}>
            {chartData.map((entry: { name: string; avg: number; peak: number }) => (
              <Cell
                key={entry.name}
                fill={entry.avg > 70 ? "#ef4444" : entry.avg > 40 ? "#f59e0b" : "#22c55e"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
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
