import pytest
from core.telemetry import generate_telemetry, validate_telemetry

def test_generate_telemetry_valid():
    row = generate_telemetry("2026-11-27T12:00:00").to_dict()
    validate_telemetry(row)

def test_invalid_battery_rejected():
    with pytest.raises(ValueError):
        generate_telemetry(battery=101)

def test_missing_field_rejected():
    with pytest.raises(ValueError):
        validate_telemetry({"timestamp":"2026-11-27T12:00:00"})
