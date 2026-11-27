from scripts.generate_sample_data import load_demo

def test_demo_pipeline_populates_database(tmp_path):
    repo = load_demo(reset=True, db_path=tmp_path/"integration.db")
    counts = repo.counts()
    assert counts["frames"] == 6
    assert counts["detections"] >= 4
    assert counts["alerts"] >= 1
