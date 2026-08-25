"""History of Sage Pastel batch payment export attempts."""

import json

from odoo import api, fields, models


class BatchPaymentExportHistory(models.Model):
    """Persist request/response payloads for each batch export to Sage."""

    _name = "batch.payment.export.history"
    _description = "Batch Payment Export History"
    _order = "export_date desc"
    _rec_name = "display_name"

    batch_id = fields.Many2one(
        "batch.payment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="batch_id.company_id",
        store=True,
        index=True,
    )
    export_date = fields.Datetime(
        string="Export Date",
        default=fields.Datetime.now,
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Exported By",
        default=lambda self: self.env.user,
        required=True,
    )
    state = fields.Selection(
        [
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        required=True,
        index=True,
    )
    sage_reference = fields.Char(string="Sage Reference")
    request_payload = fields.Text(string="Request Payload (JSON)")
    response_payload = fields.Text(string="Response / Error")

    display_name = fields.Char(compute="_compute_display_name", store=True)
    request_pretty = fields.Text(
        string="Request",
        compute="_compute_pretty_payloads",
    )
    response_pretty = fields.Text(
        string="Response",
        compute="_compute_pretty_payloads",
    )
    is_success = fields.Boolean(compute="_compute_flags")
    is_failed = fields.Boolean(compute="_compute_flags")

    @api.depends("batch_id", "batch_id.name", "export_date", "state")
    def _compute_display_name(self):
        for rec in self:
            batch = rec.batch_id.name or "Batch"
            when = fields.Datetime.to_string(rec.export_date) if rec.export_date else ""
            status = dict(rec._fields["state"].selection).get(rec.state, "")
            rec.display_name = "%s · %s · %s" % (batch, status, when)

    @api.depends("state")
    def _compute_flags(self):
        for rec in self:
            rec.is_success = rec.state == "success"
            rec.is_failed = rec.state == "failed"

    @api.depends("request_payload", "response_payload")
    def _compute_pretty_payloads(self):
        for rec in self:
            rec.request_pretty = rec._pretty_json(rec.request_payload)
            rec.response_pretty = rec._pretty_json(rec.response_payload)

    @staticmethod
    def _pretty_json(raw):
        if not raw:
            return ""
        text = raw if isinstance(raw, str) else str(raw)
        text = text.strip()
        if not text:
            return ""
        try:
            return json.dumps(json.loads(text), indent=2, ensure_ascii=False, default=str)
        except Exception:
            return text
