from scripts.scalability_test import run_benchmark


def test_scalability_1000_frames_benchmark():
    metrics = run_benchmark(1000)
    assert metrics["frames"] == 1000
    assert metrics["matched_blue_trucks"] == 100
    assert metrics["query_object_color_ms"] < 1000
