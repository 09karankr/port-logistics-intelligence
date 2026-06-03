import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { VesselMap } from "../components/Map/VesselMap";
import { VesselPanel } from "../components/Map/VesselPanel";
import { FleetSummaryBar } from "../components/Dashboard/FleetSummaryBar";
import { HighRiskTable } from "../components/Dashboard/HighRiskTable";
import { useVesselStore } from "../store/vesselStore";
import { useVesselStream } from "../hooks/useVesselStream";
import { vesselApi, portApi } from "../api/queries";

export function MapPage() {
  const [selectedMmsi, setSelectedMmsi] = useState<number | null>(null);
  const setVessels = useVesselStore((s) => s.setVessels);

  // Seed store with initial snapshot
  const { data: vessels } = useQuery({
    queryKey: ["vessels-live"],
    queryFn: vesselApi.getLive,
    refetchInterval: 30_000,
  });

  const { data: ports = [] } = useQuery({
    queryKey: ["ports-congestion"],
    queryFn: portApi.getAllCongestion,
    refetchInterval: 120_000,
  });

  useEffect(() => {
    if (vessels) setVessels(vessels);
  }, [vessels, setVessels]);

  // Subscribe to live WebSocket updates
  useVesselStream();

  const handleVesselClick = useCallback((mmsi: number) => {
    setSelectedMmsi(mmsi);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <FleetSummaryBar />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Map — takes most of the space */}
        <div style={{ flex: 1, position: "relative" }}>
          <VesselMap ports={ports} onVesselClick={handleVesselClick} />
          {selectedMmsi != null && (
            <VesselPanel mmsi={selectedMmsi} onClose={() => setSelectedMmsi(null)} />
          )}
          <MapLegend />
        </div>
        {/* Right sidebar */}
        <div style={sidebar}>
          <HighRiskTable />
        </div>
      </div>
    </div>
  );
}

function MapLegend() {
  return (
    <div style={legend}>
      {[
        { color: "#ef4444", label: "High Risk" },
        { color: "#f59e0b", label: "Medium Risk" },
        { color: "#22c55e", label: "Low Risk" },
        { color: "#6b7280", label: "No Data" },
      ].map(({ color, label }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
          <span style={{ fontSize: 11, color: "#94a3b8" }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

const sidebar: React.CSSProperties = {
  width: 320,
  background: "#080c18",
  borderLeft: "1px solid #1e293b",
  padding: 16,
  overflowY: "auto",
  display: "flex",
  flexDirection: "column",
  gap: 16,
};

const legend: React.CSSProperties = {
  position: "absolute",
  bottom: 32,
  left: 16,
  background: "rgba(10,14,26,0.85)",
  border: "1px solid #1e293b",
  borderRadius: 8,
  padding: "8px 12px",
  display: "flex",
  flexDirection: "column",
  gap: 5,
  backdropFilter: "blur(4px)",
};
