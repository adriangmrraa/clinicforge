"""Resolución de proveedor para los servicios AUXILIARES de IA.

Enruta embeddings, transcripción de audio (Whisper) y visión hacia OpenRouter
o hacia OpenAI directo, usando el MISMO principio que el bot conversacional
(main._resolve_provider): si el NOMBRE del modelo lleva un prefijo 'proveedor/'
(ej. 'openai/whisper-1', 'openai/text-embedding-3-small'), la llamada va por
OpenRouter (OPENROUTER_API_KEY + base_url de OpenRouter). Si NO lleva '/', va por
OpenAI directo (comportamiento original, 100% intacto).

REVERSIBLE POR VARIABLE DE ENTORNO. Para migrar a OpenRouter poné el modelo con
prefijo (EMBEDDING_MODEL / WHISPER_MODEL / VISION_MODEL = 'openai/...'); para
volver a OpenAI, sacá el prefijo (o borrá la variable). Por defecto (sin '/'),
NADA cambia — todo sigue en OpenAI como hoy.
"""
import os

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Cache de clients AsyncOpenAI por base_url (evita reconstruir en cada llamada).
_async_clients: dict = {}


def resolve_aux_provider(model: str):
    """Devuelve (api_key, base_url, provider) para una llamada auxiliar.

    - modelo con '/' y OPENROUTER_API_KEY presente → OpenRouter.
    - si no → OpenAI directo.
    base_url siempre explícito (sirve tanto para el SDK como para POST httpx crudo:
    f"{base_url}/audio/transcriptions", f"{base_url}/embeddings", etc.).
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if "/" in (model or "") and openrouter_key:
        return openrouter_key, OPENROUTER_BASE_URL, "openrouter"
    return os.getenv("OPENAI_API_KEY", ""), OPENAI_BASE_URL, "openai"


def get_aux_async_client(model: str):
    """AsyncOpenAI client (cacheado por base_url) ruteado según el modelo."""
    from openai import AsyncOpenAI

    api_key, base_url, _provider = resolve_aux_provider(model)
    client = _async_clients.get(base_url)
    if client is None:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        _async_clients[base_url] = client
    return client


def track_name(model: str) -> str:
    """Nombre 'pelado' del modelo para el tracker de costos (saca el prefijo 'proveedor/')."""
    return (model or "").split("/")[-1]
