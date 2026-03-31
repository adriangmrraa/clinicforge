"""Sentry error tracking configuration with PII scrubbing."""
import os
import re
import logging

logger = logging.getLogger(__name__)

# Pattern to match phone numbers (international format)
_PHONE_PATTERN = re.compile(r'\+?\d{10,15}')
# Pattern to match email addresses
_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Headers that must be redacted
_SENSITIVE_HEADERS = {'authorization', 'x-admin-token', 'cookie'}


def _scrub_pii(event, hint):
    """Remove PII from Sentry events before sending."""
    # Scrub request headers
    request = event.get('request', {})
    headers = request.get('headers', {})
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in _SENSITIVE_HEADERS:
                headers[key] = '[REDACTED]'

    # Scrub phone numbers and emails from extra data
    def scrub_value(val):
        if isinstance(val, str):
            val = _PHONE_PATTERN.sub('[REDACTED_PHONE]', val)
            val = _EMAIL_PATTERN.sub('[REDACTED_EMAIL]', val)
        return val

    def scrub_dict(d):
        if isinstance(d, dict):
            return {k: scrub_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [scrub_dict(item) for item in d]
        else:
            return scrub_value(d)

    if 'extra' in event:
        event['extra'] = scrub_dict(event['extra'])

    # Scrub breadcrumbs
    for breadcrumb in event.get('breadcrumbs', {}).get('values', []):
        if 'message' in breadcrumb:
            breadcrumb['message'] = scrub_value(breadcrumb['message'])
        if 'data' in breadcrumb:
            breadcrumb['data'] = scrub_dict(breadcrumb['data'])

    return event


def init_sentry():
    """Initialize Sentry SDK. No-op if SENTRY_DSN is not set."""
    dsn = os.getenv('SENTRY_DSN', '')
    if not dsn:
        logger.info("Sentry disabled (SENTRY_DSN not set)")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.asyncio import AsyncioIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            before_send=_scrub_pii,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                AsyncioIntegration(),
            ],
            # Only capture 5xx errors, not 4xx
            ignore_errors=[],
            send_default_pii=False,
        )
        logger.info(f"Sentry initialized (env={os.getenv('SENTRY_ENVIRONMENT', 'production')})")
    except ImportError:
        logger.warning("sentry-sdk not installed — Sentry disabled")
    except Exception as e:
        logger.error(f"Sentry initialization failed: {e}")
