from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

APP_NAME = "DroneGuard AI"
APP_VERSION = "2.0.0"

DB_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "storage" / "droneguard.db"))
FRAME_STORAGE = ROOT / "storage" / "frames"
LOG_DIR = ROOT / "storage" / "logs"
SAMPLE_MEDIA_DIR = ROOT / "sample_media"
REPORTS_DIR = ROOT / "reports"

# Security & safety thresholds
NIGHT_START_HOUR = int(os.getenv("NIGHT_START_HOUR", "0"))
NIGHT_END_HOUR = int(os.getenv("NIGHT_END_HOUR", "5"))
LOW_BATTERY_THRESHOLD = int(os.getenv("LOW_BATTERY_THRESHOLD", "20"))
CRITICAL_BATTERY_THRESHOLD = int(os.getenv("CRITICAL_BATTERY_THRESHOLD", "15"))
MAX_ALTITUDE_METERS = float(os.getenv("MAX_ALTITUDE_METERS", "60"))
LOITERING_SECONDS = int(os.getenv("LOITERING_SECONDS", "120"))
LOITERING_MIN_OBSERVATIONS = int(os.getenv("LOITERING_MIN_OBSERVATIONS", "2"))
DUPLICATE_ALERT_WINDOW_SECONDS = int(os.getenv("DUPLICATE_ALERT_WINDOW_SECONDS", "300"))
RESTRICTED_ZONES = [
    z.strip()
    for z in os.getenv(
        "RESTRICTED_ZONES",
        "Restricted Zone,Restricted Area,Server Perimeter,Loading Dock B",
    ).split(",")
    if z.strip()
]

# Frame extraction defaults
DEFAULT_FRAME_INTERVAL_SECONDS = float(os.getenv("DEFAULT_FRAME_INTERVAL_SECONDS", "2.0"))
MAX_VIDEO_FRAMES = int(os.getenv("MAX_VIDEO_FRAMES", "60"))

# Vision-Language Model configuration
VLM_MODE = os.getenv("VLM_MODE", "simulation").lower()
VLM_PROVIDER = os.getenv("VLM_PROVIDER", "auto").lower()
VLM_TIMEOUT_SECONDS = int(os.getenv("VLM_TIMEOUT_SECONDS", "30"))
VLM_MAX_RETRIES = int(os.getenv("VLM_MAX_RETRIES", "2"))

# LLM orchestration configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_VLM_MODEL = os.getenv("OLLAMA_VLM_MODEL", "llava")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")

for directory in (DB_PATH.parent, FRAME_STORAGE, LOG_DIR, SAMPLE_MEDIA_DIR, REPORTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
