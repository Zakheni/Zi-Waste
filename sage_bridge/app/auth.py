"""API key authentication. Header x-api-key only — no query-string keys."""

from typing import Optional

from fastapi import Header, HTTPException

from .config import API_KEY


def require_key(x_api_key: Optional[str] = Header(default=None, alias="x-api-key")):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY missing from environment")
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
