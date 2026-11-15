from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Deque

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 200
EMAIL_RE = re.compile(r"^[^@\s]{1,120}@[^@\s]{1,180}\.[^@\s]{2,}$")
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def now_s() -> int:
    return int(time.time())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return "scrypt$16384$8$1${}${}".format(
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(derived).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$", 5)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(hash_b64.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def validate_password(password: str) -> str | None:
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"密码至少需要 {PASSWORD_MIN_LENGTH} 个字符"
    if len(password) > PASSWORD_MAX_LENGTH:
        return "密码过长"
    if password.strip() != password:
        return "密码首尾不能包含空白字符"
    return None


def validate_email(email: str) -> str | None:
    if not EMAIL_RE.match(email.strip()):
        return "请输入有效的邮箱地址"
    return None


def new_session_token() -> str:
    return secrets.token_urlsafe(40)


def new_api_key() -> tuple[str, str, str, str]:
    """Return (secret, prefix, last_four, hash)."""
    secret = "fd_live_" + secrets.token_urlsafe(32)
    return secret, secret[:12], secret[-4:], hash_token(secret)


def mask_api_key(prefix: str, last_four: str) -> str:
    return f"{prefix}…{last_four}"


def bearer_token(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


class RateLimiter:
    """Small in-process sliding window limiter.

    This is intentionally simple: the app is single-node and private-use. It exists
    to blunt accidental loops and password guessing, not as a security boundary.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


def make_csrf_token(secret: str, session_token: str) -> str:
    return hmac.new(secret.encode(), session_token.encode(), hashlib.sha256).hexdigest()
