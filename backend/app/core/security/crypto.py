"""AES-GCM field encryption. Stored as `v1:<nonce>:<ciphertext>` (base64). `v1` allows key rotation."""
import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


@lru_cache
def _aes(key_b64: str) -> AESGCM:
    return AESGCM(base64.b64decode(key_b64))


def _b(x: bytes) -> str:
    return base64.b64encode(x).decode()


def enc(s: str | None) -> str | None:
    if s is None:
        return None
    nonce = os.urandom(12)
    return f"v1:{_b(nonce)}:{_b(_aes(settings.field_enc_key).encrypt(nonce, s.encode(), None))}"


def dec(s: str | None) -> str | None:
    if s is None:
        return None
    v, n, c = s.split(":")
    if v != "v1":
        raise ValueError("unknown ciphertext version")
    return _aes(settings.field_enc_key).decrypt(base64.b64decode(n), base64.b64decode(c), None).decode()


def enc_map(d):
    """Encrypt every string leaf of a dict."""
    if isinstance(d, dict):
        return {k: enc_map(v) for k, v in d.items()}
    return enc(d) if isinstance(d, str) else d


def dec_map(d):
    if isinstance(d, dict):
        return {k: dec_map(v) for k, v in d.items()}
    return dec(d) if isinstance(d, str) else d


def enc_bytes(b: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + _aes(settings.field_enc_key).encrypt(nonce, b, None)


def dec_bytes(b: bytes) -> bytes:
    return _aes(settings.field_enc_key).decrypt(b[:12], b[12:], None)
