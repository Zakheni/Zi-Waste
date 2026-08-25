"""In-memory idempotency cache for POST /v1/invoices and /v1/payments/batch."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple

_LOCK = threading.Lock()
_STORE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_TTL_SECONDS = 24 * 3600


def get(key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    now = time.time()
    with _LOCK:
        item = _STORE.get(key)
        if not item:
            return None
        ts, payload = item
        if now - ts > _TTL_SECONDS:
            _STORE.pop(key, None)
            return None
        return payload


def put(key: Optional[str], payload: Dict[str, Any]) -> None:
    if not key:
        return
    with _LOCK:
        _STORE[key] = (time.time(), payload)
