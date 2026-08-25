"""Partner credit balance fields used by Pastel batch payment."""

from odoo import models, fields, api


class ResPartner(models.Model):
    """Extend partners with customer credit summary fields."""

    _inherit = 'res.partner'

    credit_ids = fields.One2many(
        "customer.credit",
        "partner_id",
    )

    credit_balance = fields.Monetary(
        compute="_compute_credit_balance",
        currency_field="currency_id",
        string="Credit Balance",
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends("credit_ids.balance")
    def _compute_credit_balance(self):
        """Sum balances of open credit records for the partner."""
        for partner in self:
            partner.credit_balance = sum(
                partner.credit_ids.filtered(
                    lambda c: c.state == "open"
                ).mapped("balance")
            )

    credit_count = fields.Integer(
        compute="_compute_credit_count"
    )

    def _compute_credit_count(self):
        """Count linked customer credit records."""
        for partner in self:
            partner.credit_count = len(partner.credit_ids)
