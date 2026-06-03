import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { useVesselStore } from "../../store/vesselStore";
import type { Port } from "../../types";

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const RISK_COLOR_EXPR = [
  "match", ["get", "risk_level"],
  "HIGH",   "#ef4444",
  "MEDIUM", "#f59e0b",
  "LOW",    "#22c55e",
  "#6b7280",
] as any;

interface Props {
  ports: Port[];
  onVesselClick: (mmsi: number) => void;
}

function toVesselGeoJSON(vessels: Map<number, any>): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: Array.from(vessels.values()).map((v) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [v.lon, v.lat] },
      properties: {
        mmsi:       v.mmsi,
        name:       v.name ?? `MMSI ${v.mmsi}`,
        risk_level: v.risk_level ?? "NONE",
        speed:      v.speed ?? 0,
      },
    })),
  };
}

function toPortGeoJSON(ports: Port[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: ports.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: { id: p.id, name: p.name, congestion: p.congestion_pct ?? 0 },
    })),
  };
}

export function VesselMap({ ports, onVesselClick }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const mapLoaded = useRef(false);
  const vessels = useVesselStore((s) => s.vessels);

  // Always keep latest GeoJSON in refs so the load handler can read them
  const vesselGeoJSON = useRef<GeoJSON.FeatureCollection>(toVesselGeoJSON(new Map()));
  const portGeoJSON = useRef<GeoJSON.FeatureCollection>(toPortGeoJSON([]));
  const onVesselClickRef = useRef(onVesselClick);
  onVesselClickRef.current = onVesselClick;

  // ── Initialise map once ───────────────────────────────────────────────────
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: [20, 30],   // centred globally
      zoom: 2,
      renderWorldCopies: false,
    });
    map.current = m;

    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl(), "bottom-right");

    m.on("load", () => {
      mapLoaded.current = true;

      // ── Vessel source + layers ────────────────────────────────────────────
      m.addSource("vessels", { type: "geojson", data: vesselGeoJSON.current });

      m.addLayer({
        id: "vessels-glow",
        type: "circle",
        source: "vessels",
        paint: {
          "circle-radius":  ["interpolate", ["linear"], ["zoom"], 2, 8, 6, 14, 10, 20],
          "circle-color":   RISK_COLOR_EXPR,
          "circle-opacity": 0.2,
          "circle-blur":    1,
        },
      });

      m.addLayer({
        id: "vessels-dot",
        type: "circle",
        source: "vessels",
        paint: {
          "circle-radius":       ["interpolate", ["linear"], ["zoom"], 2, 4, 6, 7, 10, 11],
          "circle-color":        RISK_COLOR_EXPR,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "rgba(255,255,255,0.8)",
          "circle-opacity":      1,
        },
      });

      m.on("click", "vessels-dot", (e) => {
        const mmsi = e.features?.[0]?.properties?.mmsi as number;
        if (mmsi) onVesselClickRef.current(mmsi);
      });
      m.on("mouseenter", "vessels-dot", () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", "vessels-dot", () => { m.getCanvas().style.cursor = ""; });

      // ── Port source + layers ──────────────────────────────────────────────
      m.addSource("ports", { type: "geojson", data: portGeoJSON.current });

      m.addLayer({
        id: "port-ring",
        type: "circle",
        source: "ports",
        paint: {
          "circle-radius":       ["interpolate", ["linear"], ["get", "congestion"], 0, 10, 100, 30],
          "circle-color":        ["interpolate", ["linear"], ["get", "congestion"], 0, "#22c55e", 50, "#f59e0b", 80, "#ef4444"],
          "circle-opacity":      0.35,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-stroke-opacity": 0.4,
        },
      });

      m.addLayer({
        id: "port-labels",
        type: "symbol",
        source: "ports",
        layout: {
          "text-field":   ["get", "name"],
          "text-size":    11,
          "text-offset":  [0, 2],
          "text-anchor":  "top",
        },
        paint: {
          "text-color":       "#94a3b8",
          "text-halo-color":  "#0a0e1a",
          "text-halo-width":  1,
        },
      });
    });

    return () => {
      mapLoaded.current = false;
      m.remove();
      map.current = null;
    };
  }, []);

  // ── Push vessel updates into the map source whenever store changes ─────────
  useEffect(() => {
    vesselGeoJSON.current = toVesselGeoJSON(vessels);
    if (!mapLoaded.current || !map.current) return;
    (map.current.getSource("vessels") as maplibregl.GeoJSONSource)
      ?.setData(vesselGeoJSON.current);
  }, [vessels]);

  // ── Push port updates ─────────────────────────────────────────────────────
  useEffect(() => {
    portGeoJSON.current = toPortGeoJSON(ports);
    if (!mapLoaded.current || !map.current) return;
    (map.current.getSource("ports") as maplibregl.GeoJSONSource)
      ?.setData(portGeoJSON.current);
  }, [ports]);

  return (
    <div
      ref={mapContainer}
      style={{ width: "100%", height: "100%", borderRadius: "8px", overflow: "hidden" }}
    />
  );
}
