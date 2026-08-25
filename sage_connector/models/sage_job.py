"""Durable Sage sync jobs with retry backoff."""

import json
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

BACKOFF_MINUTES = (1, 5, 15, 60)
MAX_RETRIES = 6


class SageJob(models.Model):
    """One import or export unit of work against the Sage bridge."""

    _name = "sage.job"
    _description = "Sage Sync Job"
    _order = "id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(compute="_compute_name", store=True)
    backend_id = fields.Many2one("sage.backend", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    job_type = fields.Selection(
        [
            ("import_customers", "Import Customers"),
            ("import_suppliers", "Import Suppliers"),
            ("import_products", "Import Products"),
            ("import_invoices", "Import Invoices"),
            ("export_invoice", "Export Invoice"),
            ("export_receipt_batch", "Export Receipt Batch"),
            ("upsert_customer", "Upsert Customer"),
            ("upsert_product", "Upsert Product"),
            ("transfer_import", "Transfer Import"),
            ("transfer_export", "Transfer Export"),
        ],
        required=True, index=True,
    )
    res_model = fields.Char()
    res_id = fields.Integer()
    payload = fields.Text()
    idempotency_key = fields.Char(index=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("error", "Error"),
            ("dead", "Dead"),
        ],
        default="pending", required=True, index=True, tracking=True,
    )
    retry_count = fields.Integer(default=0)
    next_retry = fields.Datetime()
    error = fields.Text()
    result = fields.Text()
    correlation_id = fields.Char(index=True)
    error_short = fields.Char(compute="_compute_error_short")
    payload_pretty = fields.Text(string="Payload", compute="_compute_pretty_json")
    result_pretty = fields.Text(string="Result", compute="_compute_pretty_json")

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

    @api.depends("payload", "result")
    def _compute_pretty_json(self):
        for rec in self:
            rec.payload_pretty = rec._pretty_json(rec.payload)
            rec.result_pretty = rec._pretty_json(rec.result)

    @api.depends("job_type", "res_model", "res_id")
    def _compute_name(self):
        labels = dict(self._fields["job_type"].selection)
        for rec in self:
            rec.name = "%s #%s" % (labels.get(rec.job_type, rec.job_type), rec.id or rec.res_id or "")

    @api.depends("error")
    def _compute_error_short(self):
        for rec in self:
            rec.error_short = (rec.error or "").replace("\n", " ")[:140]

    @api.model
    def enqueue(self, backend, job_type, payload=None, res_model=None, res_id=None, idempotency_key=None):
        """Create a pending job. Skip if the same idempotency key is already pending/done."""
        if idempotency_key:
            existing = self.search([
                ("backend_id", "=", backend.id),
                ("idempotency_key", "=", idempotency_key),
                ("state", "in", ("pending", "running", "done")),
            ], limit=1)
            if existing:
                return existing
        return self.create({
            "backend_id": backend.id,
            "job_type": job_type,
            "payload": json.dumps(payload, indent=2, default=str, ensure_ascii=False) if payload is not None and not isinstance(payload, str) else (payload or ""),
            "res_model": res_model,
            "res_id": res_id or 0,
            "idempotency_key": idempotency_key,
            "state": "pending",
        })

    @api.model
    def _recover_open_circuits(self):
        """Close the circuit when /health recovers."""
        backends = self.env["sage.backend"].search([("circuit_open", "=", True), ("active", "=", True)])
        for backend in backends:
            try:
                data = self.env["sage.client"].health(backend)
                if data.get("ok"):
                    backend.write({"circuit_open": False, "circuit_failures": 0})
            except Exception:
                continue

    @api.model
    def process_queue(self, limit=50):
        """Cron entry: process due jobs, honour circuit breaker."""
        self._recover_open_circuits()
        now = fields.Datetime.now()
        jobs = self.search([
            ("state", "in", ("pending", "error")),
            "|", ("next_retry", "=", False), ("next_retry", "<=", now),
            ("backend_id.circuit_open", "=", False),
        ], limit=limit, order="id")
        for job in jobs:
            try:
                job.with_company(job.company_id).sudo()._run()
            except Exception as exc:
                job._fail(str(exc))
        return True

    def action_retry(self):
        for rec in self:
            rec.write({"state": "pending", "next_retry": False, "error": False})
        return True

    def action_process_now(self):
        for rec in self:
            try:
                rec.with_company(rec.company_id).sudo()._run()
            except Exception as exc:
                rec._fail(str(exc))
                raise
        return True

    def _run(self):
        self.ensure_one()
        self.write({"state": "running"})
        sync = self.env["sage.sync"].with_company(self.company_id)
        payload = {}
        if self.payload:
            try:
                payload = json.loads(self.payload)
            except Exception:
                payload = {}
        handlers = {
            "import_customers": lambda: sync.import_masters(self.backend_id, ["customers"]),
            "import_suppliers": lambda: sync.import_masters(self.backend_id, ["suppliers"]),
            "import_products": lambda: sync.import_masters(self.backend_id, ["products"]),
            "import_invoices": lambda: sync.import_masters(self.backend_id, ["invoices"]),
            "export_invoice": lambda: sync.export_invoice(self.env["account.move"].browse(self.res_id), job=self),
            "export_receipt_batch": lambda: sync.export_receipt_batch(
                self.env["batch.payment"].browse(self.res_id), job=self
            ),
            "upsert_customer": lambda: sync.upsert_partner(self.env["res.partner"].browse(self.res_id)),
            "upsert_product": lambda: sync.upsert_product(self.env["product.template"].browse(self.res_id)),
            "transfer_import": lambda: sync.import_selected(self.backend_id, payload.get("kind"), payload.get("rows") or []),
            "transfer_export": lambda: sync.export_selected(self.backend_id, payload.get("kind"), payload.get("rows") or []),
        }
        handler = handlers.get(self.job_type)
        if not handler:
            raise UserError(_("Unknown job type %s") % self.job_type)
        result = handler()
        self.write({
            "state": "done",
            "result": json.dumps(result, indent=2, default=str, ensure_ascii=False) if not isinstance(result, str) else self._pretty_json(result),
            "error": False,
        })
        self.backend_id.write({"circuit_failures": 0, "circuit_open": False})
        return result

    def _fail(self, message):
        self.ensure_one()
        retries = self.retry_count + 1
        vals = {
            "retry_count": retries,
            "error": message,
            "state": "dead" if retries >= MAX_RETRIES else "error",
        }
        if retries < MAX_RETRIES:
            mins = BACKOFF_MINUTES[min(retries - 1, len(BACKOFF_MINUTES) - 1)]
            vals["next_retry"] = fields.Datetime.now() + timedelta(minutes=mins)
        self.write(vals)
        backend = self.backend_id
        fails = backend.circuit_failures + 1
        backend.write({
            "circuit_failures": fails,
            "circuit_open": fails >= 5,
        })
