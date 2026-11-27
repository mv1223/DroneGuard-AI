from scripts.generate_sample_data import load_demo
repo = load_demo(reset=True)
print("Demo loaded:", repo.counts())
