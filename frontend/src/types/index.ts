export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface VesselLive {
  mmsi: number;
  name?: string;
  flag?: string;
  vessel_type_name?: string;
  lat: number;
  lon: number;
  speed?: number;
  heading?: number;
  nav_status?: number;
  last_seen: string;
  risk_level?: RiskLevel;
  risk_score?: number;
}

export interface VesselTrackPoint {
  time: string;
  lat: number;
  lon: number;
  speed?: number;
  heading?: number;
}

export interface RiskScore {
  time: string;
  mmsi: number;
  order_id?: string;
  total_score: number;
  risk_level: RiskLevel;
  eta_delay_days?: number;
  eta_score?: number;
  congestion_pct?: number;
  congestion_score?: number;
  weather_max_wave_m?: number;
  weather_score?: number;
  summary?: string;
}

export interface Port {
  id: number;
  name: string;
  country?: string;
  un_locode?: string;
  lat: number;
  lon: number;
  congestion_pct?: number;
  vessels_anchored?: number;
  last_updated?: string;
}

export interface ShipmentOrder {
  id: string;
  order_ref: string;
  customer: string;
  commodity?: string;
  value_usd?: number;
  origin_port_name?: string;
  dest_port_name?: string;
  vessel_mmsi?: number;
  vessel_name?: string;
  scheduled_etd?: string;
  scheduled_eta?: string;
  status: string;
  current_risk_level?: RiskLevel;
  current_risk_score?: number;
}

export interface FleetSummary {
  active_vessels: number;
  orders_in_transit: number;
  high_risk_count: number;
  medium_risk_count: number;
  alerts_24h: number;
}

export interface LivePositionUpdate {
  mmsi: number;
  lat: number;
  lon: number;
  speed?: number;
  heading?: number;
  nav_status?: number;
  time: string;
}
