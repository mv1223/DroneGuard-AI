from datetime import datetime, timedelta
import random
from .schemas import Telemetry

def generate_telemetry(timestamp: str | None = None, location: str = "Main Gate",
                       battery: float = 85, altitude: float = 25,
                       drone_id: str = "DRONE-001") -> Telemetry:
    """Generate one deterministic-shape telemetry record for the simulator."""
    ts = timestamp or datetime.now().replace(microsecond=0).isoformat()
    if not 0 <= battery <= 100:
        raise ValueError("battery_percentage must be between 0 and 100")
    if altitude < 0:
        raise ValueError("altitude cannot be negative")
    return Telemetry(ts, drone_id, 17.385 + random.uniform(-0.001, 0.001),
                     78.486 + random.uniform(-0.001, 0.001), altitude,
                     battery, round(random.uniform(0, 4), 2), location)

def validate_telemetry(record: dict) -> None:
    required = {"timestamp", "drone_id", "latitude", "longitude", "altitude",
                "battery_percentage", "speed", "location_name", "flight_status"}
    missing = required - set(record)
    if missing:
        raise ValueError(f"Missing telemetry fields: {', '.join(sorted(missing))}")
    datetime.fromisoformat(record["timestamp"])
    if not 0 <= float(record["battery_percentage"]) <= 100:
        raise ValueError("Battery must be between 0 and 100")
    if float(record["altitude"]) < 0:
        raise ValueError("Altitude cannot be negative")

def sample_telemetry() -> list[dict]:
    base = datetime(2026, 11, 27, 0, 0)
    rows = [
        ("Main Gate", 85, 25), ("Parking Area", 84, 24),
        ("Main Gate", 83, 25), ("Restricted Zone", 82, 28),
        ("Garage", 81, 23), ("Main Gate", 18, 25),
    ]
    return [generate_telemetry((base + timedelta(minutes=i*2)).isoformat(),
                               loc, bat, alt).to_dict()
            for i, (loc, bat, alt) in enumerate(rows)]
