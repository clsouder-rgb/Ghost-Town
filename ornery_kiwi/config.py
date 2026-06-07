import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_base_env = os.getenv("BASE_DIR")
BASE_DIR = Path(_base_env).expanduser() if _base_env else Path.home() / "Documents" / "ReelCapture"

# Override WATCH_DIR to point at any folder — e.g. your Desktop drop folder
_watch_env = os.getenv("WATCH_DIR")
WATCH_DIR = Path(_watch_env).expanduser() if _watch_env else BASE_DIR / "watch"

# API server binding — 127.0.0.1 for localhost-only, 0.0.0.0 for network access
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

# API authentication — optional token for write endpoints
API_TOKEN = os.getenv("API_TOKEN", "")

OUTPUT_DIR = BASE_DIR / "output"
PROCESSED_DIR = BASE_DIR / "processed"

CREDENTIALS_PATH = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", str(BASE_DIR / "credentials.json")))
TOKEN_PATH = BASE_DIR / "token.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Set AI_PROVIDER=openai to use OpenAI instead of Claude
AI_PROVIDER = os.getenv("AI_PROVIDER", "claude").lower()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Evidence Library governance
# Minimum viability score (0-10) for pipeline results to be auto-ingested.
# Raise this to reduce noise. Set to 0 to ingest everything.
EVIDENCE_MIN_SCORE = int(os.getenv("EVIDENCE_MIN_SCORE", "4"))
# Title similarity threshold (0.0-1.0). Records with title similarity above
# this value are treated as duplicates and skipped.
EVIDENCE_TITLE_SIMILARITY = float(os.getenv("EVIDENCE_TITLE_SIMILARITY", "0.85"))

GDRIVE_FOLDER_NAME = os.getenv("GDRIVE_FOLDER_NAME", "ReelCapture")
GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

VIABILITY_CATEGORIES = [
    "Tutorial / How-To",
    "Advertisement / Promotional",
    "News / Journalism",
    "Entertainment / Comedy",
    "Documentary",
    "Product Demo",
    "Educational",
    "Social / Personal",
    "Sports / Fitness",
    "Music / Performance",
    "Other",
]
