"""
Position engine — computes a vessel's current lat/lon along a great-circle
route using deterministic time-based interpolation.

No state stored: given current time + departure offset, position is always
calculable. When a vessel completes a route it automatically restarts.
"""

import math
from datetime import datetime, timezone
from typing import NamedTuple


class Position(NamedTuple):
    lat: float
    lon: float
    heading: float   # degrees true
    speed: float     # knots


# ── Great-circle math ─────────────────────────────────────────────────────────

R_NM = 3440.065  # Earth radius in nautical miles


def haversine_nm(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in nautical miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_NM * math.asin(math.sqrt(a))


def bearing(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Initial bearing from point 1 → point 2 in degrees (0–360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def interpolate_gc(
    lon1: float, lat1: float,
    lon2: float, lat2: float,
    fraction: float,
) -> tuple[float, float]:
    """
    Interpolate along great circle between two points.
    fraction=0 → start, fraction=1 → end.
    """
    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2, lam2 = math.radians(lat2), math.radians(lon2)

    d = 2 * math.asin(math.sqrt(
        math.sin((phi2 - phi1) / 2) ** 2 +
        math.cos(phi1) * math.cos(phi2) * math.sin((lam2 - lam1) / 2) ** 2
    ))
    if d < 1e-10:
        return lon1, lat1

    f = fraction
    a = math.sin((1 - f) * d) / math.sin(d)
    b = math.sin(f * d) / math.sin(d)

    x = a * math.cos(phi1) * math.cos(lam1) + b * math.cos(phi2) * math.cos(lam2)
    y = a * math.cos(phi1) * math.sin(lam1) + b * math.cos(phi2) * math.sin(lam2)
    z = a * math.sin(phi1) + b * math.sin(phi2)

    phi = math.atan2(z, math.sqrt(x ** 2 + y ** 2))
    lam = math.atan2(y, x)
    return math.degrees(lam), math.degrees(phi)


# ── Route geometry ────────────────────────────────────────────────────────────

def build_legs(waypoints: list[tuple[float, float]]) -> list[dict]:
    """Pre-compute leg distances and cumulative distances for a route."""
    legs = []
    cumulative = 0.0
    for i in range(len(waypoints) - 1):
        lon1, lat1 = waypoints[i]
        lon2, lat2 = waypoints[i + 1]
        dist = haversine_nm(lon1, lat1, lon2, lat2)
        legs.append({
            "lon1": lon1, "lat1": lat1,
            "lon2": lon2, "lat2": lat2,
            "dist_nm": dist,
            "cum_start": cumulative,
            "cum_end": cumulative + dist,
        })
        cumulative += dist
    return legs


def apply_lateral_offset(
    lon: float, lat: float, heading_deg: float, offset_nm: float
) -> tuple[float, float]:
    """
    Shift a position by offset_nm nautical miles perpendicular to heading.
    Positive offset = starboard (right), negative = port (left).
    """
    if abs(offset_nm) < 0.01:
        return lon, lat
    perp_deg = (heading_deg + 90) % 360
    perp_rad = math.radians(perp_deg)
    # 1 nm ≈ 1/60 degree latitude; longitude degree shrinks with cos(lat)
    dlat = (offset_nm / 60) * math.cos(perp_rad)
    cos_lat = math.cos(math.radians(lat))
    dlon = (offset_nm / 60) * math.sin(perp_rad) / (cos_lat if cos_lat > 0.01 else 0.01)
    return round(lon + dlon, 5), round(lat + dlat, 5)


def position_along_route(
    legs: list[dict],
    total_nm: float,
    nm_traveled: float,
    lateral_offset_nm: float = 0.0,
) -> Position:
    """Return the position and heading at nm_traveled along the pre-built legs."""
    nm_traveled = nm_traveled % total_nm  # loop the route

    for leg in legs:
        if leg["cum_start"] <= nm_traveled <= leg["cum_end"]:
            frac = (nm_traveled - leg["cum_start"]) / leg["dist_nm"] if leg["dist_nm"] > 0 else 0
            lon, lat = interpolate_gc(
                leg["lon1"], leg["lat1"],
                leg["lon2"], leg["lat2"],
                frac,
            )
            hdg = bearing(leg["lon1"], leg["lat1"], leg["lon2"], leg["lat2"])
            lon, lat = apply_lateral_offset(lon, lat, hdg, lateral_offset_nm)
            return Position(lat=lat, lon=lon, heading=round(hdg, 1), speed=0.0)

    last = legs[-1]
    return Position(lat=last["lat2"], lon=last["lon2"], heading=0.0, speed=0.0)


# ── Per-vessel position computation ──────────────────────────────────────────

# Epoch: a fixed reference start time (routes loop relative to this)
_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def current_position(
    waypoints: list[tuple[float, float]],
    speed_kn: float,
    offset_hours: float,
    lateral_offset_nm: float = 0.0,
    legs: list[dict] | None = None,
) -> Position:
    """
    Compute the vessel's current lat/lon based on current UTC time,
    its departure offset, speed, and lateral scatter.
    """
    if legs is None:
        legs = build_legs(waypoints)

    total_nm = legs[-1]["cum_end"]
    transit_hours = total_nm / speed_kn

    now = datetime.now(tz=timezone.utc)
    elapsed_hours = (now - _EPOCH).total_seconds() / 3600 + offset_hours
    nm_traveled = (elapsed_hours * speed_kn) % total_nm

    pos = position_along_route(legs, total_nm, nm_traveled, lateral_offset_nm)
    return Position(lat=pos.lat, lon=pos.lon, heading=pos.heading, speed=round(speed_kn, 1))
