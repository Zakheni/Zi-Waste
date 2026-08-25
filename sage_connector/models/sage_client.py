"""HTTP client for sage_bridge /v1. Logs every call. No query-string keys."""

import json
import logging
import time
import uuid

import requests

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
MAX_BODY = 8000


class SageClient(models.AbstractModel):
    """Thin requests wrapper with correlation ids and truncated logs."""

    _name = "sage.client"
    _description = "Sage Bridge HTTP Client"

    def _truncate(self, data):
        text = data if isinstance(data, str) else json.dumps(data, default=str)
        if len(text) > MAX_BODY:
            return text[:MAX_BODY] + "...[truncated]"
        return text

    def _headers(self, backend, idempotency_key=None):
        headers = {
            "x-api-key": backend.api_key or "",
            "Content-Type": "application/json",
            "X-Correlation-Id": uuid.uuid4().hex,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def request(self, backend, method, path, params=None, json_body=None, idempotency_key=None, job=None):
        if not backend.base_url:
            raise UserError(_("Sage backend has no base URL."))
        url = backend.base_url.rstrip("/") + path
        headers = self._headers(backend, idempotency_key)
        correlation = headers["X-Correlation-Id"]
        started = time.time()
        log_vals = {
            "backend_id": backend.id,
            "job_id": job.id if job else False,
            "correlation_id": correlation,
            "method": method,
            "path": path,
            "request_body": self._truncate(json_body or params or ""),
        }
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=backend.timeout or 60,
            )
            duration = int((time.time() - started) * 1000)
            body = resp.text
            try:
                parsed = resp.json() if body else {}
            except Exception:
                parsed = {"raw": body}
            log_vals.update({
                "http_status": resp.status_code,
                "duration_ms": duration,
                "response_body": self._truncate(parsed),
                "ok": 200 <= resp.status_code < 300,
            })
            self.env["sage.sync.log"].sudo().create(log_vals)
            if not (200 <= resp.status_code < 300):
                raise UserError(_("Sage bridge %s %s failed (%s): %s") % (
                    method, path, resp.status_code, body[:500],
                ))
            return parsed
        except UserError:
            raise
        except requests.RequestException as exc:
            duration = int((time.time() - started) * 1000)
            log_vals.update({
                "duration_ms": duration,
                "ok": False,
                "error": str(exc),
            })
            self.env["sage.sync.log"].sudo().create(log_vals)
            raise UserError(_("Sage bridge request failed: %s") % exc)

    def health(self, backend):
        url = backend.base_url.rstrip("/") + "/health"
        try:
            resp = requests.get(url, timeout=backend.timeout or 15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise UserError(_("Sage health check failed: %s") % exc)

    def get_page(self, backend, path, since=None, cursor=None, limit=200, extra=None, job=None):
        params = {"limit": limit}
        if since:
            params["since"] = since
        if cursor:
            params["cursor"] = cursor
        if extra:
            params.update(extra)
        data = self.request(backend, "GET", path, params=params, job=job)
        if isinstance(data, list):
            return data, None, False
        items = data.get("items") or []
        meta = data.get("meta") or {}
        return items, meta.get("next_cursor"), bool(meta.get("has_more"))
