from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VesselPosition(BaseModel):
    mmsi: int
    lat: float
    lon: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    course: Optional[float] = None
    nav_status: Optional[int] = None
    time: datetime
    vessel_name: Optional[str] = None
    vessel_type_name: Optional[str] = None
    flag: Optional[str] = None


class VesselLive(BaseModel):
    mmsi: int
    name: Optional[str] = None
    flag: Optional[str] = None
    vessel_type_name: Optional[str] = None
    lat: float
    lon: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    nav_status: Optional[int] = None
    last_seen: datetime
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None


class VesselTrackPoint(BaseModel):
    time: datetime
    lat: float
    lon: float
    speed: Optional[float] = None
    heading: Optional[float] = None


class RiskScore(BaseModel):
    time: datetime
    mmsi: int
    order_id: Optional[UUID] = None
    total_score: float
    risk_level: str
    eta_delay_days: Optional[float] = None
    eta_score: Optional[float] = None
    congestion_pct: Optional[float] = None
    congestion_score: Optional[float] = None
    weather_max_wave_m: Optional[float] = None
    weather_score: Optional[float] = None
    summary: Optional[str] = None


class PortCongestion(BaseModel):
    port_id: int
    port_name: str
    time: datetime
    vessels_anchored: int
    vessels_at_berth: int
    congestion_pct: Optional[float] = None


class ShipmentOrder(BaseModel):
    id: UUID
    order_ref: str
    customer: str
    commodity: Optional[str] = None
    value_usd: Optional[int] = None
    origin_port_name: Optional[str] = None
    dest_port_name: Optional[str] = None
    vessel_mmsi: Optional[int] = None
    vessel_name: Optional[str] = None
    scheduled_etd: Optional[datetime] = None
    scheduled_eta: Optional[datetime] = None
    status: str
    current_risk_level: Optional[str] = None
    current_risk_score: Optional[float] = None


class ShipmentOrderCreate(BaseModel):
    order_ref: str = Field(..., min_length=1)
    customer: str = Field(..., min_length=1)
    commodity: Optional[str] = None
    value_usd: Optional[int] = None
    origin_port_id: int
    dest_port_id: int
    vessel_mmsi: Optional[int] = None
    scheduled_etd: Optional[datetime] = None
    scheduled_eta: Optional[datetime] = None


class PortPerformance(BaseModel):
    port_id: int
    port_name: str
    country: Optional[str] = None
    avg_congestion_pct: Optional[float] = None
    peak_congestion_pct: Optional[float] = None
    days_over_50_pct: Optional[int] = None


class LaneRisk(BaseModel):
    origin: str
    destination: str
    month: int
    avg_risk_score: float
    shipment_count: int
