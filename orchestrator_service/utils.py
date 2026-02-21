"""
Utilidades generales del orchestrator.

Cifrado en producción:
- Contraseñas de usuarios: bcrypt via passlib (auth_service.py)
- API keys y tokens:       Fernet via core/credentials.py (CREDENTIALS_FERNET_KEY)

Este módulo no contiene lógica de cifrado activa.
"""
