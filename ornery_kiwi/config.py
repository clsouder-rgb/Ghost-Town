import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path.home() / "Documents" / "ReelCapture"
WATCH_DIR = BASE_DIR / "watch"
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
