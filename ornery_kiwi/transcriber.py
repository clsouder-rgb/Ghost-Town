import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_whisper_model(model_name: str):
    global _whisper_model
    if _whisper_model is None:
        import whisper
        logger.info(f"Loading Whisper model: {model_name}")
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model


def _extract_audio(video_path: Path, audio_path: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"ffmpeg failed: {result.stderr}")
        return False
    return True


def transcribe_video(video_path: Path, whisper_model_name: str = "base") -> dict:
    """Transcribe a video file using Whisper. Returns transcript dict with text and segments."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = Path(tmp.name)

    try:
        logger.info(f"Extracting audio from {video_path.name}")
        if not _extract_audio(video_path, audio_path):
            return {"text": "", "segments": [], "language": "unknown", "error": "Audio extraction failed"}

        model = _get_whisper_model(whisper_model_name)
        logger.info(f"Transcribing {video_path.name}")
        result = model.transcribe(str(audio_path), verbose=False)

        return {
            "text": result.get("text", "").strip(),
            "segments": result.get("segments", []),
            "language": result.get("language", "unknown"),
            "error": None,
        }
    finally:
        if audio_path.exists():
            audio_path.unlink()


def get_video_duration(video_path: Path) -> Optional[float]:
    """Return video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    import json
    data = json.loads(result.stdout)
    try:
        return float(data["format"]["duration"])
    except (KeyError, ValueError):
        return None
