from pathlib import Path
import json

from database.repository import Repository
from core.pipeline import SecurityPipeline

ROOT = Path(__file__).resolve().parents[1]


def load_demo(reset: bool = False, db_path=None) -> Repository:
    repo = Repository(db_path)
    if reset:
        repo.clear_all()
    frames = json.loads((ROOT / "data" / "sample_frames.json").read_text(encoding="utf-8"))
    telemetry = json.loads((ROOT / "data" / "sample_telemetry.json").read_text(encoding="utf-8"))
    pipeline = SecurityPipeline(repo)

    telemetry_ids: dict[str, int] = {}
    for row in telemetry:
        tid, _ = pipeline.ingest_telemetry(row)
        telemetry_ids[row["timestamp"]] = tid

    for item in frames:
        tid = telemetry_ids.get(item["timestamp"])
        pipeline.ingest_description(item, telemetry_id=tid)
    return repo


if __name__ == "__main__":
    repo = load_demo(reset=True)
    print("Demo data loaded:", repo.counts())
