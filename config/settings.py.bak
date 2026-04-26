# config/settings.py
# VoidSend - Encrypted local config storage

import json
import os
import base64
from pathlib import Path
from typing import Optional
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken

CONFIG_DIR = Path.home() / ".voidsend"
CONFIG_FILE = CONFIG_DIR / "config.enc"
SALT_FILE = CONFIG_DIR / "salt.bin"


def _get_or_create_salt() -> bytes:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = os.urandom(16)
    SALT_FILE.write_bytes(salt)
    return salt


def _derive_key(passphrase: str) -> bytes:
    salt = _get_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def save_config(data: dict, passphrase: str) -> None:
    """Encrypt and save config dict to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    key = _derive_key(passphrase)
    f = Fernet(key)
    encrypted = f.encrypt(json.dumps(data).encode())
    CONFIG_FILE.write_bytes(encrypted)


def load_config(passphrase: str) -> Optional[dict]:
    """Decrypt and load config. Returns None if passphrase wrong or no config."""
    if not CONFIG_FILE.exists():
        return None
    key = _derive_key(passphrase)
    f = Fernet(key)
    try:
        decrypted = f.decrypt(CONFIG_FILE.read_bytes())
        return json.loads(decrypted.decode())
    except (InvalidToken, json.JSONDecodeError):
        return None


def config_exists() -> bool:
    return CONFIG_FILE.exists()


def delete_config() -> None:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    if SALT_FILE.exists():
        SALT_FILE.unlink()


def get_config_path() -> Path:
    return CONFIG_FILE