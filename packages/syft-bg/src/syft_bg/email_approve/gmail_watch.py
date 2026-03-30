"""Gmail watch management and history fetching."""

import base64
import time
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Renew watch 1 day before expiry
WATCH_RENEW_MARGIN_MS = 24 * 60 * 60 * 1000


class GmailWatcher:
    """Manages Gmail push notification watch and history fetching."""

    def __init__(self, credentials: Credentials):
        self._credentials = credentials
        self._service = build(
            "gmail", "v1", credentials=credentials, cache_discovery=False
        )
        self._watch_expiration_ms: Optional[int] = None

    def start_watch(self, topic_name: str) -> tuple[str, int]:
        """Start or renew Gmail watch on INBOX.

        Returns (history_id, expiration_ms).
        """
        body = {
            "topicName": topic_name,
            "labelIds": ["INBOX"],
            "labelFilterBehavior": "INCLUDE",
        }
        resp = self._service.users().watch(userId="me", body=body).execute()
        history_id = str(resp["historyId"])
        expiration_ms = int(resp["expiration"])
        self._watch_expiration_ms = expiration_ms
        print(
            f"[GmailWatcher] Watch active: historyId={history_id} "
            f"expiration_ms={expiration_ms}"
        )
        return history_id, expiration_ms

    def renew_if_needed(self, topic_name: str) -> Optional[tuple[str, int]]:
        """Renew watch if close to expiry. Returns new (history_id, expiration) or None."""
        if self._watch_expiration_ms is None:
            return self.start_watch(topic_name)

        now_ms = int(time.time() * 1000)
        if now_ms >= self._watch_expiration_ms - WATCH_RENEW_MARGIN_MS:
            print("[GmailWatcher] Watch nearing expiration, renewing.")
            return self.start_watch(topic_name)

        return None

    def list_history_message_ids(self, start_history_id: str) -> tuple[set[str], str]:
        """Fetch message IDs added since start_history_id.

        Returns (message_ids, newest_history_id).
        """
        page_token = None
        message_ids: set[str] = set()
        newest_history_id = start_history_id

        while True:
            resp = (
                self._service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                    pageToken=page_token,
                )
                .execute()
            )

            if "historyId" in resp:
                newest_history_id = str(resp["historyId"])

            for item in resp.get("history", []):
                for added in item.get("messagesAdded", []):
                    msg = added.get("message", {})
                    mid = msg.get("id")
                    if mid:
                        message_ids.add(mid)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return message_ids, newest_history_id

    def get_message(self, msg_id: str) -> dict:
        """Fetch a full message by ID."""
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )


def extract_reply_text(msg: dict) -> Optional[str]:
    """Extract the reply text from a Gmail message, stripping quoted content."""
    payload = msg.get("payload", {})
    text = _extract_text_plain(payload)
    if not text:
        return None
    return _strip_quoted_reply(text)


def get_thread_id(msg: dict) -> Optional[str]:
    """Get the thread ID from a message."""
    return msg.get("threadId")


def get_header(msg: dict, name: str) -> Optional[str]:
    """Get a header value from a message."""
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _extract_text_plain(payload: dict) -> Optional[str]:
    """Recursively extract text/plain content from message payload."""
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    if mime_type == "text/plain" and data:
        return _decode_base64url(data)

    for part in payload.get("parts", []):
        result = _extract_text_plain(part)
        if result:
            return result

    return None


def _decode_base64url(data: str) -> str:
    """Decode base64url-encoded string."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")


def _strip_quoted_reply(text: str) -> str:
    """Strip quoted reply text, keeping only the new content."""
    lines = text.split("\n")
    result = []
    for line in lines:
        # Stop at common quote markers
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if stripped.startswith("On ") and stripped.endswith("wrote:"):
            break
        if stripped.startswith("---------- Forwarded message"):
            break
        result.append(line)

    return "\n".join(result).strip()
