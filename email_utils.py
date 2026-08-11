"""Email file / raw-message parsing helpers for PhishShield."""
from __future__ import annotations

import email
import re
from email import policy
from email.header import decode_header, make_header
from email.utils import parseaddr
from typing import Any, Dict, Optional


URGENT_PHRASES = [
    "urgent",
    "immediate",
    "action required",
    "verify now",
    "security alert",
    "account suspended",
    "password expired",
    "click here",
    "limited time",
    "offer expires",
]


def _decode_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _domain_from_address(address: str) -> str:
    _, addr = parseaddr(address or "")
    if "@" in addr:
        return addr.split("@", 1)[1].strip().lower().rstrip(">")
    match = re.search(r"@([\w.-]+\.\w{2,})", address or "", re.IGNORECASE)
    return match.group(1).lower() if match else ""


def _count_links(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"https?://\S+|www\.\S+", text, re.IGNORECASE))


def _has_urgent_keywords(text: str) -> int:
    lowered = (text or "").lower()
    return int(any(phrase in lowered for phrase in URGENT_PHRASES))


def _extract_body_from_message(msg: email.message.Message) -> str:
    """Prefer plain text; fall back to HTML stripped of tags lightly."""
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disposition:
                continue
            try:
                payload = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        payload = payload.decode(charset, errors="replace")
                    except Exception:
                        payload = payload.decode("utf-8", errors="replace")
            if not isinstance(payload, str):
                continue
            if content_type == "text/plain":
                plain_parts.append(payload)
            elif content_type == "text/html":
                html_parts.append(payload)
    else:
        try:
            payload = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                charset = msg.get_content_charset() or "utf-8"
                payload = payload.decode(charset, errors="replace")
        if isinstance(payload, str):
            if msg.get_content_type() == "text/html":
                html_parts.append(payload)
            else:
                plain_parts.append(payload)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        # Keep HTML so BeautifulSoup link counting still works server-side
        return "\n".join(html_parts).strip()
    return ""


def _message_has_attachment(msg: email.message.Message) -> int:
    if not msg.is_multipart():
        return 0
    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", "")).lower()
        if "attachment" in disposition:
            return 1
        filename = part.get_filename()
        if filename:
            return 1
    return 0


def parse_eml_bytes(raw: bytes) -> Dict[str, Any]:
    msg = email.message_from_bytes(raw, policy=policy.default)
    subject = _decode_header_value(msg.get("Subject"))
    from_header = _decode_header_value(msg.get("From"))
    body = _extract_body_from_message(msg)
    sender_domain = _domain_from_address(from_header)
    combined = f"{subject}\n{body}"
    return {
        "email_text": body,
        "subject": subject,
        "from": from_header,
        "sender_domain": sender_domain,
        "has_attachment": _message_has_attachment(msg),
        "urgent_keywords": _has_urgent_keywords(combined),
        "links_count": _count_links(body),
        "format": "eml",
    }


def parse_msg_bytes(raw: bytes) -> Dict[str, Any]:
    try:
        import extract_msg  # type: ignore
    except ImportError as exc:
        raise ValueError(
            "Outlook .msg support requires the extract-msg package. "
            "Install it or export the email as .eml."
        ) from exc

    import tempfile
    import os

    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        msg = extract_msg.Message(path)
        try:
            subject = msg.subject or ""
            body = msg.body or msg.htmlBody or ""
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
            from_header = msg.sender or msg.senderEmail or ""
            sender_domain = _domain_from_address(from_header)
            attachments = list(msg.attachments) if msg.attachments else []
            combined = f"{subject}\n{body}"
            return {
                "email_text": body,
                "subject": subject,
                "from": from_header,
                "sender_domain": sender_domain,
                "has_attachment": int(len(attachments) > 0),
                "urgent_keywords": _has_urgent_keywords(combined),
                "links_count": _count_links(body),
                "format": "msg",
            }
        finally:
            msg.close()
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def parse_plain_text(text: str) -> Dict[str, Any]:
    subject = ""
    from_header = ""
    body = text

    subject_match = re.search(r"^Subject:\s*(.*)$", text, re.MULTILINE | re.IGNORECASE)
    if subject_match:
        subject = subject_match.group(1).strip()

    from_match = re.search(r"^From:\s*(.*)$", text, re.MULTILINE | re.IGNORECASE)
    if from_match:
        from_header = from_match.group(1).strip()

    # Split headers from body when a blank line separator exists
    parts = re.split(r"\r?\n\r?\n", text, maxsplit=1)
    if len(parts) == 2 and re.search(r"^(From|Subject|To|Date|MIME-Version):", parts[0], re.I | re.M):
        body = parts[1]

    sender_domain = _domain_from_address(from_header)
    combined = f"{subject}\n{body}"
    return {
        "email_text": body.strip(),
        "subject": subject,
        "from": from_header,
        "sender_domain": sender_domain,
        "has_attachment": int("content-disposition: attachment" in text.lower()),
        "urgent_keywords": _has_urgent_keywords(combined),
        "links_count": _count_links(body),
        "format": "txt",
    }


def parse_email_file(filename: str, raw: bytes) -> Dict[str, Any]:
    name = (filename or "").lower()
    if name.endswith(".msg"):
        return parse_msg_bytes(raw)
    if name.endswith(".eml"):
        return parse_eml_bytes(raw)
    # Try RFC822 first; fall back to plain text
    try:
        parsed = parse_eml_bytes(raw)
        if parsed.get("email_text") or parsed.get("subject"):
            return parsed
    except Exception:
        pass
    text = raw.decode("utf-8", errors="replace")
    return parse_plain_text(text)
