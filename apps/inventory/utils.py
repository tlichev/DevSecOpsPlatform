import base64
import hashlib
import logging

logger = logging.getLogger(__name__)


def _get_fernet():
    from cryptography.fernet import Fernet
    from django.conf import settings
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if key:
        raw = key.encode() if isinstance(key, str) else key
    else:
        # Derive a stable key from SECRET_KEY for development.
        # Replace FIELD_ENCRYPTION_KEY in .env for production.
        secret = settings.SECRET_KEY.encode()
        raw = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(raw)


def encrypt_password(plaintext: str) -> str:
    if not plaintext:
        return ''
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception:
        logger.exception('Password encryption failed')
        return ''


def decrypt_password(ciphertext: str) -> str:
    if not ciphertext:
        return ''
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        # Not encrypted (e.g. loaded from fixture as plain text)
        return ciphertext
