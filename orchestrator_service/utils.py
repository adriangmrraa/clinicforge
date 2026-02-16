import os
import base64
from itertools import cycle

# Simple Encryption Helper (Standard Lib only)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "agente-js-secret-key-2024")

def encrypt_password(password: str) -> str:
    """Simple XOR + Base64 encryption."""
    if not password: return ""
    xored = ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(password, cycle(ENCRYPTION_KEY)))
    return base64.b64encode(xored.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    """Simple XOR + Base64 decryption."""
    if not encrypted: return ""
    try:
        decoded = base64.b64decode(encrypted).decode()
        return ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(decoded, cycle(ENCRYPTION_KEY)))
    except:
        return ""
