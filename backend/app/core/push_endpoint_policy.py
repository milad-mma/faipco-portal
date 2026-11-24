"""Web Push endpoint policy. Never send VAPID or encrypted payloads to arbitrary URLs.

Known browser vendor hosts are allowed by exact hostname or vendor-owned suffix,
not substring. Extend deliberately only after verifying a new browser provider.
Unsubscribe need not pass this policy (a legacy bad endpoint must be removable).
"""
import base64
import re
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
import requests

MAX_ENDPOINT_LENGTH = 4096
EXACT_HOSTS = frozenset({
    "fcm.googleapis.com", "android.googleapis.com", "updates.push.services.mozilla.com",
    "web.push.apple.com", "push.services.mozilla.com", "notify.windows.com", "wns.windows.com",
})
SUFFIX_HOSTS = (".push.apple.com", ".push.services.mozilla.com", ".notify.windows.com", ".wns.windows.com")
_HOST_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", re.ASCII)
_KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]+={0,2}", re.ASCII)


def valid_push_endpoint(endpoint: str) -> bool:
    if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= MAX_ENDPOINT_LENGTH:
        return False
    if any(ord(ch) <= 32 or ord(ch) >= 127 for ch in endpoint) or "\\" in endpoint:
        return False
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443) or parsed.fragment or not parsed.path.startswith("/")
                or parsed.path == "/" or not _HOST_PATTERN.fullmatch(host)):
            return False
        # Reject ambiguous authorities, empty labels, percent encodings and trailing dots.
        if parsed.netloc.lower() not in (host, host + ":443") or ".." in host:
            return False
        return host in EXACT_HOSTS or any(host.endswith(suffix) for suffix in SUFFIX_HOSTS)
    except (ValueError, UnicodeError):
        return False


def decode_key(value: str, size: int) -> bytes:
    if not _KEY_PATTERN.fullmatch(value):
        raise ValueError("Invalid Web Push encryption key")
    raw = base64.b64decode(value.rstrip("=") + "=" * (-len(value.rstrip("=")) % 4),
                           altchars=b"-_", validate=True)
    if len(raw) != size or base64.urlsafe_b64encode(raw).decode().rstrip("=") != value.rstrip("="):
        raise ValueError("Invalid Web Push encryption key length")
    return raw


def validate_public_key(value: str) -> str:
    raw = decode_key(value, 65)
    if raw[0] != 4:
        raise ValueError("Invalid Web Push public key")
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    return value


def validate_auth_key(value: str) -> str:
    decode_key(value, 16)
    return value


class PushHTTPSession(requests.Session):
    """pywebpush's requests_session injection; do not follow provider redirects."""
    def request(self, method, url, **kwargs):
        if not valid_push_endpoint(url):
            raise ValueError("Unapproved Web Push provider")
        kwargs["allow_redirects"] = False
        kwargs["verify"] = True
        return super().request(method, url, **kwargs)
