"""Pastel connector settings and Sage field extensions on core Odoo models."""

from odoo import models, fields, _
from odoo.exceptions import UserError


class PastelConnectorSetting(models.Model):
    """Bridge URL, API key, and push-to-Sage configuration per company."""

    _name = "pastel.connector.setting"
    _description = "Pastel Connector Settings"
    _rec_name = "name"

    name = fields.Char(default="Pastel Connector Configuration", readonly=True)
    pastel_api_base = fields.Char(string="Bridge URL", required=True, help="e.g. http://WINDOWS-IP:8787")
    pastel_api_key  = fields.Char(string="API Key", required=True)
    enable_push_to_sage = fields.Boolean(string="Enable push (Odoo → Sage)", default=True,
                                         help="If enabled, Odoo edits/deletes will be pushed to Sage via the bridge")

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    def action_test_connection(self):
        """Ping the Pastel bridge health endpoint and show a success notification."""
        self.ensure_one()
        ok = self.env["pastel.sync"].pastel_test_connection()
        if ok:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Pastel"), "message": _("Connection OK"), "type": "success"},
            }
        raise UserError(_("Connection failed"))

    def action_import_all_now(self):
        """Import customers, products, and invoices from Sage and notify the user."""
        self.ensure_one()
        res = self.env["pastel.sync"].import_all(customers=True, products=True, invoices=True)
        msg = _("Imported: Cust %(ci)s/%(cu)s updated, Prod %(pi)s/%(pu)s updated, Inv %(ii)s/%(iu)s updated") % res
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Pastel Import"), "message": msg, "type": "success"},
        }


class ResPartner(models.Model):
    """Store Sage customer identifiers and accounting metadata on partners."""

    _inherit = "res.partner"
    x_pastel_code = fields.Char(index=True, copy=False, string="Sage Customer Code")
    x_pastel_tax_code = fields.Char(string="Sage Tax Code")
    x_pastel_category = fields.Char(string="Sage Category")
    x_pastel_currency_code = fields.Char(string="Sage Currency")
    x_pastel_open_item = fields.Boolean(string="Sage Open Item")
    x_pastel_credit_limit = fields.Float(string="Sage Credit Limit", copy=False)
    x_pastel_balance = fields.Float(string="Sage Current Balance", copy=False)


class ProductTemplate(models.Model):
    """Store Sage item code and tax metadata on product templates."""

    _inherit = "product.template"
    x_pastel_item_code = fields.Char(index=True, string="Sage Item Code")
    x_pastel_price_regime = fields.Char(string="Sage Price Regime")
    x_pastel_tax_code = fields.Char(string="Sage Tax Code")


class AccountMove(models.Model):
    """Store Sage document number and status on customer invoices."""

    _inherit = "account.move"
    x_pastel_doc_no = fields.Char(string="Sage Doc No.", index=True)
    x_pastel_status = fields.Char(string="Sage Status")
