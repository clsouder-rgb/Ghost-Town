# Ornery-Kiwi

Media intelligence agent that watches a folder for video and image files, extracts content using Whisper and Claude Vision, classifies it with Claude, and outputs structured reports synced to Google Drive.

## What it does

1. **Watches** `~/Documents/ReelCapture/watch/` for new `.mp4 .mov .avi .mkv .webm` and `.jpg .png .gif .webp .bmp` files
2. **Transcribes** video audio with [OpenAI Whisper](https://github.com/openai/whisper)
3. **Extracts** text and describes images with Claude Vision
4. **Classifies** content and scores viability (1–10) via Claude API
5. **Writes** a structured `.md` report and a formatted `.docx` document to `~/Documents/ReelCapture/output/`
6. **Syncs** both files to a `ReelCapture` folder in Google Drive
7. **Moves** processed source files to `~/Documents/ReelCapture/processed/`

## Directory layout

```
~/Documents/ReelCapture/
├── watch/          ← drop media files here
├── output/         ← .md and .docx reports
├── processed/      ← source files after processing
├── credentials.json  ← Google OAuth credentials (you provide)
└── token.json        ← auto-generated after first Drive auth
```

## Prerequisites

### System packages

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### Python ≥ 3.10

```bash
pip install -r requirements.txt
```

> Whisper pulls in PyTorch (~2 GB). First run will download the selected model weights.

## Configuration

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Google Drive setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → enable **Google Drive API**
3. Create OAuth 2.0 credentials (Desktop app) → download `credentials.json`
4. Place it at `~/Documents/ReelCapture/credentials.json` (or set `GOOGLE_CREDENTIALS_PATH`)
5. On first run a browser window will open for OAuth consent — approve it once

## Usage

### Watch mode (continuous)

```bash
python main.py --watch
```

Add `--scan-existing` to also process files already in the watch folder at startup.

### Single file

```bash
python main.py --process path/to/video.mp4
python main.py --process path/to/image.png
```

### Skip Drive sync

```bash
python main.py --watch --no-drive
```

### Verbose logging

```bash
python main.py --watch -v
```

## Output format

### Markdown report

```
# <Inferred Title>
> Processed by Ornery-Kiwi | 2025-01-15 14:32:00
---
## Overview
| Field | Value |
...
## Viability Assessment
Score: 8/10 — HIGH
...
## Classification
...
## Transcript / Extracted Text
...
```

### Word document

Same structure with color-coded viability score (green/orange/red) and a formatted table.

## Viability scoring

| Score | Label | Meaning |
|-------|-------|---------|
| 1–3   | LOW   | Poor quality, misleading, or very limited appeal |
| 4–6   | MEDIUM | Average content with moderate value |
| 7–8   | HIGH  | Strong quality and clear audience fit |
| 9–10  | HIGH  | Exceptional — viral or high-impact potential |
