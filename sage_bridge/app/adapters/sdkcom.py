"""SDKCOM write path for Sage 50 Pastel Partner (32-bit COM)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

_logger = logging.getLogger(__name__)


def sdk_available(progid: str) -> bool:
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return False
    try:
        import win32com.client as win32

        win32.Dispatch(progid)
        return True
    except Exception as exc:
        _logger.info("SDKCOM Dispatch(%s) failed: %s", progid, exc)
        return False


def post_invoice_sdk(
    payload: Dict[str, Any],
    *,
    progid: str,
    company_path: str,
    username: str,
    password: str,
) -> Dict[str, Any]:
    """Post an invoice via SDKCOM. ProgID varies by Pastel year — see INSTALL.md."""
    import win32com.client as win32

    sdk = win32.Dispatch(progid)
    if company_path and hasattr(sdk, "Open"):
        sdk.Open(company_path, username or "", password or "")
    elif company_path and hasattr(sdk, "OpenCompany"):
        sdk.OpenCompany(company_path, username or "", password or "")

    doc_type = int(payload.get("document_type") or 3)
    customer = payload.get("customer_code")
    inv_date = payload.get("invoice_date")
    requested = (payload.get("doc_no") or "").strip()

    # Typical Partner SDK surface (method names differ by version).
    # Call through getattr so a missing method falls through to the adapter.
    create = getattr(sdk, "CreateInvoice", None) or getattr(sdk, "InvoiceAdd", None)
    if not callable(create):
        raise RuntimeError(
            "SDKCOM is loaded but has no CreateInvoice/InvoiceAdd. "
            "Set SAGE_WRITE_MODE=odbc_guarded or update SDKCOM_PROGID."
        )

    result = create(
        customer,
        inv_date,
        payload.get("payment_reference") or requested,
        int(doc_type),
        payload.get("lines") or [],
    )
    sage_doc = None
    if isinstance(result, str):
        sage_doc = result
    elif hasattr(result, "DocumentNumber"):
        sage_doc = str(result.DocumentNumber)
    sage_doc = (sage_doc or requested).strip()
    return {"ok": True, "doc_no": sage_doc, "write_mode": "sdkcom", "created": True}


def post_receipt_sdk(
    payload: Dict[str, Any],
    *,
    progid: str,
    company_path: str,
    username: str,
    password: str,
) -> Optional[Dict[str, Any]]:
    """Return None if receipts are not exposed on this SDK version."""
    try:
        import win32com.client as win32
    except Exception:
        return None
    try:
        sdk = win32.Dispatch(progid)
    except Exception:
        return None
    create = getattr(sdk, "CreateReceipt", None) or getattr(sdk, "ReceiptAdd", None)
    if not callable(create):
        return None
    if company_path and hasattr(sdk, "Open"):
        sdk.Open(company_path, username or "", password or "")
    inserted = 0
    for idx, line in enumerate(payload.get("lines") or [], start=1):
        create(
            line.get("partner_code"),
            payload.get("payment_date"),
            float(line.get("amount") or 0),
            line.get("invoice_doc_no") or "",
            line.get("reference") or payload.get("batch_ref"),
        )
        inserted += 1
    return {
        "ok": True,
        "batch_id": payload.get("batch_ref"),
        "partner_type": "customer",
        "inserted": inserted,
        "write_mode": "sdkcom",
        "allocated": True,
    }
