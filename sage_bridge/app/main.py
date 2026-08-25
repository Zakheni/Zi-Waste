"""Sage 50 Pastel Windows bridge — FastAPI /v1 contract."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from . import idempotency
from .adapters import get_adapter
from .auth import require_key
from .config import BIND_HOST, BIND_PORT

_logger = logging.getLogger("sage_bridge")


def _configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if sys.platform != "win32":
        return
    try:
        handler = logging.handlers.NTEventLogHandler("sage_bridge")
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
    except Exception:
        _logger.warning("Windows Event Log is unavailable; file/console logging only")


_configure_logging()

app = FastAPI(
    title="Sage 50 Pastel Bridge",
    version="1.0.0",
    description="Odoo talks only to this HTTP API. Sage files/COM stay on Windows.",
)
ADAPTER = get_adapter()


def _page(items, next_cursor, has_more):
    return {"items": items, "meta": {"next_cursor": next_cursor, "has_more": has_more}}


@app.get("/health")
def health():
    return ADAPTER.health()


@app.get("/v1/customers")
def list_customers(
    _key: str = Depends(require_key),
    since: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=5000),
    q: Optional[str] = Query(None),
):
    items, nxt, more = ADAPTER.pull_customers(since, cursor, limit, q)
    return _page(items, nxt, more)


@app.put("/v1/customers/{code}")
def upsert_customer(code: str, payload: Dict[str, Any], _key: str = Depends(require_key)):
    return ADAPTER.upsert_customer(code, payload or {})


@app.get("/v1/suppliers")
def list_suppliers(
    _key: str = Depends(require_key),
    since: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=5000),
    q: Optional[str] = Query(None),
):
    items, nxt, more = ADAPTER.pull_suppliers(since, cursor, limit, q)
    return _page(items, nxt, more)


@app.get("/v1/products")
def list_products(
    _key: str = Depends(require_key),
    since: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=5000),
    q: Optional[str] = Query(None),
):
    items, nxt, more = ADAPTER.pull_products(since, cursor, limit, q)
    return _page(items, nxt, more)


@app.put("/v1/products/{code}")
def upsert_product(code: str, payload: Dict[str, Any], _key: str = Depends(require_key)):
    return ADAPTER.upsert_product(code, payload or {})


@app.get("/v1/invoices")
def list_invoices(
    _key: str = Depends(require_key),
    since: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=5000),
    doc_type: Optional[int] = Query(None),
):
    items, nxt, more = ADAPTER.pull_invoices(since, cursor, limit, doc_type)
    return _page(items, nxt, more)


@app.get("/v1/invoices/exists")
def invoice_exists(
    _key: str = Depends(require_key),
    doc_no: str = Query(...),
    doc_type: Optional[int] = Query(None),
):
    return ADAPTER.invoice_exists(doc_no, doc_type)


@app.post("/v1/invoices")
def create_invoice(
    payload: Dict[str, Any],
    _key: str = Depends(require_key),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    cached = idempotency.get(idempotency_key)
    if cached:
        return cached
    result = ADAPTER.post_invoice(payload or {}, replace=False)
    idempotency.put(idempotency_key, result)
    return result


@app.put("/v1/invoices/{doc_no:path}")
def replace_invoice(
    doc_no: str = Path(...),
    payload: Dict[str, Any] = None,
    _key: str = Depends(require_key),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    cached = idempotency.get(idempotency_key)
    if cached:
        return cached
    body = dict(payload or {})
    body["doc_no"] = doc_no
    result = ADAPTER.post_invoice(body, replace=True)
    idempotency.put(idempotency_key, result)
    return result


@app.post("/v1/payments/batch")
def create_payment_batch(
    payload: Dict[str, Any],
    _key: str = Depends(require_key),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    cached = idempotency.get(idempotency_key)
    if cached:
        return cached
    result = ADAPTER.post_receipt_batch(payload or {})
    idempotency.put(idempotency_key, result)
    return result


@app.exception_handler(HTTPException)
async def http_exc_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "detail": exc.detail})


def run():
    import uvicorn

    uvicorn.run("app.main:app", host=BIND_HOST, port=BIND_PORT, reload=False)


if __name__ == "__main__":
    run()
