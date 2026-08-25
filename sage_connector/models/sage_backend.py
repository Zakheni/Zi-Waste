"""Per-company Sage bridge connection and capability cache."""

import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


BACKEND_LIST_ARCH = """
<tree decoration-success="last_health_ok"
      decoration-danger="circuit_open"
      decoration-muted="not active">
    <field name="name" decoration-bf="1"/>
    <field name="company_id" groups="base.group_multi_company"/>
    <field name="last_health_ok" string="Connected" widget="boolean"/>
    <field name="circuit_open" string="Paused" widget="boolean" optional="show"/>
    <field name="base_url"/>
    <field name="adapter_name"/>
    <field name="write_mode"/>
    <field name="active" widget="boolean_toggle"/>
</tree>
"""


class SageBackend(models.Model):
    """HTTP endpoint and adapter settings for one Odoo company."""

    _name = "sage.backend"
    _description = "Sage Bridge Backend"
    _rec_name = "name"

    name = fields.Char(required=True, default="Sage Bridge")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company, index=True
    )
    active = fields.Boolean(default=True)
    base_url = fields.Char(required=True, help="e.g. http://127.0.0.1:8788")
    api_key = fields.Char(
        compute="_compute_api_key",
        inverse="_inverse_api_key",
        help="Stored in system parameters, not on this record.",
    )
    adapter_name = fields.Selection(
        [
            ("pastel_partner", "Pastel Partner"),
            ("pastel_partner_18", "Pastel Partner 18"),
            ("pastel_partner_21", "Pastel Partner 21"),
        ],
        default="pastel_partner",
        required=True,
    )
    timeout = fields.Integer(default=60)
    import_customers = fields.Boolean(default=True)
    import_suppliers = fields.Boolean(default=True)
    import_products = fields.Boolean(default=True)
    import_invoices = fields.Boolean(default=False)
    push_masters = fields.Boolean(
        default=False,
        help="If enabled, new Odoo partners/products can be upserted to Sage.",
    )
    last_health = fields.Text(readonly=True)
    last_health_ok = fields.Boolean(readonly=True)
    write_mode = fields.Char(readonly=True)
    capabilities_json = fields.Text(readonly=True)
    circuit_open = fields.Boolean(readonly=True)
    circuit_failures = fields.Integer(readonly=True)
    last_customer_cursor = fields.Char()
    last_supplier_cursor = fields.Char()
    last_product_cursor = fields.Char()
    last_invoice_cursor = fields.Char()
    last_customer_since = fields.Date()
    last_supplier_since = fields.Date()
    last_product_since = fields.Date()
    last_invoice_since = fields.Date()
    job_ids = fields.One2many("sage.job", "backend_id")
    log_ids = fields.One2many("sage.sync.log", "backend_id")

    _sql_constraints = [
        ("company_uniq", "unique(company_id)", "Only one Sage backend per company."),
    ]

    def _param_key(self):
        self.ensure_one()
        return "sage_connector.api_key.%s" % (self.company_id.id,)

    @api.depends("company_id")
    def _compute_api_key(self):
        ICP = self.env["ir.config_parameter"].sudo()
        for rec in self:
            rec.api_key = ICP.get_param(rec._param_key(), "") if rec.company_id else ""

    def _inverse_api_key(self):
        ICP = self.env["ir.config_parameter"].sudo()
        for rec in self:
            ICP.set_param(rec._param_key(), rec.api_key or "")

    @api.model
    def _for_company(self, company=None):
        company = company or self.env.company
        backend = self.search([("company_id", "=", company.id), ("active", "=", True)], limit=1)
        if not backend:
            raise UserError(_("No Sage backend configured for company %s.") % company.display_name)
        return backend

    def action_test_connection(self):
        self.ensure_one()
        data = self.env["sage.client"].health(self)
        self.env["sage.client"].request(self, "GET", "/v1/customers", params={"limit": 1})
        caps = data.get("capabilities") or {}
        self.write({
            "last_health": json.dumps(data, default=str),
            "last_health_ok": bool(data.get("ok")),
            "write_mode": data.get("write_mode") or "",
            "capabilities_json": json.dumps(caps),
            "circuit_open": False,
            "circuit_failures": 0,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sage Bridge"),
                "message": _("Connection OK (%s / %s)") % (data.get("adapter"), data.get("write_mode")),
                "type": "success",
            },
        }

    def capability(self, name, default=True):
        self.ensure_one()
        try:
            caps = json.loads(self.capabilities_json or "{}")
        except Exception:
            caps = {}
        if not caps:
            return default
        return bool(caps.get(name, default))

    def action_open_jobs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sage Jobs"),
            "res_model": "sage.job",
            "view_mode": "tree,form",
            "mobile_view_mode": "tree",
            "domain": [("backend_id", "=", self.id)],
            "context": {"default_backend_id": self.id, "search_default_groupby_state": 1},
        }

    def action_open_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sage Sync Logs"),
            "res_model": "sage.sync.log",
            "view_mode": "tree,form",
            "mobile_view_mode": "tree",
            "domain": [("backend_id", "=", self.id)],
            "context": {"default_backend_id": self.id},
        }

    def action_open_tax_maps(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tax Mappings"),
            "res_model": "sage.mapping.tax",
            "view_mode": "tree,form",
            "mobile_view_mode": "tree",
            "domain": [("backend_id", "=", self.id)],
            "context": {"default_backend_id": self.id},
        }

    def action_open_journal_maps(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Journal Mappings"),
            "res_model": "sage.mapping.journal",
            "view_mode": "tree,form",
            "mobile_view_mode": "tree",
            "domain": [("backend_id", "=", self.id)],
            "context": {"default_backend_id": self.id},
        }

    @api.model
    def cleanup_action_views(self):
        """Keep actions/views consistent; do not purge backend kanban."""
        View = self.env["ir.ui.view"]

        # Drop any view still referencing removed computed fields.
        View.search([
            ("model", "like", "sage.%"),
            ("arch_db", "ilike", "health_status"),
        ]).unlink()

        backend_act = self.env.ref("sage_connector.action_sage_backend", raise_if_not_found=False)
        if backend_act:
            backend_act.write({
                "view_mode": "kanban,tree,form",
                "mobile_view_mode": "kanban",
                "view_id": False,
            })

        for xid, mode in (
            ("sage_connector.action_sage_job", "tree,form"),
            ("sage_connector.action_sage_sync_log", "tree,form"),
            ("sage_connector.action_sage_mapping_tax", "tree,form"),
            ("sage_connector.action_sage_mapping_journal", "tree,form"),
        ):
            act = self.env.ref(xid, raise_if_not_found=False)
            if act:
                act.write({"view_mode": mode, "mobile_view_mode": "tree"})

        list_view = self.env.ref("sage_connector.view_sage_backend_list", raise_if_not_found=False)
        if list_view:
            list_view.write({"arch": BACKEND_LIST_ARCH, "priority": 1})

        return True
