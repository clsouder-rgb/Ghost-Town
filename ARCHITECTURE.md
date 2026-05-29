# Ornery-Kiwi — Architecture

This document maps every connection point between the iOS app, the Share Extension, and the Python API server.

---

## System diagram

```
┌─────────────────────────────────┐         ┌────────────────────────────────────┐
│          iOS Device             │         │         Mac mini (server)          │
│                                 │         │                                    │
│  ┌────────────────────┐         │  HTTP   │  ┌──────────────────────────────┐  │
│  │  OrneryKiwi.app    │  ──────────────── │  │  serve.py (port 8000)        │  │
│  │  (SwiftUI)         │         │         │  │  FastAPI + uvicorn           │  │
│  │                    │         │         │  └──────────┬───────────────────┘  │
│  │  SettingsView ─────┼─ URL ──────────── │             │                      │
│  │  APIClient    ─────┼─ POST /ingest ─── │  ┌──────────▼───────────────────┐  │
│  └────────────────────┘         │         │  │  ornery_kiwi/pipeline.py     │  │
│                                 │         │  │  Whisper · Claude · Drive    │  │
│  ┌────────────────────┐         │         │  └──────────────────────────────┘  │
│  │  OrneryKiwiShare   │  ──────────────── │                                    │
│  │  (Share Extension) │  POST /ingest     │  ~/Documents/ReelCapture/          │
│  │                    │         │         │  ├── watch/                         │
│  └────────────────────┘         │         │  ├── output/  (.md + .docx)        │
│                                 │         │  └── processed/                    │
│  ╔══════════════════════╗       │         └────────────────────────────────────┘
│  ║  App Group           ║       │
│  ║  group.com.ornery-   ║       │
│  ║  kiwi.shared         ║       │
│  ║  (shared UserDefaults║       │
│  ║   suite)             ║       │
│  ╚══════════════════════╝       │
└─────────────────────────────────┘
```

---

## API endpoints

All endpoints are on `http://<server>:8000`.

### `GET /health`

Health check. No authentication.

**Response `200`**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "watch_dir": "/Users/you/Documents/ReelCapture/watch",
  "active_jobs": 0,
  "total_jobs": 12
}
```

**iOS usage:** `SettingsView` calls this via `APIClient.shared.health()` when the user taps "Check Connection". Also useful for reachability probing before submitting a share.

---

### `POST /ingest`

Queue a media item for processing. Accepts either a public URL or a local file path (local to the server).

**Request body**
```json
{ "url": "https://example.com/clip.mp4" }
```
or
```json
{ "file_path": "/Users/you/Downloads/photo.png" }
```

At least one field is required. Providing both is a validation error.

**Response `202 Accepted`**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "queued",
  "message": "Job queued. Poll /ingest/status/3fa8... for updates."
}
```

**iOS usage:** `APIClient.shared.ingest(url:filePath:)`. The Share Extension will call this with the URL of the shared item (see §Share Extension Implementation Checklist).

---

### `GET /ingest/status/{job_id}`

Poll the status of a job.

**Response `200`**
```json
{
  "job_id": "3fa85f64-...",
  "status": "complete",
  "source": "https://example.com/clip.mp4",
  "created_at": "2025-01-15T14:32:00Z",
  "updated_at": "2025-01-15T14:33:12Z",
  "result": {
    "file": "/Users/you/Documents/ReelCapture/watch/clip.mp4",
    "type": "video",
    "md_path": "/Users/you/Documents/ReelCapture/output/clip_20250115_143300.md",
    "docx_path": "/Users/you/Documents/ReelCapture/output/clip_20250115_143300.docx",
    "viability_score": 8,
    "drive_urls": {
      "clip_20250115_143300.md": "https://drive.google.com/file/d/...",
      "clip_20250115_143300.docx": "https://drive.google.com/file/d/..."
    }
  },
  "error": null
}
```

**Status lifecycle:** `queued` → `processing` → `complete` | `failed`

**iOS usage:** `APIClient.shared.jobStatus(jobId:)`. Poll with a timer or use exponential backoff. `JobStatusValue.isTerminal` returns `true` once polling can stop.

**Swift types:** `JobStatusResponse`, `JobResult`, `JobStatusValue` in `ios/OrneryKiwi/Network/Models.swift`.

---

## iOS ↔ API — connection points by file

| iOS file | What it does | API surface |
|----------|-------------|-------------|
| `Settings/SettingsStore.swift` | Persists `serverURL` to App Group suite | None — controls `APIClient.baseURL` |
| `Settings/SettingsView.swift` | URL text field + "Check Connection" button | `GET /health` |
| `Network/APIClient.swift` | All HTTP calls | `POST /ingest`, `GET /ingest/status/{id}`, `GET /health` |
| `Network/Models.swift` | Codable types mirroring API JSON schemas | All endpoints |
| `ShareExtension/ShareViewController.swift` | Reads `serverURL` from shared defaults | `POST /ingest` (planned) |

