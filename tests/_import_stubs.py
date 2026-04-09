"""Module-level import stubs that allow importing main.py in test environments
where optional runtime dependencies (jwt, socketio, cryptography, etc.) are not installed.

Usage at the TOP of test files (before any main import):
    import tests._import_stubs  # noqa: F401 — side effects only

This module is idempotent — safe to import multiple times.
"""

import sys
import types
from unittest.mock import MagicMock


def _already_done() -> bool:
    return sys.modules.get("_stubs_applied") is not None


def apply() -> None:
    if _already_done():
        return

    # -------------------------------------------------------------------------
    # google.auth.crypt — loaded by google-auth (installed) but needs cryptography
    # which is NOT installed in this test environment. Stub it before google loads it.
    # -------------------------------------------------------------------------
    try:
        import google.auth as _ga  # noqa: F401 — side effect: loads google.auth

        _fake_crypt = types.ModuleType("google.auth.crypt")
        _crypt_cls = MagicMock()
        for _attr in [
            "RSASigner", "ES256Signer", "RSAVerifier", "Verifier",
            "Signer", "ES256Verifier", "EsVerifier",
        ]:
            setattr(_fake_crypt, _attr, _crypt_cls)
        sys.modules["google.auth.crypt"] = _fake_crypt

        _fake_crypt_es = types.ModuleType("google.auth.crypt.es")
        _fake_crypt_es.EsVerifier = _crypt_cls
        _fake_crypt_es.ES256Signer = _crypt_cls
        sys.modules["google.auth.crypt.es"] = _fake_crypt_es

        _fake_crypt_rsa = types.ModuleType("google.auth.crypt.rsa")
        _fake_crypt_rsa.RSASigner = _crypt_cls
        _fake_crypt_rsa.RSAVerifier = _crypt_cls
        sys.modules["google.auth.crypt.rsa"] = _fake_crypt_rsa

        _ga.crypt = _fake_crypt  # type: ignore

    except Exception:
        pass

    # -------------------------------------------------------------------------
    # google.auth.jwt — stub it entirely so it doesn't re-import crypt.es
    # -------------------------------------------------------------------------
    try:
        _fake_jwt = types.ModuleType("google.auth.jwt")
        _fake_jwt.Credentials = MagicMock()
        _fake_jwt.decode = MagicMock()
        _fake_jwt.encode = MagicMock()
        sys.modules["google.auth.jwt"] = _fake_jwt
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Other missing packages
    # -------------------------------------------------------------------------
    _MISSING = [
        "jwt",
        "socketio",
        "redis",
        "asyncpg",
        "uvicorn",
        "passlib",
        "passlib.context",
        "passlib.hash",
        "aiohttp",
        # httpx IS installed — don't stub it
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.primitives.asymmetric",
        "cryptography.hazmat.primitives.asymmetric.ec",
        "cryptography.hazmat.primitives.asymmetric.rsa",
        "cryptography.hazmat.primitives.asymmetric.utils",
        "cryptography.hazmat.primitives.serialization",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.backends",
        "cryptography.x509",
        # multipart and python_multipart ARE installed — don't stub them
        # "multipart",
        # "python_multipart",
        "email_validator",
        "dns",
        "dns.resolver",
    ]
    class _AutoAttrModule(types.ModuleType):
        """A ModuleType that returns MagicMock for any attribute access.
        Allows `from stubbed_mod import SomeClass` to succeed.
        """
        def __getattr__(self, name: str) -> object:
            if name.startswith("__"):
                raise AttributeError(name)
            val = MagicMock()
            setattr(self, name, val)
            return val

    for _mod_name in _MISSING:
        if _mod_name not in sys.modules:
            _m = _AutoAttrModule(_mod_name)
            _m.__path__ = []  # type: ignore
            _m.__spec__ = None  # type: ignore
            sys.modules[_mod_name] = _m

    # -------------------------------------------------------------------------
    # langchain.agents.AgentExecutor — moved in LangChain 1.x
    # -------------------------------------------------------------------------
    try:
        import langchain.agents as _la

        if not hasattr(_la, "AgentExecutor"):
            _la.AgentExecutor = MagicMock  # type: ignore
        if not hasattr(_la, "create_openai_tools_agent"):
            _la.create_openai_tools_agent = MagicMock()  # type: ignore
    except Exception:
        pass

    # Mark as applied
    sys.modules["_stubs_applied"] = types.ModuleType("_stubs_applied")


# Apply automatically on import
apply()
