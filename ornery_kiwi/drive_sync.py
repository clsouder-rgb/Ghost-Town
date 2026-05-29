import logging
from pathlib import Path
from typing import Optional

from .config import CREDENTIALS_PATH, TOKEN_PATH, GDRIVE_FOLDER_NAME, GDRIVE_SCOPES

logger = logging.getLogger(__name__)

_MIME_MAP = {
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _build_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), GDRIVE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Google credentials not found at {CREDENTIALS_PATH}. "
                    "Download credentials.json from Google Cloud Console and place it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), GDRIVE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, folder_name: str) -> str:
    """Return Drive folder ID, creating it if it doesn't exist."""
    query = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        " and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=meta, fields="id").execute()
    logger.info(f"Created Drive folder '{folder_name}': {folder['id']}")
    return folder["id"]


def upload_file(local_path: Path, subfolder: Optional[str] = None) -> Optional[str]:
    """Upload a file to Google Drive. Returns the file URL or None on failure."""
    local_path = Path(local_path)
    if not local_path.exists():
        logger.error(f"File not found for upload: {local_path}")
        return None

    try:
        from googleapiclient.http import MediaFileUpload

        service = _build_service()
        root_id = _get_or_create_folder(service, GDRIVE_FOLDER_NAME)

        parent_id = root_id
        if subfolder:
            # Reuse or create a subfolder inside ReelCapture
            query = (
                f"name='{subfolder}' and mimeType='application/vnd.google-apps.folder'"
                f" and '{root_id}' in parents and trashed=false"
            )
            results = service.files().list(q=query, fields="files(id)").execute()
            sub_files = results.get("files", [])
            if sub_files:
                parent_id = sub_files[0]["id"]
            else:
                meta = {
                    "name": subfolder,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [root_id],
                }
                sub = service.files().create(body=meta, fields="id").execute()
                parent_id = sub["id"]

        mime_type = _MIME_MAP.get(local_path.suffix.lower(), "application/octet-stream")
        file_meta = {"name": local_path.name, "parents": [parent_id]}
        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

        uploaded = (
            service.files()
            .create(body=file_meta, media_body=media, fields="id, webViewLink")
            .execute()
        )
        url = uploaded.get("webViewLink", "")
        logger.info(f"Uploaded {local_path.name} to Drive: {url}")
        return url

    except Exception as exc:
        logger.error(f"Drive upload failed for {local_path.name}: {exc}")
        return None


def sync_report_pair(md_path: Path, docx_path: Path, subfolder: Optional[str] = None) -> dict:
    """Upload both output files and return a dict of {filename: url}."""
    results = {}
    for path in [md_path, docx_path]:
        url = upload_file(path, subfolder=subfolder)
        results[path.name] = url or "(upload failed)"
    return results
