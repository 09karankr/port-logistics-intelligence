from datetime import datetime, timezone
from typing import Any

# AIS vessel type code → human name
VESSEL_TYPE_NAMES = {
    70: "Cargo", 71: "Cargo - Hazardous A", 72: "Cargo - Hazardous B",
    73: "Cargo - Hazardous C", 74: "Cargo - Hazardous D",
    79: "Cargo - No Additional Info",
    80: "Tanker", 81: "Tanker - Hazardous A", 82: "Tanker - Hazardous B",
    83: "Tanker - Hazardous C", 84: "Tanker - Hazardous D",
    89: "Tanker - No Additional Info",
}

NAV_STATUS_NAMES = {
    0: "Under way using engine", 1: "At anchor", 2: "Not under command",
    3: "Restricted manoeuvrability", 4: "Constrained by draught",
    5: "Moored", 6: "Aground", 7: "Engaged in Fishing",
    8: "Under way sailing", 15: "Undefined",
}


def _safe_float(val, *, invalid=None) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (invalid is not None and f == invalid) else f
    except (TypeError, ValueError):
        return None


def _parse_ais_eta(month: int, day: int, hour: int, minute: int) -> datetime | None:
    if month == 0 and day == 0:
        return None
    try:
        now = datetime.now(tz=timezone.utc)
        year = now.year if month >= now.month else now.year + 1
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_position_report(msg: dict[str, Any]) -> dict | None:
    """
    Parse an AISStream message into a flat position dict.
    Returns None if the message is not a position report or lacks coordinates.
    """
    msg_type = msg.get("MessageType", "")
    meta = msg.get("MetaData", {})
    mmsi_raw = meta.get("MMSI") or msg.get("MMSI")

    if not mmsi_raw:
        return None

    try:
        mmsi = int(mmsi_raw)
    except (TypeError, ValueError):
        return None

    lat = _safe_float(meta.get("latitude"))
    lon = _safe_float(meta.get("longitude"))

    if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    if lat == 0.0 and lon == 0.0:
        return None

    time_str = meta.get("time_utc") or meta.get("TimeReceived")
    if time_str:
        try:
            ts = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now(tz=timezone.utc)
    else:
        ts = datetime.now(tz=timezone.utc)

    # Handle both PositionReport and ShipStaticData message shapes
    payload = msg.get("Message", {})
    pos = (
        payload.get("PositionReport")
        or payload.get("StandardClassBPositionReport")
        or payload.get("ExtendedClassBPositionReport")
        or {}
    )
    static = payload.get("ShipStaticData") or {}

    vessel_type = static.get("Type") or 0
    eta_raw = static.get("Eta") or {}

    return {
        "time":         ts,
        "mmsi":         mmsi,
        "lat":          lat,
        "lon":          lon,
        "speed":        _safe_float(pos.get("Sog"), invalid=102.3),
        "heading":      _safe_float(pos.get("TrueHeading"), invalid=511),
        "course":       _safe_float(pos.get("Cog"), invalid=360),
        "nav_status":   pos.get("NavigationalStatus"),
        "draught":      _safe_float(static.get("MaximumStaticDraught")),
        "destination":  static.get("Destination"),
        "eta_ais":      _parse_ais_eta(
            eta_raw.get("Month", 0), eta_raw.get("Day", 0),
            eta_raw.get("Hour", 0),  eta_raw.get("Minute", 0),
        ),
        # vessel metadata (upserted separately)
        "vessel": {
            "mmsi":             mmsi,
            "name":             meta.get("ShipName") or static.get("Name"),
            "imo":              static.get("ImoNumber"),
            "call_sign":        static.get("CallSign"),
            "vessel_type":      vessel_type,
            "vessel_type_name": VESSEL_TYPE_NAMES.get(vessel_type, str(vessel_type)),
            "flag":             static.get("Flag"),
        },
    }
