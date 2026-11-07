import hashlib
import hmac
import secrets

# No 0/O or 1/I so a User ID is easy to read out and type.
_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_USER_ID_PREFIX = "SAKHI-"
_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}


def generate_user_id() -> str:
    return _USER_ID_PREFIX + "".join(secrets.choice(_ID_ALPHABET) for _ in range(4))


def normalize_user_id(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT_PARAMS)
    return f"{salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT_PARAMS)
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
