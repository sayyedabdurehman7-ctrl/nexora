"""Optional Windows Credential Manager access for deployment credentials."""

from __future__ import annotations


def read_service_token() -> str:
    """Read the NEXORA service token without logging or exposing its value."""
    try:
        import win32cred

        credential = win32cred.CredRead("NEXORA/service-token", win32cred.CRED_TYPE_GENERIC)
        blob = credential.get("CredentialBlob", b"")
        if isinstance(blob, bytes):
            for encoding in ("utf-16-le", "utf-8"):
                try:
                    value = blob.decode(encoding).strip("\x00 \t\r\n\"'")
                    if value:
                        return value
                except UnicodeDecodeError:
                    continue
        return str(blob or "").strip().strip("\"'")
    except Exception:
        return ""
