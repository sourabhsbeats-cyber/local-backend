"""Fernet encryption for vendor portal passwords (at-rest). Key derived from SECRET_KEY."""
import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    raw = settings.SECRET_KEY.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt_password(plain: str) -> str:
    if plain is None:
        plain = ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_password(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
