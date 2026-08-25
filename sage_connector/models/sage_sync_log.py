"""Request/response log for Sage bridge calls."""

import json

from odoo import api, fields, models


class SageSyncLog(models.Model):
    """Truncated HTTP trace for one Sage bridge call."""

    _name = "sage.sync.log"
    _description = "Sage Sync Log"
    _order = "id desc"

    backend_id = fields.Many2one("sage.backend", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True)
    job_id = fields.Many2one("sage.job", ondelete="set null")
    correlation_id = fields.Char(index=True)
    method = fields.Char()
    path = fields.Char()
    http_status = fields.Integer()
    duration_ms = fields.Integer()
    request_body = fields.Text()
    response_body = fields.Text()
    error = fields.Text()
    ok = fields.Boolean()
    status_label = fields.Char(compute="_compute_status_label")
    request_pretty = fields.Text(string="Request", compute="_compute_pretty_json")
    response_pretty = fields.Text(string="Response", compute="_compute_pretty_json")

    @staticmethod
    def _pretty_json(raw):
        if not raw:
            return ""
        if not isinstance(raw, str):
            try:
                return json.dumps(raw, indent=2, default=str, ensure_ascii=False)
            except Exception:
                return str(raw)
        text = raw.strip()
        if not text:
            return ""
        try:
            return json.dumps(json.loads(text), indent=2, default=str, ensure_ascii=False)
        except Exception:
            return raw

    @api.depends("request_body", "response_body")
    def _compute_pretty_json(self):
        for rec in self:
            rec.request_pretty = rec._pretty_json(rec.request_body)
            rec.response_pretty = rec._pretty_json(rec.response_body)

    @api.depends("ok", "http_status")
    def _compute_status_label(self):
        for rec in self:
            if rec.ok:
                rec.status_label = "OK %s" % (rec.http_status or "")
            elif rec.http_status:
                rec.status_label = "Failed %s" % rec.http_status
            else:
                rec.status_label = "Failed"
