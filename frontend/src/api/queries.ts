import { api } from "./client";
import type {
  VesselLive, VesselTrackPoint, RiskScore,
  Port, ShipmentOrder, FleetSummary,
} from "../types";

export const vesselApi = {
  getLive: () => api.get<VesselLive[]>("/vessels/live").then((r) => r.data),
  getTrack: (mmsi: number, hours = 24) =>
    api.get<VesselTrackPoint[]>(`/vessels/${mmsi}/track`, { params: { hours } }).then((r) => r.data),
  getRisk: (mmsi: number) =>
    api.get<RiskScore>(`/vessels/${mmsi}/risk`).then((r) => r.data),
  getRiskHistory: (mmsi: number, hours = 72) =>
    api.get<RiskScore[]>(`/vessels/${mmsi}/risk/history`, { params: { hours } }).then((r) => r.data),
};

export const portApi = {
  list: () => api.get<Port[]>("/ports").then((r) => r.data),
  getAllCongestion: () => api.get<Port[]>("/ports/congestion/all").then((r) => r.data),
  getCongestionHistory: (portId: number, days = 30) =>
    api.get(`/ports/${portId}/congestion/history`, { params: { days } }).then((r) => r.data),
};

export const orderApi = {
  list: (params?: { status?: string; risk_level?: string; limit?: number }) =>
    api.get<ShipmentOrder[]>("/orders", { params }).then((r) => r.data),
  get: (id: string) => api.get<ShipmentOrder>(`/orders/${id}`).then((r) => r.data),
};

export const analyticsApi = {
  fleetSummary: () => api.get<FleetSummary>("/analytics/fleet-summary").then((r) => r.data),
  portPerformance: (days = 90) =>
    api.get("/analytics/port-performance", { params: { days } }).then((r) => r.data),
  laneRisk: (months = 6) =>
    api.get("/analytics/lane-risk", { params: { months } }).then((r) => r.data),
  highRiskShipments: (limit = 20) =>
    api.get("/analytics/high-risk-shipments", { params: { limit } }).then((r) => r.data),
  alertHistory: (limit = 50) =>
    api.get("/analytics/alert-history", { params: { limit } }).then((r) => r.data),
};