---

## Shared settings — App Group

Both the main app and the Share Extension read/write a single key through a shared `UserDefaults` suite:

| Key | Default | Written by | Read by |
|-----|---------|-----------|--------|
| `serverURL` | `http://localhost:8000` | `SettingsStore` (main app) | `APIClient`, `ShareViewController` |

**Suite name:** `group.com.ornery-kiwi.shared`  
Defined in:
- `ios/OrneryKiwi/OrneryKiwi.entitlements`
- `ios/ShareExtension/ShareExtension.entitlements`
- `ios/OrneryKiwi/Settings/SettingsStore.swift` (static constant `appGroupSuite`)
- `ios/ShareExtension/ShareViewController.swift` (mirrored static constant)

Changing `serverURL` in Settings is immediately visible to the Share Extension on next invocation — no IPC required.

---

## Job lifecycle

```
Client               FastAPI              background thread       pipeline
  │                    │                       │                     │
  │  POST /ingest ────►│                       │                     │
  │                    │  job_store.create()   │                     │
  │                    │  run_in_executor() ──►│                     │
  │◄─── 202 queued ────│                       │                     │
  │                    │                       │  update(processing) │
  │                    │                       │  process_file() ───►│
  │  GET /status ─────►│  job_store.get()      │                     │ Whisper
  │◄─── processing ────│                       │                     │ Claude Vision
  │                    │                       │                     │ Classifier
  │                    │                       │◄── result ──────────│ Drive sync
  │                    │                       │  update(complete)   │
  │  GET /status ─────►│  job_store.get()      │                     │
  │◄─── complete ──────│                       │                     │
```

---

## Share Extension — implementation checklist

The extension is currently scaffolded but non-functional. To activate it:

- [ ] **Network entitlement** — Add `com.apple.developer.networking.wifi-info` or enable outbound networking in the extension's sandbox (required for `URLSession` calls from an extension).
- [ ] **Item extraction** — Implement `ShareViewController._extractURL()` for each UTType: `UTType.url`, `UTType.fileURL`, `UTType.image`, `UTType.movie`.
- [ ] **API call** — Call `_submitToAPI(urlString:)` with the extracted item. For binary items (images/video), consider uploading via multipart if the server adds a `POST /ingest/upload` endpoint, or writing to a shared container and sending the path.
- [ ] **Feedback UI** — Show a progress indicator while `POST /ingest` is in flight; on success show the `job_id` and optionally poll for the final viability score.
- [ ] **Error handling** — Surface network errors (server unreachable, timeout) with a "Go to Settings" action that deep-links into the main app.
- [ ] **Polling (optional)** — After submitting, poll `GET /ingest/status/{job_id}` with exponential backoff (2 s, 4 s, 8 s…) capped at 30 s, then show the viability score inline.

---

## Python API — file map

```
ornery_kiwi/api/
├── app.py           FastAPI app, CORS middleware, router registration
├── models.py        Pydantic request/response schemas
├── job_store.py     Thread-safe in-memory job registry (JobStore singleton)
└── routes/
    ├── health.py    GET /health
    └── ingest.py    POST /ingest, GET /ingest/status/{job_id},
                     ThreadPoolExecutor worker, URL downloader
```

---

## Server deployment — Mac mini

`serve.py` starts both the API server and the folder watcher in one process:

```
┌─────────────────────────────────────────────────────┐
│ python serve.py                                     │
│                                                     │
│  Main thread: uvicorn (FastAPI, port 8000)          │
│  Daemon thread: OrneryKiwiWatcher (watchdog)        │
│  ThreadPoolExecutor: ingest workers (max 4)         │
└─────────────────────────────────────────────────────┘
```

Auto-start via launchd:
```bash
./install_launchd.sh          # installs ~/Library/LaunchAgents/com.ornery-kiwi.agent.plist
```

Logs: `~/Library/Logs/ornery-kiwi.log` and `ornery-kiwi.err`.

---

## Configuration

All configuration flows through `ornery_kiwi/config.py` and a `.env` file:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | — | Required. Claude API key. |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model used for Vision + classification |
| `WHISPER_MODEL` | `base` | Whisper model size |
| `GOOGLE_CREDENTIALS_PATH` | `~/Documents/ReelCapture/credentials.json` | OAuth2 creds for Drive |
| `GDRIVE_FOLDER_NAME` | `ReelCapture` | Drive folder name |

iOS `serverURL` default: `http://localhost:8000` (assumes local network access to Mac mini).
For remote access, use Tailscale, ngrok, or a reverse proxy and update the URL in Settings.
