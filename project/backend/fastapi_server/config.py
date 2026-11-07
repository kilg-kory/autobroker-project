"""Настройки backend из окружения.

Про investor здесь известно ровно одно — адрес HTTP API. Ни импортов,
ни знания о его внутреннем устройстве.
"""

import os

INVESTOR_API_URL = os.getenv("INVESTOR_API_URL", "http://127.0.0.1:8100").rstrip("/")
INVESTOR_TIMEOUT_SECONDS = float(os.getenv("INVESTOR_TIMEOUT_SECONDS", "15"))
CACHE_TTL_SECONDS = float(os.getenv("CACHE_TTL_SECONDS", "5"))

# По умолчанию прокси из окружения игнорируются: httpx умеет подхватывать
# системный прокси (в Windows — из реестра WinINET), и тогда запросы к
# локальному/внутреннему адресу уходят в прокси и падают с 503.
# Включать (INVESTOR_TRUST_ENV=1) стоит только если investor доступен
# исключительно через корпоративный прокси.
INVESTOR_TRUST_ENV = os.getenv("INVESTOR_TRUST_ENV", "0") == "1"
