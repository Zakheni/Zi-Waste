"""Customer credit ledger entries created from batch payment overpayments."""

from odoo import fields, models


class CustomerCredit(models.Model):
    """Track open customer credit balances linked to batch payments."""

    _name = "customer.credit"
    _description = "Customer Credit"
    _order = "create_date desc"

    usage_ids = fields.One2many(
        "customer.credit.usage",
        "credit_id",
        string="Usage History"
    )

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="cascade",
    )

    batch_id = fields.Many2one(
        "batch.payment"
    )

    amount = fields.Monetary(
        required=True,
        currency_field="currency_id",
    )

    balance = fields.Monetary(
        required=True,
        currency_field="currency_id",
    )

    state = fields.Selection([
        ("open", "Open"),
        ("used", "Used"),
    ], default="open")

    notes = fields.Text()

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

